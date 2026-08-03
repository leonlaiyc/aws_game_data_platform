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
import time
import uuid
from datetime import date
from decimal import Decimal

import boto3
import diagnostics
from athena_utils import fetch_all_rows, run_athena_query
from templates import (
    KPI_DEFINITIONS_VERSION,
    SITE_REGIONS,
    TEMPLATES,
    VALID_CLIENT_SITES,
    VALID_GAMES,
)

bedrock = boto3.client("bedrock-runtime")
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
MODEL_ID = "amazon.nova-lite-v1:0"
GUARDRAIL_ID = os.environ["GUARDRAIL_ID"]
GUARDRAIL_VERSION = os.environ["GUARDRAIL_VERSION"]
AS_OF_DATE = os.environ["AS_OF_DATE"]           # this project's data is a fixed historical simulation, not live
DATA_MIN_DATE = os.environ["DATA_MIN_DATE"]
DATA_MAX_DATE = os.environ["DATA_MAX_DATE"]
REPLAY_EVENT_HOUR = os.environ.get("REPLAY_EVENT_HOUR", "")
BUSINESS_TIMEZONE_OFFSET_HOURS = int(
    os.environ.get("BUSINESS_TIMEZONE_OFFSET_HOURS", "0")
)
LAKE_BUCKET_NAME = os.environ.get("LAKE_BUCKET_NAME", "")
ANALYTICS_TICKETS_TABLE_NAME = os.environ.get(
    "ANALYTICS_TICKETS_TABLE_NAME", ""
)
analytics_tickets = (
    dynamodb.Table(ANALYTICS_TICKETS_TABLE_NAME)
    if ANALYTICS_TICKETS_TABLE_NAME
    else None
)
ANOMALY_INCIDENTS_TABLE_NAME = os.environ.get(
    "ANOMALY_INCIDENTS_TABLE_NAME", ""
)
anomaly_incidents = (
    dynamodb.Table(ANOMALY_INCIDENTS_TABLE_NAME)
    if ANOMALY_INCIDENTS_TABLE_NAME
    else None
)
PUBLICATION_MANIFEST_KEY = "manifests/published/gold_daily_kpi.json"
# Exact IAM role name treated as the internal operator (unrestricted). Empty
# means "nobody" - the safe default.
OPERATOR_PRINCIPAL_PATTERN = os.environ.get("OPERATOR_PRINCIPAL_PATTERN", "")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _data_window() -> dict:
    """Use the transform's completion marker, never a hard-coded notion of
    today or an unsafe MAX(dt) over a table that may still be publishing."""
    if not LAKE_BUCKET_NAME:
        return {
            "published_from": DATA_MIN_DATE,
            "published_through": DATA_MAX_DATE,
            "published_at": None,
            "source": "environment_fallback",
        }
    obj = s3.get_object(
        Bucket=LAKE_BUCKET_NAME, Key=PUBLICATION_MANIFEST_KEY
    )
    manifest = json.loads(obj["Body"].read())
    if (
        manifest.get("table") != "gold_daily_kpi"
        or not manifest.get("published_through")
        or not manifest.get("published_at")
    ):
        raise ValueError("gold_daily_kpi publication manifest is incomplete")
    return {
        "published_from": manifest.get("published_from", DATA_MIN_DATE),
        "published_through": manifest["published_through"],
        "published_at": manifest["published_at"],
        "source": "publication_manifest",
    }


