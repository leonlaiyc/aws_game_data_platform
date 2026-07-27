"""Step 5: generates the experiment readout.

Every number in the final report is traceable to our own code, not to the
LLM - the report is assembled from two kinds of parts:

- "Key Stats" and "Guardrail Status" are rendered directly from
  analysis_result by _render_key_stats/_render_guardrail_status. Bedrock
  never sees these as something to reproduce; there is no way for it to
  get a figure here wrong, because it doesn't write these sections at all.
- "Conclusion" and "Next-round Recommendation" are the only LLM-authored
  parts (qualitative judgment - is this a good result? what should happen
  next?), and the prompt explicitly asks for a verdict in words, not a
  restatement of the figures.

This is a stronger guarantee than scanning the model's output for
numbers after the fact (the previous design): a number in "Key Stats"
can't be wrong because we wrote it ourselves, rather than checking
whether it happens to match something we allowed. The grounding check
below still runs - as a secondary safety net - on just the two
LLM-authored fields, in case the model ignores the instruction and
restates a figure anyway.
"""
import json
import os
import re

import boto3
from dynamo_utils import now_iso, to_decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["EXPERIMENTS_TABLE_NAME"])
bedrock = boto3.client("bedrock-runtime")
MODEL_ID = "amazon.nova-lite-v1:0"
SIGNIFICANCE_ALPHA = 0.05


def _build_prompt(experiment: dict, analysis_result: dict) -> str:
    guardrail_lines = "\n".join(
        f"- {g['metric']}: treatment value {g['treatment_mean']} vs {g['direction']} threshold {g['threshold']} -> {g['status']}"
        for g in analysis_result["guardrail_status"]
    ) or "(none defined)"
    significance = "significant" if analysis_result["significant"] else "not significant"

    return f"""You are writing the qualitative portions of an internal experiment readout for a
B2B gaming analytics team. The numeric results below are shown to you for context only - they
will be printed separately, verbatim, by our own reporting code. Do NOT restate exact figures
(no percentages, means, p-values, or counts) anywhere in your response - describe magnitude and
direction in words instead (e.g. "a large, statistically significant increase").

Experiment: {experiment['name']}
OEC metric: {analysis_result['oec_metric']}
Control: n={analysis_result['control_n']}, mean={analysis_result['control_mean']}
Treatment: n={analysis_result['treatment_n']}, mean={analysis_result['treatment_mean']}
Lift: {analysis_result['lift_pct']}%, {significance} at alpha={SIGNIFICANCE_ALPHA}
Guardrails:
{guardrail_lines}

Respond with ONLY a JSON object, no markdown fences, with exactly these two keys:
{{"conclusion": "1-2 sentences, qualitative judgment of the result",
  "recommendation": "1-2 sentences, what to do next round"}}"""


def _parse_llm_json(text: str) -> tuple:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()
    try:
        obj = json.loads(stripped)
        return obj.get("conclusion", "").strip(), obj.get("recommendation", "").strip(), True
    except (json.JSONDecodeError, AttributeError):
        return stripped, "", False


def _render_key_stats(analysis_result: dict) -> str:
    significance = "significant" if analysis_result["significant"] else "not significant"
    return (
        f"- Control group: n={analysis_result['control_n']}, mean={analysis_result['control_mean']}\n"
        f"- Treatment group: n={analysis_result['treatment_n']}, mean={analysis_result['treatment_mean']}\n"
        f"- Lift: {analysis_result['lift_pct']}%\n"
        f"- Statistical significance: p-value={analysis_result['p_value']} ({significance} at alpha={SIGNIFICANCE_ALPHA})"
    )


def _render_guardrail_status(analysis_result: dict) -> str:
    lines = [
        f"- {g['metric']}: treatment value {g['treatment_mean']} vs {g['direction']} threshold {g['threshold']} -> {g['status']}"
        for g in analysis_result["guardrail_status"]
    ]
    return "\n".join(lines) if lines else "(no guardrail metrics defined)"


# Scientific notation (e.g. Python's str(1e-06) == "1e-06") must match as one
# token - without the optional exponent group, "1e-06" splits into "1" and
# "-06", and "-06" isn't a real figure, just a regex parsing artifact.
_NUMBER_RE = r"-?\b\d+\.?\d*(?:[eE][+-]?\d+)?\b"
_IGNORED_SMALL_INTS = {"1", "2"}  # harmless if the model numbers its own sentences


def _allowed_numbers(experiment: dict, analysis_result: dict) -> set:
    values = [
        analysis_result["control_mean"], analysis_result["treatment_mean"],
        analysis_result["lift_pct"], analysis_result["p_value"],
        analysis_result["control_n"], analysis_result["treatment_n"],
        SIGNIFICANCE_ALPHA,
    ]
    for g in analysis_result["guardrail_status"]:
        values += [g["treatment_mean"], g["threshold"]]
    allowed = {str(v) for v in values if v is not None}
    allowed |= set(re.findall(_NUMBER_RE, experiment.get("name", "")))
    return allowed


def _grounding_check(llm_text: str, experiment: dict, analysis_result: dict) -> tuple:
    """Secondary safety net over the LLM-authored conclusion/recommendation
    only - Key Stats and Guardrail Status are code-rendered and don't need
    checking, they're correct by construction."""
    allowed = _allowed_numbers(experiment, analysis_result)
    found = re.findall(_NUMBER_RE, llm_text)
    suspicious = [n for n in found if n not in allowed and n not in _IGNORED_SMALL_INTS]
    return (len(suspicious) == 0), suspicious


def handler(event, context):
    experiment_id = event["experiment_id"]
    experiment = event["assignment"]["experiment"]
    analysis_result = event["analysis_result"]

    prompt = _build_prompt(experiment, analysis_result)
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0.1},
    )
    raw_text = resp["output"]["message"]["content"][0]["text"]
    conclusion, recommendation, parsed_ok = _parse_llm_json(raw_text)

    grounding_ok, suspicious = _grounding_check(conclusion + " " + recommendation, experiment, analysis_result)

    report_text = (
        f"### Conclusion\n{conclusion}\n\n"
        f"### Key Stats\n{_render_key_stats(analysis_result)}\n\n"
        f"### Guardrail Status\n{_render_guardrail_status(analysis_result)}\n\n"
        f"### Next-round Recommendation\n{recommendation}"
    )

    readout = {
        "report_text": report_text,
        "grounding_check_passed": grounding_ok,
        "suspicious_numbers": suspicious,
        "llm_response_parsed": parsed_ok,
        "generated_at": now_iso(),
        "model_id": MODEL_ID,
    }

    table.update_item(
        Key={"experiment_id": experiment_id},
        UpdateExpression="SET readout = :r, #state = :analyzed, analyzed_at = :now, updated_at = :now",
        ExpressionAttributeNames={"#state": "state"},
        ExpressionAttributeValues={":r": to_decimal(readout), ":analyzed": "analyzed", ":now": now_iso()},
    )

    return readout
