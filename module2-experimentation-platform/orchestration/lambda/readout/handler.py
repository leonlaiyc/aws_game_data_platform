"""Step 5: Bedrock (Nova Lite) generates a structured report draft, grounded
in the analysis step's numbers - the prompt supplies the exact figures and
instructs the model to use only those, and a lightweight post-generation
check flags any number in the output that isn't one of the supplied values
(not a full NLI-grade grounding verifier, just a cheap regex sanity check -
documented as a known limitation).
"""
import os
import re

import boto3
from dynamo_utils import now_iso, to_decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["EXPERIMENTS_TABLE_NAME"])
bedrock = boto3.client("bedrock-runtime")
MODEL_ID = "amazon.nova-lite-v1:0"
SIGNIFICANCE_ALPHA = 0.05

# List-marker digits ("1.", "2.", ...) in the requested 4-section report
# format are not analysis figures and would otherwise false-positive as
# "invented numbers".
_IGNORED_SMALL_INTS = {"1", "2", "3", "4"}


def _build_prompt(experiment: dict, analysis_result: dict) -> str:
    guardrail_lines = "\n".join(
        f"- {g['metric']}: treatment value {g['treatment_mean']} vs {g['direction']} threshold {g['threshold']} -> {g['status']}"
        for g in analysis_result["guardrail_status"]
    ) or "(none defined)"

    return f"""You are writing an internal experiment readout for a B2B gaming analytics team.
Use ONLY the numbers given below. Do not invent, estimate, or reformat any figure not listed here.

Experiment: {experiment['name']}
OEC metric: {analysis_result['oec_metric']}
Control group: n={analysis_result['control_n']}, mean={analysis_result['control_mean']}
Treatment group: n={analysis_result['treatment_n']}, mean={analysis_result['treatment_mean']}
Lift: {analysis_result['lift_pct']}%
Statistical significance: p-value={analysis_result['p_value']} ({'significant' if analysis_result['significant'] else 'not significant'} at alpha={SIGNIFICANCE_ALPHA})

Guardrail metrics:
{guardrail_lines}

Write a short report with exactly these 4 sections:
1. Conclusion (1-2 sentences)
2. Key stats (restate the numbers above)
3. Guardrail status
4. Next-round recommendation

Every number you write must be one of the numbers given above, unchanged."""


# Scientific notation (e.g. Python's str(1e-06) == "1e-06") must match as one
# token - without the optional exponent group, "1e-06" splits into "1" and
# "-06", and "-06" isn't a real figure, just a regex parsing artifact.
_NUMBER_RE = r"-?\b\d+\.?\d*(?:[eE][+-]?\d+)?\b"


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
    # A digit that's part of the experiment's own name (e.g. an internal
    # "-2" suffix) is an identifier echoed back, not an invented figure.
    allowed |= set(re.findall(_NUMBER_RE, experiment.get("name", "")))
    return allowed


def _grounding_check(report_text: str, experiment: dict, analysis_result: dict) -> tuple:
    allowed = _allowed_numbers(experiment, analysis_result)
    # \b boundaries matter here: metric names like "ggr_usd_7d" contain a
    # literal digit that isn't a figure the model reported - "_" is a \w
    # character in regex, so there's no boundary between it and the "7",
    # and an unanchored digit match would wrongly flag it as invented.
    found = re.findall(_NUMBER_RE, report_text)
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
        inferenceConfig={"maxTokens": 500, "temperature": 0.1},
    )
    report_text = resp["output"]["message"]["content"][0]["text"]
    grounding_ok, suspicious = _grounding_check(report_text, experiment, analysis_result)

    readout = {
        "report_text": report_text,
        "grounding_check_passed": grounding_ok,
        "suspicious_numbers": suspicious,
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