def _build_system_prompt(data_window: dict | None = None) -> str:
    # Deliberately kept out of the "user" turn and passed via converse()'s
    # `system` param instead: Bedrock Guardrails' PROMPT_ATTACK filter scans
    # user-turn content for injected instructions, and a dense instructional
    # block (the classic injection shape) sitting in the user turn was
    # tripping it against our OWN trusted prompt. Splitting system
    # instructions from user-supplied content is also just the correct
    # architecture, not merely a guardrail workaround.
    data_window = data_window or {
        "published_from": DATA_MIN_DATE,
        "published_through": DATA_MAX_DATE,
    }
    metric_lines = "\n".join(f"- {key}: {t['label']} - {t['description']}" for key, t in TEMPLATES.items())
    return f"""You are classifying a business question about Aurora Games' gaming analytics
platform, for a semantic layer that only ever runs pre-approved SQL templates - you do not write
SQL, and you never state a numeric answer yourself.

Available metrics:
{metric_lines}

Available client sites and region mapping: {SITE_REGIONS}
Available games: {", ".join(VALID_GAMES)}
Reference "today" date is the latest complete publication: {data_window["published_through"]}
Data available from {data_window["published_from"]} to {data_window["published_through"]}

Classify the user's question and respond with ONLY a JSON object, no markdown fences:
{{"category": "answerable" | "diagnose" | "out_of_scope" | "needs_clarification" | "no_template_match",
  "metric": one of [{", ".join(f'"{k}"' for k in TEMPLATES)}] or null,
  "client_site_id": one of ["site_a", "site_b", "site_c"] or null,
  "game_id": one of [{", ".join(f'"{game}"' for game in VALID_GAMES)}] or null,
  "start_date": "YYYY-MM-DD" or null,
  "end_date": "YYYY-MM-DD" or null,
  "clarification_question": "..." or null,
  "reasoning": "one short sentence, for an internal audit log only"}}

Rules:
- "out_of_scope": the question isn't about any game analytics metric at all.
- "needs_clarification": the metric is identifiable but the site or date range is missing or
  ambiguous - ask exactly one targeted clarifying question.
- "no_template_match": clearly an analytics question, but not one of the metrics listed above.
- "diagnose": the user asks WHY a recent KPI dropped, whether a site/game has a problem, or asks
  for a first-look investigation. Resolve end_date. client_site_id may be null; null means aggregate
  every site permitted by the authenticated identity. metric and game_id may also be null.
- "answerable": ONLY when metric, client_site_id, start_date, and end_date are ALL confidently
  determined. game_id is optional; extract it when the question names a game. Interpret relative
  time expressions (e.g. "last week") relative to the reference date.
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


def _validate_slots(
    parsed: dict, data_window: dict | None = None
) -> dict:
    """Defensive re-validation of model-extracted slots before they ever
    reach a SQL string - never trust the model's raw output directly,
    even though the prompt already constrains it to a closed set."""
    if parsed.get("category") == "diagnose":
        site = parsed.get("client_site_id")
        as_of_date = parsed.get("end_date")
        game_id = parsed.get("game_id")
        if (
            (site is not None and site not in VALID_CLIENT_SITES)
            or not (as_of_date and _DATE_RE.match(as_of_date))
            or (game_id is not None and game_id not in VALID_GAMES)
        ):
            return {
                **parsed,
                "category": "needs_clarification",
                "clarification_question": (
                    "Which date should I investigate?"
                ),
                "reasoning": (
                    "diagnostic request needs one complete date and an optional whitelisted site"
                ),
            }
        window = data_window or {
            "published_from": DATA_MIN_DATE,
            "published_through": DATA_MAX_DATE,
        }
        try:
            requested_date = date.fromisoformat(as_of_date)
            min_date = date.fromisoformat(window["published_from"])
            max_date = date.fromisoformat(window["published_through"])
        except (TypeError, ValueError):
            requested_date = None
        if (
            requested_date is None
            or not min_date <= requested_date <= max_date
        ):
            return {
                **parsed,
                "category": "needs_clarification",
                "clarification_question": (
                    f"Complete data is available from {window['published_from']} "
                    f"to {window['published_through']}. Which date inside that "
                    "window should I investigate?"
                ),
                "reasoning": "diagnostic date is outside the complete publication",
            }
        return parsed
    if parsed.get("category") != "answerable":
        return parsed
    metric, site = parsed.get("metric"), parsed.get("client_site_id")
    start, end = parsed.get("start_date"), parsed.get("end_date")
    game_id = parsed.get("game_id")
    if (metric not in TEMPLATES or site not in VALID_CLIENT_SITES
            or (game_id is not None and game_id not in VALID_GAMES)
            or not (start and _DATE_RE.match(start)) or not (end and _DATE_RE.match(end))):
        return {**parsed, "category": "needs_clarification",
                "clarification_question": "I couldn't confidently pin down the metric, site, and date range - "
                                           "could you specify all three (e.g. \"GGR for site_a in the last week\")?",
                "reasoning": "post-parse validation rejected a slot value outside the known whitelist"}
    window = data_window or {
        "published_from": DATA_MIN_DATE,
        "published_through": DATA_MAX_DATE,
    }
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        min_date = date.fromisoformat(window["published_from"])
        max_date = date.fromisoformat(window["published_through"])
    except (TypeError, ValueError):
        return {
            **parsed,
            "category": "needs_clarification",
            "clarification_question": "Please provide a valid date range.",
            "reasoning": "date parsing failed after slot extraction",
        }
    if not (min_date <= start_date <= end_date <= max_date):
        return {
            **parsed,
            "category": "needs_clarification",
            "clarification_question": (
                f"Complete data is available from {min_date} to {max_date}. "
                "Which range inside that window should I use?"
            ),
            "reasoning": "requested range falls outside the complete publication",
        }
    if game_id and "game_sql" not in TEMPLATES[metric]:
        return {
            **parsed,
            "category": "needs_clarification",
            "clarification_question": (
                "Retention is defined at client-site cohort level in this "
                "semantic layer. Should I answer without a game filter?"
            ),
            "reasoning": "selected KPI has no governed per-game definition",
        }
    return parsed


def _run_template(
    metric: str, site: str, start: str, end: str, game_id: str | None = None
) -> dict:
    template = TEMPLATES[metric]
    template_key = "game_sql" if game_id else "sql"
    sql = template[template_key].format(
        client_site_id=site,
        game_id=game_id,
        start_date=start,
        end_date=end,
    )
    rows = fetch_all_rows(run_athena_query(sql))
    value = float(rows[0]["value"]) if rows and rows[0].get("value") is not None else None
    return {
        "value": round(value, 4) if value is not None else None,
        "label": template["label"],
        "unit": template["unit"],
        "source_table": (
            template["game_source_table"]
            if game_id
            else template["source_table"]
        ),
        "kpi_definition_anchor": template["kpi_definition_anchor"],
        "game_id": game_id,
    }


def _audit_log(question: str, parsed: dict, extra: dict = None):
    # Not user-facing - this is the trail a real threshold/prompt would be
    # tuned from, per the same principle recorded for Module 4.
    print(json.dumps({"audit": True, "question": question, "parsed": parsed, **(extra or {})}))


def _run_diagnosis(site: str, as_of_date: str) -> dict:
    """Run the existing first-look logic without a second model invocation."""
    comparison = diagnostics.site_baseline_comparison(site, as_of_date)
    if not comparison:
        return {"report_text": None, "comparison": {}, "game_breakdown": []}
    breakdown = diagnostics.game_breakdown(site, as_of_date)
    headline = (
        "On-demand first-look requested - review the code-rendered breakdown "
        "below."
    )
    return {
        "report_text": diagnostics.render_report(
            site,
            as_of_date,
            comparison,
            breakdown,
            headline,
        ),
        "comparison": comparison,
        "game_breakdown": breakdown,
    }


def _automation_outcome(category: str) -> dict:
    """Stable fields for low-cost Logs Insights measurement.

    These deliberately do not call a category ratio "deflection": only
    persisted user feedback or downstream case outcomes can prove that.
    """
    return {
        "measurement_event": "analytics_self_service_outcome",
        "automation_outcome": {
            "answerable": "answer_delivered",
            "diagnosis": "diagnosis_delivered",
            "needs_clarification": "clarification_requested",
            "no_template_match": "human_ticket_or_no_data",
            "scope_blocked": "scope_refused",
            "out_of_scope": "out_of_scope_refused",
            "blocked": "guardrail_blocked",
            "forecast_not_supported": "forecast_boundary_explained",
        }.get(category, "unknown"),
        "requires_human": category == "no_template_match",
    }


_FORECAST_RE = re.compile(
    r"(明天|未來|下週|下个月|下個月).*(回來|恢復|回升|成長|多少|會不會|是否)|"
    r"(will|forecast|predict).*(tomorrow|next|recover)",
    re.IGNORECASE,
)
_USAGE_DROP_RE = re.compile(
    r"(今天|今日).*(人數|使用者|活躍).*(為何|为什么|為什麼|怎麼|怎么|突然|掉|下降)|"
    r"why.*(active users|usage).*(drop|down)",
    re.IGNORECASE,
)


def _is_forecast_question(question: str) -> bool:
    return bool(_FORECAST_RE.search(question))


def _is_usage_drop_question(question: str) -> bool:
    return bool(_USAGE_DROP_RE.search(question))


def _latest_incident(sites: list[str]) -> dict | None:
    if anomaly_incidents is None:
        return None
    items = anomaly_incidents.scan(Limit=100).get("Items", [])
    eligible = [item for item in items if item.get("client_site_id") in sites]
    return max(eligible, key=lambda item: item.get("detected_at", ""), default=None)


def _clock_label(event_hour: str) -> str:
    match = re.search(r"[T ](\d{2}):(\d{2})", event_hour or "")
    if not match:
        return event_hour or "最新完整時段"
    hour = (int(match.group(1)) + BUSINESS_TIMEZONE_OFFSET_HOURS) % 24
    minute = match.group(2)
    period = "上午" if hour < 12 else "下午"
    display_hour = hour if 1 <= hour <= 12 else (12 if hour in {0, 12} else hour - 12)
    return f"{period} {display_hour}:{minute}"


def _business_usage_diagnosis(caller_scope: list | None) -> dict:
    sites = sorted(caller_scope or VALID_CLIENT_SITES)
    evidence = (
        diagnostics.authorised_scope_cumulative_comparison(
            sites, REPLAY_EVENT_HOUR
        )
        if REPLAY_EVENT_HOUR
        else diagnostics.authorised_scope_cumulative_comparison(sites)
    )
    comparison = evidence.get("comparison", {}).get("active_users", {})
    if not comparison or evidence.get("baseline_points", 0) < 30:
        return {
            "category": "no_template_match",
            "answer": "目前沒有足夠的 30 天完整資料，因此無法提供可靠比較。",
        }

    actual = round(comparison["actual"])
    baseline = round(comparison["baseline_avg_30d"])
    pct_drop = abs(comparison.get("pct_change") or 0)
    cutoff = _clock_label(evidence["event_hour"])
    incident = _latest_incident(sites)
    incident_sentence = "目前尚未產生對應告警，系統會在下一次排程繼續檢查。"
    if incident:
        status = incident.get("status")
        status_text = {
            "DETECTED": "發出告警，等待負責人開始排查",
            "INVESTIGATING": "發出告警，目前技術人員正在排查中",
            "RESOLVED": "發出告警，目前已標記為處理完成",
        }.get(status, "發出告警")
        incident_sentence = (
            f"異常監控系統已於{_clock_label(incident.get('event_hour', ''))} {status_text}。"
        )

    scope_label = "你有權限查看的所有站點"
    answer = (
        f"今天截至{cutoff}，{scope_label}共有 {actual:,} 位活躍使用者；"
        f"過去 30 天截至相同時間平均約有 {baseline:,} 位，目前少了約 {pct_drop:.0f}%。\n\n"
        f"{incident_sentence}原因尚未確認。"
    )
    return {
        "category": "diagnosis",
        "answer": answer,
        "scope": {"mode": "all_authorised_sites", "sites": sites},
        "query_evidence": evidence,
        "incident": incident,
    }


class ScopeResolutionError(Exception):
    """Raised when an authenticated caller cannot be mapped to a tenant."""


_ANALYST_ROLE_RE = re.compile(r"aurora-games-analyst-(site_[a-z0-9_]+)")


def _role_name(user_arn: str) -> str:
    resource = user_arn.split(":", 5)[-1] if ":" in user_arn else ""
    if resource.startswith("assumed-role/"):
        parts = resource.split("/", 2)
        return parts[1] if len(parts) >= 2 else ""
    if resource.startswith("role/"):
        return resource.rsplit("/", 1)[-1]
    return ""


def _caller_scope(event) -> list:
    """Tenant scope is derived from the authenticated IAM identity and from
    nothing else.

    **Gotcha worth stating explicitly:** the obvious place to put a scope like
    this is the request body, and it reads perfectly well in code - the
    comparison against the requested site is a real check. It just isn't a
    control, because the value being checked came from the caller. Anything
    that decides what a caller may see has to come from what authenticated
    them.

    Fails **closed**: an identity mapping to neither an analyst role nor an
    allow-listed operator principal is refused rather than quietly granted
    everything. Mapping by role-name convention is a demo simplification - a
    real deployment would carry the tenant in a verified IdP claim rather than
    inferring it from an ARN.
    """
    arn = (event.get("requestContext", {}).get("identity", {}) or {}).get("userArn") or ""
    role_name = _role_name(arn)
    match = _ANALYST_ROLE_RE.fullmatch(role_name)
    if match and match.group(1) in VALID_CLIENT_SITES:
        return [match.group(1)]
    if OPERATOR_PRINCIPAL_PATTERN and role_name == OPERATOR_PRINCIPAL_PATTERN:
        return None  # internal operator: every site
    raise ScopeResolutionError(f"caller identity is not mapped to any tenant scope: {arn or '<none>'}")


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _response(result: dict, status: int = 200) -> dict:
    # API Gateway's LambdaIntegration defaults to proxy mode, which requires
    # this exact statusCode/body envelope rather than a raw application dict.
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result, default=_json_default),
    }


def _persist_analytics_ticket(
    ticket_id: str,
    question: str,
    parsed: dict,
    caller_scope: list | None,
) -> None:
    if analytics_tickets is None:
        raise RuntimeError("ANALYTICS_TICKETS_TABLE_NAME is not configured")
    analytics_tickets.put_item(
        Item={
            "ticket_id": ticket_id,
            "status": "OPEN",
            "created_at_epoch": int(time.time()),
            "expires_at": int(time.time()) + 90 * 86400,
            "question": question,
            "requested_metric": parsed.get("metric"),
            "requested_site": parsed.get("client_site_id"),
            "requested_game": parsed.get("game_id"),
            "caller_scope": caller_scope or ["all_sites_operator"],
            "classification_reason": parsed.get("reasoning"),
        },
        ConditionExpression="attribute_not_exists(ticket_id)",
    )


def handler(event, context):
    try:
        body = (
            json.loads(event["body"])
            if isinstance(event.get("body"), str)
            else (event.get("body") or event)
        )
    except (json.JSONDecodeError, TypeError):
        body = None
    if not isinstance(body, dict):
        return _response({"error": "request body must be a JSON object"}, 400)
    question = body.get("question")
    if (
        not isinstance(question, str)
        or not question.strip()
        or len(question) > 2000
    ):
        return _response(
            {"error": "question must be a non-empty string of at most 2000 characters"},
            400,
        )

    try:
        caller_scope = _caller_scope(event)
    except ScopeResolutionError as e:
        _audit_log(
            question,
            {"category": "scope_unresolved"},
            {
                "reason": str(e),
                "final_category": "scope_blocked",
                **_automation_outcome("scope_blocked"),
            },
        )
        return _response(
            {"category": "scope_blocked",
             "answer": "Your credentials are not associated with a client site."},
            status=403,
        )

    # These two high-value business questions have deterministic outcomes.
    # They do not need a model to decide whether forecasting exists or to
    # rewrite code-owned numbers into a technical incident report.
    if _is_forecast_question(question):
        result = {
            "category": "forecast_not_supported",
            "answer": (
                "目前系統可以分析已發生的數據變化，但尚未建立並驗證人數預測模型，"
                "因此無法判定明天是否會恢復。"
            ),
        }
        _audit_log(
            question,
            {"category": "forecast_not_supported"},
            {"caller_scope": caller_scope, **_automation_outcome(result["category"])},
        )
        return _response(result)

    if _is_usage_drop_question(question):
        result = _business_usage_diagnosis(caller_scope)
        _audit_log(
            question,
            {"category": "diagnose", "scope_mode": "all_authorised_sites"},
            {
                "caller_scope": caller_scope,
                "final_category": result["category"],
                **_automation_outcome(result["category"]),
            },
        )
        return _response(result)

    data_window = _data_window()
    resp = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": _build_system_prompt(data_window)}],
        messages=[{"role": "user", "content": [{"text": question}]}],
        inferenceConfig={"maxTokens": 400, "temperature": 0.1},
        guardrailConfig={"guardrailIdentifier": GUARDRAIL_ID, "guardrailVersion": GUARDRAIL_VERSION, "trace": "enabled"},
    )

    if resp.get("stopReason") == "guardrail_intervened":
        _audit_log(
            question,
            {"category": "blocked"},
            {
                "guardrail_trace": resp.get("trace"),
                "final_category": "blocked",
                **_automation_outcome("blocked"),
            },
        )
        return _response({
            "category": "blocked",
            "answer": "This assistant only helps with Aurora Games analytics questions and can't process this request.",
        })

    parsed = _validate_slots(
        _parse_llm_json(resp["output"]["message"]["content"][0]["text"]),
        data_window,
    )
    category = parsed.get("category")

    if (
        category in {"answerable", "diagnose"}
        and caller_scope
        and parsed.get("client_site_id") is not None
        and parsed["client_site_id"] not in caller_scope
    ):
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
        _persist_analytics_ticket(
            ticket_id, question, parsed, caller_scope
        )
        result = {"category": category, "ticket_id": ticket_id,
                  "answer": f"That's a great analytics question, but it's outside what I can answer directly today. "
                             f"I've routed it to our analytics team - ticket {ticket_id}."}
    elif category == "diagnose":
        if parsed.get("client_site_id") is None:
            result = _business_usage_diagnosis(caller_scope)
            _audit_log(
                question,
                parsed,
                {
                    "caller_scope": caller_scope,
                    "final_category": result["category"],
                    **_automation_outcome(result["category"]),
                },
            )
            return _response(result)
        diagnosis = _run_diagnosis(
            parsed["client_site_id"],
            parsed["end_date"],
        )
        if diagnosis["report_text"] is None:
            result = {
                "category": "no_template_match",
                "answer": (
                    "There is no complete data for that site and date, so I "
                    "can't produce a grounded diagnosis."
                ),
            }
        else:
            result = {
                "category": "diagnosis",
                "answer": diagnosis["report_text"],
                "source_footer": (
                    "Sources: gold_daily_kpi and governed silver_events; "
                    f"published through {data_window['published_through']}."
                ),
                "query_evidence": {
                    "client_site_id": parsed["client_site_id"],
                    "game_id_requested": parsed.get("game_id"),
                    "as_of_date": parsed["end_date"],
                    "comparison": diagnosis["comparison"],
                    "game_breakdown": diagnosis["game_breakdown"],
                    "publication": data_window,
                },
            }
    else:  # answerable
        r = _run_template(
            parsed["metric"],
            parsed["client_site_id"],
            parsed["start_date"],
            parsed["end_date"],
            parsed.get("game_id"),
        )
        if r["value"] is None:
            result = {"category": "no_template_match",
                      "answer": "I found the right metric, but there's no data for that exact site/date range."}
        else:
            game_dimension = f" / {r['game_id']}" if r["game_id"] else ""
            result = {
                "category": "answerable",
                "answer": f"{r['label']} for {parsed['client_site_id']} from {parsed['start_date']} to "
                          f"{parsed['end_date']}{game_dimension}: "
                          f"{r['value']} {r['unit']}.",
                "source_footer": f"Source: {r['source_table']} "
                                 f"(KPI_DEFINITIONS.md {KPI_DEFINITIONS_VERSION}#{r['kpi_definition_anchor']}), "
                                 f"published through {data_window['published_through']}.",
                "query_evidence": {
                    "metric": parsed["metric"],
                    "client_site_id": parsed["client_site_id"],
                    "game_id": r["game_id"],
                    "start_date": parsed["start_date"],
                    "end_date": parsed["end_date"],
                    "source_table": r["source_table"],
                    "publication": data_window,
                },
            }

    _audit_log(
        question,
        parsed,
        {
            "caller_scope": caller_scope,
            "final_category": result["category"],
            **_automation_outcome(result["category"]),
        },
    )
    return _response(result)
