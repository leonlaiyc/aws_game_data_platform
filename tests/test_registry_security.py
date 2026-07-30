"""Security and validation tests for the Module 2 experiment registry.

The registry is a data-plane boundary: an authenticated analyst must see only
their own tenant, and model-facing metric names must come from a closed set
before they can reach dynamically assembled Athena SQL.
"""
import json
from decimal import Decimal

import pytest

from conftest import REPO_ROOT, load_handler

REGISTRY_DIR = REPO_ROOT / "module2-experimentation-platform" / "registry" / "lambda" / "api"
handler = load_handler(
    "m2_registry_handler",
    REGISTRY_DIR,
    env={
        "EXPERIMENTS_TABLE_NAME": "test-experiments",
        "EXPOSURES_TABLE_NAME": "test-exposures",
        "ORCHESTRATION_STATE_MACHINE_ARN": "arn:aws:states:ap-northeast-1:123:stateMachine:test",
        "OPERATOR_PRINCIPAL_PATTERN": "aurora-games-operator",
        "ALLOWED_CLIENT_SITES": "site_a,site_b,site_c",
        "AWS_DEFAULT_REGION": "ap-northeast-1",
    },
)

ANALYST = "arn:aws:sts::123456789012:assumed-role/aurora-games-analyst-{site}/session"
OPERATOR = "arn:aws:sts::123456789012:assumed-role/aurora-games-operator/session"


def event_for(arn):
    return {"requestContext": {"identity": {"userArn": arn}}}


def valid_payload(site="site_a"):
    return {
        "name": "Payout copy test",
        "game_id": "game_123",
        "client_site_id": site,
        "audience": {"client_site_id": site},
        "variants": [
            {"name": "control", "weight": Decimal("0.5")},
            {"name": "treatment", "weight": Decimal("0.5")},
        ],
        "oec_metric": "ggr_usd_7d",
        "guardrail_metrics": [
            {"metric": "sessions_7d", "direction": "min", "threshold": Decimal("1")},
        ],
    }


@pytest.mark.parametrize("site", ["site_a", "site_b", "site_c"])
def test_analyst_maps_to_exactly_one_site(site):
    assert handler._caller_scope(event_for(ANALYST.format(site=site))) == site


def test_operator_is_the_only_unscoped_role():
    assert handler._caller_scope(event_for(OPERATOR)) is None


@pytest.mark.parametrize("arn", [
    "arn:aws:sts::123456789012:assumed-role/evil-aurora-games-operator/session",
    "arn:aws:sts::123456789012:assumed-role/aurora-games-operator-admin/session",
    "arn:aws:iam::123456789012:user/aurora-games-operator",
    "",
])
def test_similar_or_unknown_identity_fails_closed(arn):
    with pytest.raises(handler.ScopeResolutionError):
        handler._caller_scope(event_for(arn))


def test_analyst_cannot_create_for_another_site():
    response = handler.create_experiment(valid_payload("site_b"), caller_site="site_a")
    assert response["statusCode"] == 403


class FakeTable:
    def __init__(self):
        self.pages = [
            {
                "Items": [
                    {"experiment_id": "a1", "client_site_id": "site_a"},
                    {"experiment_id": "b1", "client_site_id": "site_b"},
                ],
                "LastEvaluatedKey": {"experiment_id": "b1"},
            },
            {"Items": [{"experiment_id": "a2", "client_site_id": "site_a"}]},
        ]

    def scan(self, **kwargs):
        return self.pages.pop(0)

    def get_item(self, Key):
        return {
            "Item": {
                "experiment_id": Key["experiment_id"],
                "client_site_id": "site_b",
                "state": "draft",
            },
        }


def test_list_filters_every_scan_page_to_callers_site(monkeypatch):
    monkeypatch.setattr(handler, "table", FakeTable())
    response = handler.list_experiments("site_a")
    body = json.loads(response["body"])
    assert [item["experiment_id"] for item in body["experiments"]] == ["a1", "a2"]


def test_cross_tenant_get_is_indistinguishable_from_missing(monkeypatch):
    monkeypatch.setattr(handler, "table", FakeTable())
    response = handler.get_experiment("b1", "site_a")
    assert response["statusCode"] == 404
    assert json.loads(response["body"]) == {"error": "not found"}


