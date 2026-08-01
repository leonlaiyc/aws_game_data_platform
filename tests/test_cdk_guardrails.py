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
from infra.observability_stack import ObservabilityStack  # noqa: E402
from infra.orchestration_stack import OrchestrationStack  # noqa: E402
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
    registry = RegistryStack(
        app, "Registry", env=ENV, lake_bucket=foundation.lake_bucket
    )
    orchestration = OrchestrationStack(
        app,
        "Orchestration",
        env=ENV,
        lake_bucket=foundation.lake_bucket,
        experiments_table=registry.experiments_table,
        exposures_table=registry.exposures_table,
    )
    observability = ObservabilityStack(
        app,
        "Observability",
        env=ENV,
        lambda_function_names={"TestFunction": "aurora-games-test"},
        state_machine_arn=(
            "arn:aws:states:ap-northeast-1:123456789012:"
            "stateMachine:aurora-games-test"
        ),
        dlq_names=["aurora-games-test-dlq"],
    )
    built = {
        "foundation": foundation,
        "governance": GovernanceStack(app, "Governance", env=ENV, lake_bucket=foundation.lake_bucket),
        "registry": registry,
        "orchestration": orchestration,
        "analytics": AnalyticsAssistantStack(app, "Analytics", env=ENV, lake_bucket=foundation.lake_bucket),
        "chatbot": SupportChatbotStack(app, "Chatbot", env=ENV),
        "observability": observability,
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

    object_actions = {
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:AbortMultipartUpload",
    }
    for logical_id, resource in policies.items():
        for statement in resource["Properties"]["PolicyDocument"]["Statement"]:
            actions = statement.get("Action")
            actions = [actions] if isinstance(actions, str) else (actions or [])
            if not object_actions.intersection(actions):
                continue
            resources = statement.get("Resource")
            resources = [resources] if not isinstance(resources, list) else resources
            for res in resources:
                rendered = str(res)
                assert "athena-results/analyst/" in rendered, (
                    f"{logical_id} grants S3 object access outside the analyst results "
                    f"prefix: {rendered}"
                )


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
    """The first-look consumer handles business-metric alerts, but not
    arbitrage alerts that have a different evidence contract."""
    subs = stacks["analytics"].find_resources("AWS::SNS::Subscription")
    assert subs, "no SNS subscription found"
    for logical_id, resource in subs.items():
        if resource["Properties"].get("Protocol") != "lambda":
            continue  # account-local report delivery is an outbound SQS sink
        policy = resource["Properties"].get("FilterPolicy")
        assert policy and policy.get("alert_type") == [
            "data_anomaly",
            "retention_anomaly",
        ], (
            f"{logical_id} filter policy is {policy!r}, expected business alert types"
        )


def test_alert_consumers_have_dead_letter_queues(stacks):
    """A failed alert must be inspectable afterwards, not silently dropped."""
    # Two DLQs plus one account-local first-look delivery sink.
    stacks["analytics"].resource_count_is("AWS::SQS::Queue", 3)
    stacks["analytics"].has_resource_properties("AWS::Lambda::EventInvokeConfig", {
        "DestinationConfig": {"OnFailure": {"Destination": Match.any_value()}},
    })


def test_first_look_report_has_a_delivery_channel(stacks):
    stacks["analytics"].has_resource_properties("AWS::SNS::Topic", {
        "TopicName": "aurora-games-first-look-reports",
    })
    stacks["analytics"].has_resource_properties("AWS::SQS::Queue", {
        "QueueName": "aurora-games-first-look-report-audit",
    })
    stacks["analytics"].has_resource_properties("AWS::Lambda::Function", {
        "Environment": {
            "Variables": {
                "REPORTS_TOPIC_ARN": Match.any_value(),
            },
        },
    })


def test_support_escalations_have_a_real_ticket_store(stacks):
    """A returned ticket id must identify a durable work item, not just a UUID
    formatted into friendly copy."""
    stacks["chatbot"].resource_count_is("AWS::DynamoDB::Table", 2)
    stacks["chatbot"].has_resource_properties("AWS::DynamoDB::Table", {
        "KeySchema": [{"AttributeName": "ticket_id", "KeyType": "HASH"}],
        "BillingMode": "PAY_PER_REQUEST",
    })
    stacks["chatbot"].has_resource_properties("AWS::Lambda::Function", {
        "Environment": {
            "Variables": {
                "SUPPORT_TICKETS_TABLE_NAME": Match.any_value(),
            },
        },
    })


def test_support_chat_identity_selects_one_of_two_partner_corpora(stacks):
    support = stacks["chatbot"]
    support.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": "aurora-games-game-provider-partner"},
    )
    support.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": "aurora-games-client-operator-partner"},
    )
    functions = support.find_resources("AWS::Lambda::Function")
    environments = [
        resource["Properties"].get("Environment", {}).get("Variables", {})
        for resource in functions.values()
    ]
    assert any(
        env.get("GAME_PROVIDER_PRINCIPAL_PATTERN")
        == "aurora-games-game-provider-partner"
        and env.get("CLIENT_OPERATOR_PRINCIPAL_PATTERN")
        == "aurora-games-client-operator-partner"
        and env.get("DAILY_REQUEST_LIMIT") == "50"
        for env in environments
    )
    support.has_resource_properties(
        "AWS::ApiGateway::Stage",
        {
            "MethodSettings": [
                Match.object_like({
                    "ThrottlingBurstLimit": 2,
                    "ThrottlingRateLimit": 0.1,
                })
            ]
        },
    )


