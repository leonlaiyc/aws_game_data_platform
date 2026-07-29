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


def main() -> int:
    outputs = stack_outputs(STACK_NAME)
    failures = []

    section("1. Anomaly detection: site_b's scripted retention/revenue drop")
    result = invoke(outputs["AnomalyDetectorFunctionName"], {"client_site_id": "site_b", "as_of_date": "2026-06-10"})
    print(json.dumps(result, indent=2))
    if result["alerts"]:
        print("\n-> Fired. SNS alert + gold/anomaly_alerts/site_b_2026-06-10.json written.")
    else:
        print("\n-> No alert fired (unexpected - check the lake was rebuilt with the scripted scenario intact).")

    section("2. Arbitrage detection: site_a's scripted 6-account device-sharing ring")
    result = invoke(outputs["ArbitrageDetectorFunctionName"], {"client_site_id": "site_a", "as_of_date": "2026-06-05"})
    flagged = result["flagged_players"]
    print(f"Flagged {len(flagged)} player(s):")
    for p in flagged:
        print(f"  - {p['player_id']}: shared devices {p['shared_device_ids']}, "
              f"withdrawal_to_deposit_ratio_7d={p['withdrawal_to_deposit_ratio_7d']}")
    expected_ring = {f"p_ring_{i:02d}" for i in range(6)}
    actual = {p["player_id"] for p in flagged}
    print(f"\n-> {'PASS' if actual == expected_ring else 'MISMATCH'}: expected exactly {sorted(expected_ring)}")


if __name__ == "__main__":
    sys.exit(main())