@pytest.mark.parametrize("mutator", [
    lambda p: p.update(client_site_id="site_z"),
    lambda p: p.update(game_id="game'; DROP TABLE experiments; --"),
    lambda p: p.update(oec_metric="SUM(secret_column)"),
    lambda p: p.update(variants=[
        {"name": "control", "weight": Decimal("0.9")},
        {"name": "treatment", "weight": Decimal("0.9")},
    ]),
    lambda p: p.update(guardrail_metrics=[
        {"metric": "secret_metric", "direction": "max", "threshold": Decimal("1")},
    ]),
    lambda p: p.update(audience={"client_site_id": "site_b"}),
])
def test_untrusted_registry_fields_are_rejected(mutator):
    payload = valid_payload()
    mutator(payload)
    assert handler._validate_payload(payload) is not None


class ConditionalCheckFailedException(Exception):
    pass


class ExecutionDoesNotExist(Exception):
    pass


class LifecycleTable:
    class meta:
        class client:
            class exceptions:
                ConditionalCheckFailedException = ConditionalCheckFailedException

    def __init__(self, item=None, fail_update_number=None, order=None):
        self.item = item or {
            "experiment_id": "exp_test",
            "client_site_id": "site_a",
            "state": "draft",
        }
        self.fail_update_number = fail_update_number
        self.order = order
        self.updates = []

    def get_item(self, Key):
        return {"Item": self.item}

    def update_item(self, **kwargs):
        self.updates.append(kwargs)
        if self.order is not None:
            self.order.append("table_update")
        if len(self.updates) == self.fail_update_number:
            raise RuntimeError("simulated DynamoDB failure")


def test_start_execution_failure_rolls_registry_back_to_draft(monkeypatch):
    class FailingSfn:
        def start_execution(self, **kwargs):
            raise RuntimeError("simulated Step Functions outage")

    fake_table = LifecycleTable()
    monkeypatch.setattr(handler, "table", fake_table)
    monkeypatch.setattr(handler, "sfn", FailingSfn())

    with pytest.raises(RuntimeError, match="Step Functions outage"):
        handler.start_experiment(
            "exp_test",
            {"as_of_date": "2026-05-10", "duration_days": 7},
            caller_site="site_a",
        )

    assert len(fake_table.updates) == 2
    assert ":running" in fake_table.updates[0]["ExpressionAttributeValues"]
    assert ":draft" in fake_table.updates[1]["ExpressionAttributeValues"]
    assert "REMOVE started_at, assignment_seed" in fake_table.updates[1]["UpdateExpression"]


def test_execution_is_stopped_if_its_arn_cannot_be_persisted(monkeypatch):
    class FakeSfn:
        def __init__(self):
            self.stopped = []

        def start_execution(self, **kwargs):
            return {"executionArn": "arn:aws:states:region:account:execution:test:one"}

        def stop_execution(self, **kwargs):
            self.stopped.append(kwargs)

    fake_table = LifecycleTable(fail_update_number=2)
    fake_sfn = FakeSfn()
    monkeypatch.setattr(handler, "table", fake_table)
    monkeypatch.setattr(handler, "sfn", fake_sfn)

    with pytest.raises(RuntimeError, match="DynamoDB failure"):
        handler.start_experiment(
            "exp_test",
            {"as_of_date": "2026-05-10", "duration_days": 7},
            caller_site="site_a",
        )

    assert fake_sfn.stopped[0]["executionArn"].endswith(":one")
    assert len(fake_table.updates) == 3
    assert ":draft" in fake_table.updates[2]["ExpressionAttributeValues"]


def test_start_defaults_to_live_waiting_mode_and_enables_allocation(monkeypatch):
    class CapturingSfn:
        def __init__(self):
            self.started = None

        def start_execution(self, **kwargs):
            self.started = kwargs
            return {
                "executionArn": (
                    "arn:aws:states:region:account:execution:test:live"
                )
            }

    fake_table = LifecycleTable()
    fake_sfn = CapturingSfn()
    monkeypatch.setattr(handler, "table", fake_table)
    monkeypatch.setattr(handler, "sfn", fake_sfn)

    response = handler.start_experiment(
        "exp_test",
        {"duration_days": 7},
        caller_site="site_a",
    )

    assert response["statusCode"] == 200
    values = fake_table.updates[0]["ExpressionAttributeValues"]
    assert values[":mode"] == "live"
    assert values[":enabled"] is True
    execution_input = json.loads(fake_sfn.started["input"])
    assert execution_input["execution_mode"] == "live"
    assert execution_input["planned_end_at"].endswith("Z")
    assert len(execution_input["check_dates"]) == 7


