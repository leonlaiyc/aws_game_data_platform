"""Capability A: ask-and-answer NL Q&A over the semantic layer.

NL question -> Bedrock (with Guardrails attached) parses intent into a
structured category + slots -> a matching SQL template is filled with
already-validated values and run via Athena -> the numeric answer is
rendered by CODE, not the LLM (same hardened pattern as Module 2's
readout: every figure in the response is code-rendered; the LLM's role
here is confined to intent parsing, never to restating or inventing a
number). No free-form text-to-SQL - see semantic_layer/templates.py.

Pipeline (first match wins):
1. Guardrails intervention (denied topics / prompt attack) -> BLOCKED
2. Cross-client scope violation (caller_scope set, requested site not in
   it) -> SCOPE_BLOCKED - a distinct category from "out of scope" because
   the question itself may be perfectly on-topic, it's just not this
   caller's data to see.
3. Model says the question isn't about our metrics at all -> OUT_OF_SCOPE
4. Model can't confidently resolve metric/site/date range -> NEEDS_CLARIFICATION
5. Model says it's clearly analytics-shaped but none of our templates
   cover it -> NO_TEMPLATE_MATCH -> analyst fallback + ticket stub
6. Otherwise -> ANSWERABLE -> run the template, render a grounded answer

Every response is logged in full (category, slots, raw model reasoning)
to CloudWatch Logs as an audit trail - not user-facing, but how a
threshold/classification decision here would actually get tuned in
production (see module4-fallback-handling-design threshold-handling note
in project memory for the same principle applied to Module 4).
"""
import json
import os
import re
import uuid

import boto3
from athena_utils import fetch_all_rows, run_athena_query
from templates import KPI_DEFINITIONS_VERSION, TEMPLATES, VALID_CLIENT_SITES

bedrock = boto3.client("bedrock-runtime")
MODEL_ID = "amazon.nova-lite-v1:0"
GUARDRAIL_ID = os.environ["GUARDRAIL_ID"]
GUARDRAIL_VERSION = os.environ["GUARDRAIL_VERSION"]
AS_OF_DATE = os.environ["AS_OF_DATE"]           # this project's data is a fixed historical simulation, not live
DATA_MIN_DATE = os.environ["DATA_MIN_DATE"]
DATA_MAX_DATE = os.environ["DATA_MAX_DATE"]
# Regex matching IAM principals treated as internal operators (unrestricted).
# Empty means "nobody" - the safe default, since a blank pattern must not
# accidentally match every ARN.
OPERATOR_PRINCIPAL_PATTERN = os.environ.get("OPERATOR_PRINCIPAL_PATTERN", "")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _build_system_prompt() -> str:
    # Deliberately kept out of the "user" turn and passed via converse()'s
    # `system` param instead: Bedrock Guardrails' PROMPT_ATTACK filter scans
    # user-turn content for injected instructions, and a dense instructional
    # block (the classic injection shape) sitting in the user turn was
    # tripping it against our OWN trusted prompt. Splitting system
    # instructions from user-supplied content is also just the correct
    # architecture, not merely a guardrail workaround.
    metric_lines = "\n".join(f"- {key}: {t['label']} - {t['description']}" for key, t in TEMPLATES.items())
    return f"""You are classifying a business question about Aurora Games' gaming analytics
platform, for a semantic layer that only ever runs pre-approved SQL templates - you do not write
SQL, and you never state a numeric answer yourself.

Available metrics:
{metric_lines}

Available client sites: {", ".join(VALID_CLIENT_SITES)}
Reference "today" date (this project's data is a fixed historical simulation, not live): {AS_OF_DATE}
Data available from {DATA_MIN_DATE} to {DATA_MAX_DATE}

Classify the user's question and respond with ONLY a JSON object, no markdown fences:
{{"category": "answerable" | "out_of_scope" | "needs_clarification" | "no_template_match",
  "metric": one of [{", ".join(f'"{k}"' for k in TEMPLATES)}] or null,
  "client_site_id": one of ["site_a", "site_b", "site_c"] or null,
  "start_date": "YYYY-MM-DD" or null,
  "end_date": "YYYY-MM-DD" or null,
  "clarification_question": "..." or null,
  "reasoning": "one short sentence, for an internal audit log only"}}

Rules:
- "out_of_scope": the question isn't about any game analytics metric at all.
- "needs_clarification": the metric is identifiable but the site or date range is missing or
  ambiguous - ask exactly one targeted clarifying question.
- "no_template_match": clearly an analytics question, but not one of the metrics listed above.
- "answerable": ONLY when metric, client_site_id, start_date, and end_date are ALL confidently
  determined. Interpret relative time expressions (e.g. "last week") relative to the reference date.
"""


def _parse_llm_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return {"category": "needs_clarification",
                "clarification_question": "Could you rephrase your question? I couldn't quite parse that.",
                "reasoning": f"LLM response was not valid JSON: {stripped[:200]}"}


def _validate_slots(parsed: dict) -> dict:
    """Defensive re-validation of model-extracted slots before they ever
    reach a SQL string - never trust the model's raw output directly,
    even though the prompt already constrains it to a closed set."""
    if parsed.get("category") != "answerable":
        return parsed
    metric, site = parsed.get("metric"), parsed.get("client_site_id")
    start, end = parsed.get("start_date"), parsed.get("end_date")
    if (metric not in TEMPLATES or site not in VALID_CLIENT_SITES
            or not (start and _DATE_RE.match(start)) or not (end and _DATE_RE.match(end))):
        return {**parsed, "category": "needs_clarification",
                "clarification_question": "I couldn't confidently pin down the metric, site, and date range - "
                                           "could you specify all three (e.g. \"GGR for site_a in the last week\")?",
                "reasoning": "post-parse validation rejected a slot value outside the known whitelist"}
    return parsed


