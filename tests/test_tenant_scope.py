"""Unit tests for Module 3's tenant-scope resolution.

The rule under test is that scope comes from the authenticated identity and
from nothing the caller can set. These run offline, so they catch a regression
at commit time rather than waiting for the deployed cross-tenant matrix in
module3-analytics-assistant/demo/run_demo.py to notice it.
"""
import os
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT, load_handler  # noqa: E402

MODULE3 = REPO_ROOT / "module3-analytics-assistant" / "lambda"
handler = load_handler(
    "m3_ask_answer_handler",
    MODULE3 / "ask_answer",
    extra_paths=[MODULE3 / "common" / "python"],
    env={"GUARDRAIL_ID": "test", "GUARDRAIL_VERSION": "1", "AS_OF_DATE": "2026-06-29",
         "DATA_MIN_DATE": "2026-05-01", "DATA_MAX_DATE": "2026-06-29",
         "GLUE_DATABASE_NAME": "aurora_games_lake",
         "ATHENA_WORKGROUP_NAME": "aurora-games-wg",
         "AWS_DEFAULT_REGION": "ap-northeast-1"},
)


def event_for(arn):
    return {"requestContext": {"identity": {"userArn": arn}}}


ANALYST = "arn:aws:sts::123456789012:assumed-role/aurora-games-analyst-{site}/session"
OPERATOR = "arn:aws:sts::123456789012:assumed-role/aurora-games-operator/session"


@pytest.mark.parametrize("site", ["site_a", "site_b", "site_c"])
def test_analyst_identity_maps_to_its_own_site(site):
    assert handler._caller_scope(event_for(ANALYST.format(site=site))) == [site]


def test_operator_identity_is_unrestricted(monkeypatch):
    monkeypatch.setattr(handler, "OPERATOR_PRINCIPAL_PATTERN", "aurora-games-operator")
    assert handler._caller_scope(event_for(OPERATOR)) is None


@pytest.mark.parametrize("arn", [
    "arn:aws:sts::123456789012:assumed-role/some-other-role/session",
    "arn:aws:iam::123456789012:user/random-person",
    "",
])
def test_unrecognised_identity_fails_closed(arn, monkeypatch):
    """An identity that maps to no tenant must be refused, not quietly granted
    everything. Fail-open here would mean any authenticated principal in the
    account reads every tenant's data."""
    monkeypatch.setattr(handler, "OPERATOR_PRINCIPAL_PATTERN", "aurora-games-operator")
    with pytest.raises(handler.ScopeResolutionError):
        handler._caller_scope(event_for(arn))


def test_missing_request_context_fails_closed(monkeypatch):
    monkeypatch.setattr(handler, "OPERATOR_PRINCIPAL_PATTERN", "aurora-games-operator")
    with pytest.raises(handler.ScopeResolutionError):
        handler._caller_scope({})


def test_empty_operator_pattern_grants_nobody_unrestricted_access(monkeypatch):
    monkeypatch.setattr(handler, "OPERATOR_PRINCIPAL_PATTERN", "")
    with pytest.raises(handler.ScopeResolutionError):
        handler._caller_scope(event_for(OPERATOR))


def test_request_body_cannot_influence_scope():
    """_caller_scope must read the request context and nothing else.

    Asserted against the parsed body of the function rather than its source
    text, so prose in the docstring (which discusses the request body) does not
    trip it. This documents the contract; the deployed cross-tenant matrix in
    module3-analytics-assistant/demo/run_demo.py is what proves it end to end.
    """
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(handler._caller_scope)))
    func = tree.body[0]
    if ast.get_docstring(func):
        func.body = func.body[1:]  # drop the docstring node

    literals = {node.value for node in ast.walk(ast.Module(body=func.body, type_ignores=[]))
                if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert not any("body" in s for s in literals), \
        f"_caller_scope references the request body: {literals}"
    assert any("requestContext" in s for s in literals), \
        "_caller_scope should read requestContext"


class TestSlotValidation:
    """Model-extracted slots are re-validated against a closed set before they
    are substituted into SQL, because the prompt constraining the model is not
    an input-validation boundary."""

    def test_valid_slots_pass_through(self):
        parsed = {"category": "answerable", "metric": "ggr", "client_site_id": "site_a",
                  "start_date": "2026-06-01", "end_date": "2026-06-07"}
        assert handler._validate_slots(parsed)["category"] == "answerable"

    @pytest.mark.parametrize("override", [
        {"client_site_id": "site_a' OR '1'='1"},
        {"client_site_id": "site_z"},
        {"metric": "DROP TABLE"},
        {"start_date": "2026-06-01'; DELETE FROM x--"},
        {"end_date": "not-a-date"},
        {"start_date": None},
    ])
    def test_out_of_whitelist_values_are_rejected(self, override):
        parsed = {"category": "answerable", "metric": "ggr", "client_site_id": "site_a",
                  "start_date": "2026-06-01", "end_date": "2026-06-07", **override}
        assert handler._validate_slots(parsed)["category"] == "needs_clarification"