def test_manual_stop_halts_execution_before_marking_terminal(monkeypatch):
    order = []

    class FakeSfn:
        class exceptions:
            ExecutionDoesNotExist = ExecutionDoesNotExist

        def stop_execution(self, **kwargs):
            order.append("stop_execution")

    fake_table = LifecycleTable(
        item={
            "experiment_id": "exp_test",
            "client_site_id": "site_a",
            "state": "running",
            "execution_arn": "arn:aws:states:region:account:execution:test:one",
        },
        order=order,
    )
    monkeypatch.setattr(handler, "table", fake_table)
    monkeypatch.setattr(handler, "sfn", FakeSfn())

    response = handler.stop_experiment(
        "exp_test",
        {"final_state": "stopped_early", "reason": "operator decision"},
        caller_site="site_a",
    )

    assert response["statusCode"] == 200
    assert order[:2] == ["stop_execution", "table_update"]
    assert "allocation_enabled = :disabled" in fake_table.updates[0]["UpdateExpression"]
    assert fake_table.updates[0]["ExpressionAttributeValues"][":disabled"] is False


class ExposureTable:
    name = "test-exposures"

    def __init__(self, existing=None):
        self.existing = existing

    def get_item(self, **kwargs):
        return {"Item": self.existing} if self.existing else {}


class ExposureExperimentTable:
    name = "test-experiments"

    def __init__(self, item):
        self.item = item

    def get_item(self, **kwargs):
        return {"Item": self.item}


class TransactionClient:
    def __init__(self):
        self.calls = []

    def transact_write_items(self, **kwargs):
        self.calls.append(kwargs)


def running_experiment(allocation_enabled=True):
    return {
        "experiment_id": "exp_test",
        "client_site_id": "site_a",
        "game_id": "game_123",
        "state": "running",
        "allocation_enabled": allocation_enabled,
        "assignment_seed": Decimal("12345"),
        "variants": [
            {"name": "control", "weight": Decimal("0.5")},
            {"name": "treatment", "weight": Decimal("0.5")},
        ],
    }


def test_product_exposure_is_deterministic_and_atomically_guarded(monkeypatch):
    transaction = TransactionClient()
    monkeypatch.setattr(handler, "table", ExposureExperimentTable(running_experiment()))
    monkeypatch.setattr(handler, "exposures_table", ExposureTable())
    monkeypatch.setattr(handler, "dynamodb_client", transaction)

    response = handler.record_exposure(
        "exp_test",
        {"event_id": "evt-001", "player_id": "player_123"},
        caller_site="site_a",
    )
    body = json.loads(response["body"])

    assert response["statusCode"] == 201
    assert body["decision"] == "EXPOSE"
    assert body["variant"] == handler._assign_variant(
        "exp_test",
        12345,
        "player_123",
        running_experiment()["variants"],
    )
    assert len(transaction.calls) == 1
    condition = transaction.calls[0]["TransactItems"][0]["ConditionCheck"]
    assert "allocation_enabled = :enabled" in condition["ConditionExpression"]


def test_kill_switch_returns_control_decision_without_writing(monkeypatch):
    transaction = TransactionClient()
    monkeypatch.setattr(
        handler,
        "table",
        ExposureExperimentTable(running_experiment(allocation_enabled=False)),
    )
    monkeypatch.setattr(handler, "exposures_table", ExposureTable())
    monkeypatch.setattr(handler, "dynamodb_client", transaction)

    response = handler.record_exposure(
        "exp_test",
        {"event_id": "evt-002", "player_id": "player_123"},
        caller_site="site_a",
    )
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body == {
        "decision": "DO_NOT_EXPOSE",
        "experiment_id": "exp_test",
        "fallback_variant": "control",
        "recorded": False,
        "reason": "allocation_kill_switch_disabled",
        "experiment_state": "running",
    }
    assert transaction.calls == []


def test_exposure_event_id_is_idempotent(monkeypatch):
    existing = {
        "experiment_id": "exp_test",
        "event_id": "evt-003",
        "player_id": "player_123",
        "variant": "treatment",
        "exposed_at": "2026-07-29T00:00:00Z",
    }
    transaction = TransactionClient()
    monkeypatch.setattr(handler, "table", ExposureExperimentTable(running_experiment()))
    monkeypatch.setattr(handler, "exposures_table", ExposureTable(existing))
    monkeypatch.setattr(handler, "dynamodb_client", transaction)

    response = handler.record_exposure(
        "exp_test",
        {"event_id": "evt-003", "player_id": "player_123"},
        caller_site="site_a",
    )
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["idempotent_replay"] is True
    assert body["variant"] == "treatment"
    assert transaction.calls == []