def test_support_sessions_and_notifications_are_durable_without_external_recipient(stacks):
    stacks["chatbot"].has_resource_properties("AWS::DynamoDB::Table", {
        "TableName": "aurora-games-support-sessions",
        "BillingMode": "PAY_PER_REQUEST",
        "KeySchema": [{"AttributeName": "session_id", "KeyType": "HASH"}],
        "TimeToLiveSpecification": {
            "AttributeName": "expires_at",
            "Enabled": True,
        },
        "OnDemandThroughput": {
            "MaxReadRequestUnits": 10,
            "MaxWriteRequestUnits": 10,
        },
    })
    stacks["chatbot"].has_resource_properties("AWS::SNS::Topic", {
        "TopicName": "aurora-games-partner-notifications",
    })
    stacks["chatbot"].has_resource_properties("AWS::SQS::Queue", {
        "QueueName": "aurora-games-partner-notification-audit",
    })
    stacks["chatbot"].has_resource_properties("AWS::ApiGateway::Resource", {
        "PathPart": "notifications",
    })
    subscriptions = stacks["chatbot"].find_resources("AWS::SNS::Subscription")
    assert subscriptions
    for resource in subscriptions.values():
        assert resource["Properties"]["Protocol"] == "sqs"


def test_analytics_fallback_has_a_real_bounded_ticket_store(stacks):
    stacks["analytics"].has_resource_properties("AWS::DynamoDB::Table", {
        "TableName": "aurora-games-analytics-tickets",
        "BillingMode": "PAY_PER_REQUEST",
        "KeySchema": [{"AttributeName": "ticket_id", "KeyType": "HASH"}],
        "TimeToLiveSpecification": {
            "AttributeName": "expires_at",
            "Enabled": True,
        },
        "OnDemandThroughput": {
            "MaxReadRequestUnits": 5,
            "MaxWriteRequestUnits": 5,
        },
    })
    stacks["analytics"].has_resource_properties("AWS::Lambda::Function", {
        "Environment": {
            "Variables": {
                "ANALYTICS_TICKETS_TABLE_NAME": Match.any_value(),
                "LAKE_BUCKET_NAME": Match.any_value(),
            },
        },
    })


def test_registry_can_stop_the_execution_it_records(stacks):
    policies = stacks["registry"].find_resources("AWS::IAM::Policy")
    actions = []
    for resource in policies.values():
        for statement in resource["Properties"]["PolicyDocument"]["Statement"]:
            value = statement.get("Action", [])
            actions.extend([value] if isinstance(value, str) else value)
    assert "states:StartExecution" in actions
    assert "states:StopExecution" in actions
    assert "dynamodb:TransactWriteItems" in actions


