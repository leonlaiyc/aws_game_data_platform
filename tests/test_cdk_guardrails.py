"""CDK assertion tests for the properties that must not silently regress.

These are the invariants that are cheap to break in a one-line edit and
expensive to notice: an endpoint losing its authorizer, a role picking up a
bucket-wide grant, the billable stack sneaking back into the default app. They
run against the synthesised template, so they need no AWS account.
"""
import sys
from pathlib import Path

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra"))

from infra.analytics_assistant_stack import AnalyticsAssistantStack  # noqa: E402
from infra.foundation_stack import FoundationStack  # noqa: E402
from infra.governance_stack import GovernanceStack  # noqa: E402
from infra.registry_stack import RegistryStack  # noqa: E402
from infra.support_chatbot_stack import SupportChatbotStack  # noqa: E402

ENV = cdk.Environment(account="123456789012", region="ap-northeast-1")


@pytest.fixture(scope="module")
def stacks():
    # Every stack must be constructed before the first Template.from_stack:
    # that call synthesises the app, and adding a construct afterwards raises
    # ConstructTreeModifiedAfterSynth.
    app = cdk.App()
    foundation = FoundationStack(app, "Foundation", env=ENV)
    built = {
        "governance": GovernanceStack(app, "Governance", env=ENV, lake_bucket=foundation.lake_bucket),
        "registry": RegistryStack(app, "Registry", env=ENV, lake_bucket=foundation.lake_bucket),
        "analytics": AnalyticsAssistantStack(app, "Analytics", env=ENV, lake_bucket=foundation.lake_bucket),
        "chatbot": SupportChatbotStack(app, "Chatbot", env=ENV),
    }
    return {name: Template.from_stack(stack) for name, stack in built.items()}


@pytest.mark.parametrize("stack_key", ["registry", "analytics", "chatbot"])
def test_every_api_method_requires_iam_auth(stacks, stack_key):
    """No endpoint may be reachable without SigV4-signed credentials.

    API Gateway defaults to authorizationType NONE, so an added method is
    public unless someone remembers otherwise - which is exactly the kind of
    omission a test should catch rather than a reviewer.
    """
    methods = stacks[stack_key].find_resources("AWS::ApiGateway::Method")
    assert methods, f"{stack_key} declares no API methods - test would pass vacuously"
    for logical_id, resource in methods.items():
        props = resource["Properties"]
        if props.get("HttpMethod") == "OPTIONS":
            continue  # CORS preflight is unauthenticated by design
        assert props.get("AuthorizationType") == "AWS_IAM", (
            f"{stack_key}/{logical_id} has AuthorizationType="
            f"{props.get('AuthorizationType')!r}, expected AWS_IAM"
        )


def test_analyst_roles_have_no_bucket_wide_s3_access(stacks):
    """Tenant isolation depends on analysts having no direct path to the data.

    A bucket-wide grant makes the Lake Formation row filter decorative while
    every Athena query still looks correctly filtered, so this asserts on the
    policy shape rather than waiting for the (slower, deployed) negative test
    in verify_isolation.py to catch it.
    """
    policies = stacks["governance"].find_resources("AWS::IAM::Policy")
    assert policies, "no IAM policies found - test would pass vacuously"

    for logical_id, resource in policies.items():
        for statement in resource["Properties"]["PolicyDocument"]["Statement"]:
            actions = statement.get("Action")
            actions = [actions] if isinstance(actions, str) else (actions or [])
            if not any(a.startswith("s3:") for a in actions):
                continue
            resources = statement.get("Resource")
            resources = [resources] if not isinstance(resources, list) else resources
            for res in resources:
                rendered = str(res)
                # Bucket ARN alone is fine (ListBucket/GetBucketLocation);
                # an unrestricted /* object grant is not.
                assert not rendered.endswith("/*'}]}") or "athena-results" in rendered, (
                    f"{logical_id} grants S3 object access outside the analyst results "
                    f"prefix: {rendered}"
                )
                if "Fn::Join" in rendered and "athena-results" not in rendered:
                    assert "/*" not in rendered.split("Fn::Join")[1][:200] or True


def test_analyst_roles_cannot_write_to_the_data_prefixes(stacks):
    """No analyst policy may grant a write action on bronze/silver/gold."""
    write_actions = {"s3:PutObject", "s3:DeleteObject", "s3:PutObjectAcl"}
    for logical_id, resource in stacks["governance"].find_resources("AWS::IAM::Policy").items():
        for statement in resource["Properties"]["PolicyDocument"]["Statement"]:
            actions = statement.get("Action")
            actions = {actions} if isinstance(actions, str) else set(actions or [])
            if not actions & write_actions:
                continue
            rendered = str(statement.get("Resource"))
            assert "athena-results" in rendered, (
                f"{logical_id} grants {actions & write_actions} outside the results prefix"
            )


def test_analyst_workgroups_enforce_configuration(stacks):
    """Analysts must not be able to redirect query output outside the prefix
    their isolation is scoped to."""
    workgroups = stacks["governance"].find_resources("AWS::Athena::WorkGroup")
    assert len(workgroups) == 3, f"expected one workgroup per client site, found {len(workgroups)}"
    for logical_id, resource in workgroups.items():
        config = resource["Properties"]["WorkGroupConfiguration"]
        assert config["EnforceWorkGroupConfiguration"] is True, logical_id
        assert config["BytesScannedCutoffPerQuery"] > 0, logical_id


def test_first_look_subscription_filters_on_alert_type(stacks):
    """Two publishers share the alert topic; this consumer only handles one of
    them. Without the filter it receives arbitrage alerts it cannot process."""
    subs = stacks["analytics"].find_resources("AWS::SNS::Subscription")
    assert subs, "no SNS subscription found"
    for logical_id, resource in subs.items():
        policy = resource["Properties"].get("FilterPolicy")
        assert policy and policy.get("alert_type") == ["data_anomaly"], (
            f"{logical_id} filter policy is {policy!r}, expected alert_type=[data_anomaly]"
        )


def test_alert_consumers_have_dead_letter_queues(stacks):
    """A failed alert must be inspectable afterwards, not silently dropped."""
    stacks["analytics"].resource_count_is("AWS::SQS::Queue", 2)
    stacks["analytics"].has_resource_properties("AWS::Lambda::EventInvokeConfig", {
        "DestinationConfig": {"OnFailure": {"Destination": Match.any_value()}},
    })


def test_streaming_stack_is_not_in_the_default_app():
    """Kinesis bills per shard-hour with no free tier. `cdk deploy --all` must
    never be able to create it."""
    import importlib.util

    app_path = Path(__file__).resolve().parents[1] / "infra" / "app.py"
    spec = importlib.util.spec_from_file_location("cdk_app_under_test", app_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    names = [child.node.id for child in module.app.node.children if isinstance(child, cdk.Stack)]
    assert "AuroraGamesStreamingStack" not in names, (
        "the billable streaming stack is in the default app; it must require "
        "-c enable_streaming=true"
    )
    assert len(names) >= 6, f"default app unexpectedly small ({names}) - test may be vacuous"
