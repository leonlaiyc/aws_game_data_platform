"""Runs both batch detectors against the scripted ground-truth scenarios
already embedded in the simulated data (see
data-foundation/event_simulator/config.py and scenario_manifest.json):

1. Anomaly detector against site_b's scripted retention/revenue drop
   (starts 2026-06-10) - should fire a DAU deviation alert.
2. Arbitrage detector against site_a's scripted 6-account device-sharing
   ring (active through 2026-06-05) - should flag all 6 ring players.

Requires: AuroraGamesAnomalyStack deployed, and the lake/feature_registry
already built (data-foundation/lake/build_lake.py +
feature_registry/build_feature_registry.py) so the scripted scenarios are
present in gold_daily_kpi/gold_player_features/silver_events.
"""
import argparse
import json
import sys

import boto3

STACK_NAME = "AuroraGamesAnomalyStack"

session = boto3.Session()
cfn = session.client("cloudformation")
lambda_client = session.client("lambda")
s3 = session.client("s3")


def stack_outputs(stack_name: str) -> dict:
    resp = cfn.describe_stacks(StackName=stack_name)
    return {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0]["Outputs"]}


def invoke(function_name: str, payload: dict) -> dict:
    resp = lambda_client.invoke(FunctionName=function_name, Payload=json.dumps(payload).encode("utf-8"))
    body = json.loads(resp["Payload"].read())
    if "FunctionError" in resp:
        raise RuntimeError(f"{function_name} failed: {body}")
    return body


def section(title: str):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def run_anomaly(outputs: dict, failures: list):
    section("1. Anomaly detection: site_b's scripted retention/revenue drop")
    result = invoke(outputs["AnomalyDetectorFunctionName"], {"client_site_id": "site_b", "as_of_date": "2026-06-10"})
    print(json.dumps(result, indent=2))
    alert_metrics = {alert["metric"] for alert in result.get("alerts", [])}
    if "dau" in alert_metrics:
        print("\n-> Fired. SNS alert + gold/anomaly_alerts/site_b_2026-06-10.json written.")
    else:
        failures.append(f"expected a DAU alert, got metrics {sorted(alert_metrics)}")
        print("\n-> No alert fired (unexpected - check the lake was rebuilt with the scripted scenario intact).")


def run_arbitrage(outputs: dict, failures: list):
    section("2. Arbitrage detection: site_a's scripted 6-account device-sharing ring")
    result = invoke(outputs["ArbitrageDetectorFunctionName"], {"client_site_id": "site_a", "as_of_date": "2026-06-05"})
    flagged = result["flagged_players"]
    print(f"Flagged {len(flagged)} player(s):")
    for p in flagged:
        print(f"\n  {p['player_id']}  status={p.get('status')}  review_score={p.get('review_score')}")
        print(f"    detector={p.get('detector_id')}@{p.get('detector_version')}")
        print(f"    linked_players={p.get('linked_player_ids')}")
        for reason in p.get("reason_codes", []):
            peer = (
                f", peer_p99={reason['peer_p99']}"
                if reason.get("peer_p99") is not None else ""
            )
            print(
                f"    - {reason['code']}: actual={reason['actual']}, "
                f"threshold={reason['threshold']}, contribution={reason['contribution']}{peer}"
            )
    expected_ring = {f"p_ring_{i:02d}" for i in range(6)}
    actual = {p["player_id"] for p in flagged}
    explanations_complete = all(
        p.get("status") == "REVIEW_REQUIRED"
        and p.get("reason_codes")
        and p.get("detector_version")
        and p.get("linked_player_ids")
        for p in flagged
    )
    if actual == expected_ring and explanations_complete:
        print(f"\n-> PASS: expected exactly {sorted(expected_ring)}")
        print("-> EXPLANATION CONTRACT: PASS")
        print("-> AWS EVIDENCE: gold/flagged_players/site_a_2026-06-05.json")
    else:
        if actual != expected_ring:
            failures.append(
                f"arbitrage ring mismatch: expected {sorted(expected_ring)}, got {sorted(actual)}"
            )
        if not explanations_complete:
            failures.append("one or more findings did not satisfy the explanation contract")
        print(f"\n-> MISMATCH: expected exactly {sorted(expected_ring)}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run deterministic Module 1 AWS demos.")
    parser.add_argument(
        "--scenario",
        choices=["all", "anomaly", "arbitrage"],
        default="all",
        help="Run one short operation demo, or both (default).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = stack_outputs(STACK_NAME)
    failures = []

    print(f"PRECHECK: PASS (stack={STACK_NAME}, scenario={args.scenario})")
    if args.scenario in ("all", "anomaly"):
        run_anomaly(outputs, failures)
    if args.scenario in ("all", "arbitrage"):
        run_arbitrage(outputs, failures)

    section("Result")
    if failures:
        print(f"FAILED ({len(failures)}):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"RESULT: PASS ({args.scenario})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
