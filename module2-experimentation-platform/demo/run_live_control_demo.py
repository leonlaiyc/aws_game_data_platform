"""Exercise real product exposures, exposure SRM, and the allocation switch."""
import json
import sys
import time
from pathlib import Path

import boto3

import demo_lib as lib

AS_OF_DATE = "2026-06-29"


def main() -> int:
    registry = lib.stack_outputs("AuroraGamesRegistryStack")
    api_url = registry["ExperimentsApiUrl"]
    print("PRECHECK: PASS — registry stack and signed operator session resolved")

    experiment = lib.api_request(api_url, "POST", "/experiments", {
        "name": "live-exposure-srm-kill-switch-demo",
        "owner": "growth-experimentation",
        "game_id": "game_02",
        "client_site_id": "site_c",
        "audience": {"client_site_id": "site_c"},
        "variants": [
            {"name": "control", "weight": 0.5},
            {"name": "treatment", "weight": 0.5},
        ],
        "oec_metric": "ggr_usd_7d",
        "guardrail_metrics": [],
    })
    experiment_id = experiment["experiment_id"]
    started = lib.api_request(
        api_url,
        "POST",
        f"/experiments/{experiment_id}/start",
        {
            "mode": "live",
            "as_of_date": AS_OF_DATE,
            "duration_days": 1,
        },
    )
    seed = int(started["assignment_seed"])
    variants = started["variants"]
    print(f"LIVE: {experiment_id} allocation_enabled={started['allocation_enabled']}")

    # Construct a deterministic 99/1 unique-player split. This models a real
    # product integration bug that drops treatment exposures, not random
    # sampling noise or repeated impressions from one player.
    selected = {"control": [], "treatment": []}
    candidate = 0
    while len(selected["control"]) < 99 or len(selected["treatment"]) < 1:
        player_id = f"live_demo_player_{candidate:05d}"
        variant = lib.assign_variant(
            experiment_id, seed, player_id, variants
        )
        if variant == "control" and len(selected["control"]) < 99:
            selected["control"].append(player_id)
        elif variant == "treatment" and len(selected["treatment"]) < 1:
            selected["treatment"].append(player_id)
        candidate += 1

    players = selected["control"] + selected["treatment"]
    for index, player_id in enumerate(players, start=1):
        decision = lib.api_request(
            api_url,
            "POST",
            f"/experiments/{experiment_id}/exposures",
            {
                "event_id": f"live-demo-{experiment_id}-{index:03d}",
                "player_id": player_id,
            },
        )
        if decision.get("decision") != "EXPOSE":
            raise RuntimeError(f"exposure {index} was refused: {decision}")
        # Stay below the API's explicit 10 request/s paid-plan cost boundary.
        time.sleep(0.12)
    print("EXPOSURES: 100 accepted unique players (control=99, treatment=1)")

    resources = boto3.client("cloudformation").describe_stack_resources(
        StackName="AuroraGamesOrchestrationStack"
    )["StackResources"]
    monitoring_fn = next(
        resource["PhysicalResourceId"]
        for resource in resources
        if resource["LogicalResourceId"].startswith("MonitoringCheck")
        and resource["ResourceType"] == "AWS::Lambda::Function"
    )
    response = boto3.client("lambda").invoke(
        FunctionName=monitoring_fn,
        Payload=json.dumps({
            "experiment_id": experiment_id,
            "check_date": AS_OF_DATE,
            "guardrail_metrics": [],
        }).encode("utf-8"),
    )
    result = json.loads(response["Payload"].read())
    if response.get("FunctionError") or result.get("breach_type") != "exposure_srm":
        print(f"RESULT: FAIL — monitoring returned {result}")
        return 1
    print(
        "SRM: PASS — skew detected "
        f"observed={result['srm']['observed']} p={result['srm']['p_value']}"
    )

    stopped = lib.api_request(
        api_url, "GET", f"/experiments/{experiment_id}"
    )
    post_stop = lib.api_request(
        api_url,
        "POST",
        f"/experiments/{experiment_id}/exposures",
        {
            "event_id": f"live-demo-{experiment_id}-blocked",
            "player_id": "late_player",
        },
    )
    checks = {
        "state stopped_early": stopped.get("state") == "stopped_early",
        "allocation disabled": stopped.get("allocation_enabled") is False,
        "late decision control-only": (
            post_stop.get("decision") == "DO_NOT_EXPOSE"
            and post_stop.get("fallback_variant") == "control"
            and post_stop.get("recorded") is False
        ),
    }
    for label, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print(f"EVIDENCE: registry experiment {experiment_id}")
    print("GROSS COST: below $0.01 for 101 API calls and small DynamoDB items")
    if not all(checks.values()):
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