def test_live_exposures_are_idempotent_bounded_and_queryable(stacks):
    """The live product path needs a real event store, not assignment output
    relabeled as exposure data."""
    stacks["registry"].has_resource_properties("AWS::DynamoDB::Table", {
        "TableName": "aurora-games-experiment-exposures",
        "BillingMode": "PAY_PER_REQUEST",
        "KeySchema": [
            {"AttributeName": "experiment_id", "KeyType": "HASH"},
            {"AttributeName": "event_id", "KeyType": "RANGE"},
        ],
        "TimeToLiveSpecification": {
            "AttributeName": "expires_at",
            "Enabled": True,
        },
        "OnDemandThroughput": {
            "MaxReadRequestUnits": 25,
            "MaxWriteRequestUnits": 25,
        },
        "StreamSpecification": {"StreamViewType": "NEW_IMAGE"},
    })
    stacks["registry"].has_resource_properties("AWS::Lambda::Function", {
        "Environment": {
            "Variables": {
                "EXPOSURES_TABLE_NAME": Match.any_value(),
            },
        },
    })
    stacks["registry"].has_resource_properties("AWS::ApiGateway::Resource", {
        "PathPart": "exposures",
    })


def test_live_experiment_waits_without_compute_and_monitor_can_stop_it(stacks):
    state_machines = stacks["orchestration"].find_resources(
        "AWS::StepFunctions::StateMachine"
    )
    assert len(state_machines) == 1
    rendered = str(next(iter(state_machines.values()))["Properties"])
    assert "WaitUntilPlannedEnd" in rendered
    assert "TimestampPath" in rendered
    assert "$.planned_end_at" in rendered
    assert "CompletionTransitionApplied?" in rendered
    assert "$.state_mark.transitioned" in rendered
    assert "StoppedEarlyAfterMonitoring" in rendered

    policies = stacks["orchestration"].find_resources("AWS::IAM::Policy")
    actions = []
    for resource in policies.values():
        for statement in resource["Properties"]["PolicyDocument"]["Statement"]:
            value = statement.get("Action", [])
            actions.extend([value] if isinstance(value, str) else value)
    assert "states:StopExecution" in actions


def test_paid_account_has_five_dollar_forecast_and_actual_budget(stacks):
    """A paid-plan account must have an early warning and a hard threshold.

    This is deliberately tested in the synthesised infrastructure rather than
    treated as an account-side manual convention that can drift away.
    """
    stacks["observability"].resource_count_is("AWS::Budgets::Budget", 1)
    stacks["observability"].has_resource_properties("AWS::Budgets::Budget", {
        "Budget": {
            "BudgetLimit": {"Amount": 5, "Unit": "USD"},
            "BudgetName": "aurora-games-monthly",
            "BudgetType": "COST",
            "TimeUnit": "MONTHLY",
        },
        "NotificationsWithSubscribers": Match.array_with([
            Match.object_like({
                "Notification": {
                    "ComparisonOperator": "GREATER_THAN",
                    "NotificationType": "FORECASTED",
                    "Threshold": 80,
                    "ThresholdType": "PERCENTAGE",
                },
            }),
            Match.object_like({
                "Notification": {
                    "ComparisonOperator": "GREATER_THAN",
                    "NotificationType": "ACTUAL",
                    "Threshold": 100,
                    "ThresholdType": "PERCENTAGE",
                },
            }),
        ]),
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

    # These resource families carry meaningful idle or provisioned-capacity
    # risk and therefore require an explicit, separately reviewed opt-in. A
    # free-first default deployment may use request-priced serverless services,
    # but must not silently introduce one of these.
    disallowed_default_types = {
        "AWS::EC2::NatGateway",
        "AWS::RDS::DBCluster",
        "AWS::RDS::DBInstance",
        "AWS::Redshift::Cluster",
        "AWS::OpenSearchService::Domain",
        "AWS::OpenSearchServerless::Collection",
        "AWS::MSK::Cluster",
        "AWS::EKS::Cluster",
    }
    for stack in (child for child in module.app.node.children if isinstance(child, cdk.Stack)):
        resources = Template.from_stack(stack).to_json().get("Resources", {})
        found = {
            resource["Type"]
            for resource in resources.values()
            if resource.get("Type") in disallowed_default_types
        }
        assert not found, (
            f"{stack.stack_name} contains paid-plan idle-cost resources in the "
            f"default app: {sorted(found)}"
        )
