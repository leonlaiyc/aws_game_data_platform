"""Step 5: generates the experiment readout.

Every number in the final report is traceable to our own code, not to the
LLM - the report is assembled from three kinds of parts:

- "Key Stats", "Guardrail Status", and "Caveats" are rendered directly
  from analysis_result by _render_key_stats/_render_guardrail_status/
  _render_caveats. Bedrock never sees these as something to reproduce;
  there is no way for it to get a figure here wrong, because it doesn't
  write these sections at all. Caveats (analysis_result["flags"]) are
  themselves computed by deterministic rules in the analysis Lambda
  (imbalanced groups, tiny samples, a guardrail that passed but is close,
  a suspiciously large effect, wide uncertainty) - the same "code owns
  correctness" principle applied to what gets flagged, not just to the
  numbers.
- "Conclusion" and "Next-round Recommendation" are the only LLM-authored
  parts (qualitative judgment - is this a good result? what should happen
  next?). The prompt requires the Conclusion to address every flag - the
  LLM is not free to decide whether a caveat is worth mentioning, only
  how to phrase it. It still writes no numbers at all.

Division of labor: deterministic code owns everything requiring
correctness and auditability (the numbers, the significance decision, and
now the caveat triggers); the LLM is confined to what it's reliable at -
synthesis and audience-appropriate communication, weaving code-governed
facts into prose a decision-maker can read in seconds. This isn't
distrust of the LLM - it's placing it where it's reliable. An assistant
that also judges and reports numbers is one nobody dares use in a
high-trust setting, because one hallucination voids the whole report; an
assistant confined to trustworthy language synthesis is one that actually
gets used daily.

The grounding check below still runs as a secondary safety net on just
the LLM-authored fields, in case the model restates a figure anyway.
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
    flags = analysis_result.get("flags", [])

    if flags:
        flag_lines = "\n".join(f"- [{f['code']}] {f['message']}" for f in flags)
        flag_instruction = (
            "Your Conclusion MUST address every one of the following caveats, in your own words - "
            "you are not free to omit any of them, only to phrase them naturally:\n" + flag_lines
        )
    else:
        flag_instruction = "No caveats were raised for this result - you may note it was a clean read."

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

{flag_instruction}

Respond with ONLY a JSON object, no markdown fences, with exactly these two keys:
{{"conclusion": "2-4 sentences: qualitative judgment of the result, addressing every caveat listed above",
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


def _render_caveats(analysis_result: dict) -> str:
    flags = analysis_result.get("flags", [])
    if not flags:
        return "(none - no caveat rules were triggered for this result)"
    lines = []
    for f in flags:
        evidence = ", ".join(f"{k}={v}" for k, v in f["evidence"].items())
        lines.append(f"- [{f['code']}] ({f['severity']}) {evidence}")
    return "\n".join(lines)


# Scientific notation (e.g. Python's str(1e-06) == "1e-06") must match as one
# token - without the optional exponent group, "1e-06" splits into "1" and
# "-06", and "-06" isn't a real figure, just a regex parsing artifact.
_NUMBER_RE = r"-?\b\d+\.?\d*(?:[eE][+-]?\d+)?\b"
_IGNORED_SMALL_INTS = {"1", "2"}  # harmless if the model numbers its own sentences

# Coarse coverage heuristic (not literal keyword matching, which would be
# fragile against paraphrasing): expect roughly this many extra words per
# caveat the Conclusion is required to address.
_BASE_MIN_WORDS = 12
_WORDS_PER_FLAG = 10


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
    only - Key Stats, Guardrail Status, and Caveats are code-rendered and
    don't need checking, they're correct by construction."""
    allowed = _allowed_numbers(experiment, analysis_result)
    found = re.findall(_NUMBER_RE, llm_text)
    suspicious = [n for n in found if n not in allowed and n not in _IGNORED_SMALL_INTS]
    return (len(suspicious) == 0), suspicious


def _coverage_check(prompt: str, conclusion: str, flags: list) -> dict:
    """Two cheap, mechanical checks mirroring the numeric grounding guard,
    but for completeness rather than correctness:
    - flags_in_prompt: did our own code actually pass every flag to the
      model (a self-check against a silent bug dropping one, not a check
      on the LLM)?
    - conclusion_non_trivial: is the Conclusion long enough to plausibly
      have addressed all of them, given how many were required? This is a
      coarse word-count heuristic, not literal keyword matching (which
      would be fragile against paraphrasing) - it catches a degenerate
      one-line non-answer, not a subtly incomplete one.
    """
    flags_in_prompt = all(f["code"] in prompt for f in flags)
    min_words = _BASE_MIN_WORDS + _WORDS_PER_FLAG * len(flags)
    conclusion_non_trivial = len(conclusion.split()) >= min_words
    return {
        "flags_in_prompt": flags_in_prompt,
        "conclusion_word_count": len(conclusion.split()),
        "conclusion_min_words_expected": min_words,
        "conclusion_non_trivial": conclusion_non_trivial,
    }


def handler(event, context):
    experiment_id = event["experiment_id"]
    experiment = event["assignment"]["experiment"]
    analysis_result = event["analysis_result"]
    flags = analysis_result.get("flags", [])

    prompt = _build_prompt(experiment, analysis_result)
    resp = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 400, "temperature": 0.1},
    )
    raw_text = resp["output"]["message"]["content"][0]["text"]
    conclusion, recommendation, parsed_ok = _parse_llm_json(raw_text)

    grounding_ok, suspicious = _grounding_check(conclusion + " " + recommendation, experiment, analysis_result)
    coverage = _coverage_check(prompt, conclusion, flags)

    # The check has to be able to *reject*, not merely annotate.
    #
    # An earlier version recorded grounding_check_passed alongside the report
    # and published the report regardless - which means a readout containing a
    # number the model invented still reached the reader, carrying a flag
    # nobody downstream was obliged to look at. A check whose failure changes
    # nothing is documentation, not a control.
    #
    # On failure the LLM's prose is dropped entirely and the report falls back
    # to code-rendered sections only. That is strictly less readable and
    # strictly more trustworthy, which is the correct direction to fail in:
    # every number in Key Stats, Guardrail Status and Caveats is rendered from
    # the analysis result, so the fallback cannot contain an invented figure.
    llm_text_accepted = grounding_ok and parsed_ok

    if llm_text_accepted:
        conclusion_section = f"### Conclusion\n{conclusion}\n\n"
        recommendation_section = f"\n\n### Next-round Recommendation\n{recommendation}"
    else:
        reason = ("the grounding check found figures not present in the analysis result"
                  if not grounding_ok else "the model's response could not be parsed")
        conclusion_section = (
            f"### Conclusion\n_Narrative summary withheld: {reason}. "
            f"The code-rendered sections below are unaffected and complete._\n\n"
        )
        recommendation_section = ""

    report_text = (
        f"{conclusion_section}"
        f"### Key Stats\n{_render_key_stats(analysis_result)}\n\n"
        f"### Guardrail Status\n{_render_guardrail_status(analysis_result)}\n\n"
        f"### Caveats\n{_render_caveats(analysis_result)}"
        f"{recommendation_section}"
    )

    readout = {
        "report_text": report_text,
        "grounding_check_passed": grounding_ok,
        "llm_text_accepted": llm_text_accepted,
        "suspicious_numbers": suspicious,
        "llm_response_parsed": parsed_ok,
        "flags_count": len(flags),
        "coverage_check": coverage,
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