def _run_template(metric: str, site: str, start: str, end: str) -> dict:
    template = TEMPLATES[metric]
    sql = template["sql"].format(client_site_id=site, start_date=start, end_date=end)
    rows = fetch_all_rows(run_athena_query(sql))
    value = float(rows[0]["value"]) if rows and rows[0].get("value") is not None else None
    return {
        "value": round(value, 4) if value is not None else None,
        "label": template["label"],
        "unit": template["unit"],
        "source_table": template["source_table"],
        "kpi_definition_anchor": template["kpi_definition_anchor"],
    }


def _audit_log(question: str, parsed: dict, extra: dict = None):
    # Not user-facing - this is the trail a real threshold/prompt would be
    # tuned from, per the same principle recorded for Module 4.
    print(json.dumps({"audit": True, "question": question, "parsed": parsed, **(extra or {})}))


class ScopeResolutionError(Exception):
    """Raised when an authenticated caller cannot be mapped to a tenant."""


_ANALYST_ROLE_RE = re.compile(r"aurora-games-analyst-(site_[a-z0-9_]+)")


def _caller_scope(event) -> list:
    """Tenant scope is derived from the authenticated IAM identity and from
    nothing else.

    It used to be read from the request body. With the API unauthenticated,
    that meant a caller could name any site - or omit the field entirely and be
    treated as unrestricted. The scope check was real; the input it checked was
    attacker-controlled, which makes the check decorative.

    Fails **closed**: an identity that maps to neither an analyst role nor an
    allow-listed operator principal is refused rather than quietly granted
    everything. Mapping by role-name convention is a demo simplification - a
    real deployment would carry the tenant in a verified IdP claim rather than
    inferring it from an ARN.
    """
    arn = (event.get("requestContext", {}).get("identity", {}) or {}).get("userArn") or ""
    match = _ANALYST_ROLE_RE.search(arn)
    if match:
        return [match.group(1)]
    if OPERATOR_PRINCIPAL_PATTERN and re.search(OPERATOR_PRINCIPAL_PATTERN, arn):
        return None  # internal operator: every site
    raise ScopeResolutionError(f"caller identity is not mapped to any tenant scope: {arn or '<none>'}")


def _response(result: dict, status: int = 200) -> dict:
    # API Gateway's LambdaIntegration defaults to proxy mode, which requires
    # this exact statusCode/body envelope rather than a raw application dict.
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(result)}


def handler(event, context):
    body = json.loads(event["body"]) if isinstance(event.get("body"), str) else (event.get("body") or event)
    question = body["question"]

    try:
        caller_scope = _caller_scope(event)
    except ScopeResolutionError as e:
        _audit_log(question, {"category": "scope_unresolved"}, {"reason": str(e)})
        return _response(
            {"category": "scope_blocked",
             "answer": "Your credentials are not associated with a client site."},
            status=403,
        )

    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": _build_system_prompt()}],
        messages=[{"role": "user", "content": [{"text": question}]}],
        inferenceConfig={"maxTokens": 400, "temperature": 0.1},
        guardrailConfig={"guardrailIdentifier": GUARDRAIL_ID, "guardrailVersion": GUARDRAIL_VERSION, "trace": "enabled"},
    )

    if resp.get("stopReason") == "guardrail_intervened":
        _audit_log(question, {"category": "blocked"}, {"guardrail_trace": resp.get("trace")})
        return _response({
            "category": "blocked",
            "answer": "This assistant only helps with Aurora Games analytics questions and can't process this request.",
        })

    parsed = _validate_slots(_parse_llm_json(resp["output"]["message"]["content"][0]["text"]))
    category = parsed.get("category")

    if category == "answerable" and caller_scope and parsed["client_site_id"] not in caller_scope:
        category = "scope_blocked"

    if category == "out_of_scope":
        result = {"category": category,
                  "answer": "I specialize in Aurora Games analytics questions (revenue, active users, retention). "
                            "I can't help with that, but I'm happy to help with any analytics question."}
    elif category == "scope_blocked":
        result = {"category": category,
                  "answer": "I can only answer questions about your own client site's data."}
    elif category == "needs_clarification":
        result = {"category": category, "answer": parsed.get("clarification_question")}
    elif category == "no_template_match":
        ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
        result = {"category": category, "ticket_id": ticket_id,
                  "answer": f"That's a great analytics question, but it's outside what I can answer directly today. "
                            f"I've routed it to our analytics team - ticket {ticket_id}."}
    else:  # answerable
        r = _run_template(parsed["metric"], parsed["client_site_id"], parsed["start_date"], parsed["end_date"])
        if r["value"] is None:
            result = {"category": "no_template_match",
                      "answer": "I found the right metric, but there's no data for that exact site/date range."}
        else:
            result = {
                "category": "answerable",
                "answer": f"{r['label']} for {parsed['client_site_id']} from {parsed['start_date']} to "
                          f"{parsed['end_date']}: {r['value']} {r['unit']}.",
                "source_footer": f"Source: {r['source_table']} "
                                 f"(KPI_DEFINITIONS.md {KPI_DEFINITIONS_VERSION}#{r['kpi_definition_anchor']}), "
                                 f"as of {AS_OF_DATE}.",
            }

    _audit_log(question, parsed, {"caller_scope": caller_scope, "final_category": result["category"]})
    return _response(result)
