"""Runs 3 concurrent demo experiments end to end:

1. clean_winner       - site_a/game_01: treatment gets a real, injected bet
                        volume boost -> should finish with a significant,
                        positive, grounded readout.
2. guardrail_breach   - site_c/game_02: treatment gets injected heavy-loss
                        events -> should auto-stop early via the guardrail
                        monitor, with an SNS alert.
3. srm_violation      - site_b: no data injection; this script instead
                        creates/deletes draft experiments (cheap, no Athena
                        calls) until the REAL, unmodified hash-based
                        assignment happens to produce a skewed split for a
                        small population - demonstrating the SRM check
                        catches a genuinely bad randomization, not a staged
                        one.

Requires: infra deployed, data-foundation lake + feature_registry +
orchestration Athena tables already built at least once (this script
rebuilds silver_events and gold_player_features itself after injecting
demo data, so a prior full build isn't strictly required, but the base
bronze events from event_simulator.cli must already exist in S3).
"""
import random
import subprocess
import sys
import time
from pathlib import Path

import demo_lib as lib

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_FOUNDATION_VENV = REPO_ROOT / "data-foundation" / ".venv" / "Scripts" / "python.exe"
BUILD_LAKE = REPO_ROOT / "data-foundation" / "lake" / "build_lake.py"
BUILD_FEATURES = REPO_ROOT / "module2-experimentation-platform" / "feature_registry" / "build_feature_registry.py"

AS_OF_DATE = "2026-05-10"
DURATION_DAYS = 10
CHECK_DATES = [f"2026-05-{d:02d}" for d in range(11, 11 + DURATION_DAYS)]

SRM_AS_OF_DATE = "2026-05-05"
SRM_P_VALUE_THRESHOLD = 0.01


def section(title: str):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def chi2_p_value_df1(chi2: float) -> float:
    import math
    return math.erfc(math.sqrt(chi2 / 2))


def compute_split_p_value(experiment_id: str, seed: int, player_ids: list, variants: list) -> tuple:
    counts = {v["name"]: 0 for v in variants}
    for pid in player_ids:
        counts[lib.assign_variant(experiment_id, seed, pid, variants)] += 1
    total = len(player_ids)
    chi2 = 0.0
    for v in variants:
        observed = counts[v["name"]]
        expected = total * float(v["weight"])
        if expected > 0:
            chi2 += (observed - expected) ** 2 / expected
    return chi2_p_value_df1(chi2), counts


def find_srm_experiment(api_url: str, database: str, workgroup: str) -> str:
    section("Scenario 3 setup: hunting for a naturally skewed SRM split (site_b, small early population)")
    player_ids = lib.eligible_players(database, workgroup, "site_b", SRM_AS_OF_DATE)
    print(f"Eligible population for site_b on {SRM_AS_OF_DATE}: {len(player_ids)} players")

    variants = [{"name": "control", "weight": 0.5}, {"name": "treatment", "weight": 0.5}]
    for attempt in range(1, 501):
        resp = lib.api_request(api_url, "POST", "/experiments", {
            "name": "srm-violation-demo",
            "game_id": "game_03",
            "client_site_id": "site_b",
            "audience": {"client_site_id": "site_b"},
            "variants": variants,
            "oec_metric": "ggr_usd_7d",
            "guardrail_metrics": [],
        })
        experiment_id = resp["experiment_id"]
        seed = lib.derive_seed(experiment_id)
        p_value, counts = compute_split_p_value(experiment_id, seed, player_ids, variants)

        if p_value < SRM_P_VALUE_THRESHOLD:
            print(f"  attempt {attempt}: experiment_id={experiment_id} counts={counts} p_value={p_value:.6f} <- SKEWED, keeping this one")
            return experiment_id

        lib.api_request(api_url, "DELETE", f"/experiments/{experiment_id}")
        if attempt % 25 == 0:
            print(f"  attempt {attempt}: p_value={p_value:.4f} (not skewed enough), retrying...")

    raise RuntimeError("Could not find a skewed split after 500 attempts - population may be too large/stable")


def setup_data_experiment(api_url: str, name: str, game_id: str, client_site_id: str, guardrail_metrics: list) -> tuple:
    resp = lib.api_request(api_url, "POST", "/experiments", {
        "name": name,
        "game_id": game_id,
        "client_site_id": client_site_id,
        "audience": {"client_site_id": client_site_id},
        "variants": [{"name": "control", "weight": 0.5}, {"name": "treatment", "weight": 0.5}],
        "oec_metric": "ggr_usd_7d",
        "guardrail_metrics": guardrail_metrics,
    })
    experiment_id = resp["experiment_id"]
    return experiment_id, lib.derive_seed(experiment_id)


def inject_clean_winner_effect(bucket: str, database: str, workgroup: str, experiment_id: str, seed: int):
    section("Scenario 1 setup: injecting a real bet-volume boost for the treatment group (site_a/game_01)")
    player_ids = lib.eligible_players(database, workgroup, "site_a", AS_OF_DATE)
    treatment = [p for p in player_ids if lib.assign_variant(experiment_id, seed, p, [
        {"name": "control", "weight": 0.5}, {"name": "treatment", "weight": 0.5}]) == "treatment"]
    print(f"Eligible: {len(player_ids)}, treatment group: {len(treatment)}")

    rng = random.Random(f"clean_winner:{experiment_id}")
    for dt in CHECK_DATES:
        events = []
        for pid in treatment:
            bet = 15.0
            won = rng.random() < 0.40
            win = round(bet * 1.8, 2) if won else 0.0
            events.append(lib.make_bet_event("winner", pid, "site_a", "game_01", f"{dt}T12:00:00Z", bet, win))
        lib.inject_bronze_file(bucket, dt, "demo_clean_winner_boost", events)
    print(f"Injected {len(treatment)} extra bet_settled events/day across {len(CHECK_DATES)} days.")


def inject_guardrail_breach_effect(bucket: str, database: str, workgroup: str, experiment_id: str, seed: int):
    section("Scenario 2 setup: injecting heavy-loss events for the treatment group (site_c/game_02)")
    player_ids = lib.eligible_players(database, workgroup, "site_c", AS_OF_DATE)
    treatment = [p for p in player_ids if lib.assign_variant(experiment_id, seed, p, [
        {"name": "control", "weight": 0.5}, {"name": "treatment", "weight": 0.5}]) == "treatment"]
    print(f"Eligible: {len(player_ids)}, treatment group: {len(treatment)}")

    for dt in CHECK_DATES:
        events = [
            lib.make_bet_event("guardrail", pid, "site_c", "game_02", f"{dt}T12:00:00Z", 5.0, 100.0)
            for pid in treatment
        ]
        lib.inject_bronze_file(bucket, dt, "demo_guardrail_breach", events)
    print(f"Injected {len(treatment)} big-loss bet_settled events/day across {len(CHECK_DATES)} days.")


def rebuild_lake():
    section("Rebuilding silver_events / gold_daily_kpi / gold_cohort_retention / gold_player_features")
    subprocess.run([str(DATA_FOUNDATION_VENV), str(BUILD_LAKE)], check=True, cwd=str(BUILD_LAKE.parent))
    subprocess.run([str(DATA_FOUNDATION_VENV), str(BUILD_FEATURES)], check=True, cwd=str(BUILD_FEATURES.parent))


def start_experiment(api_url: str, experiment_id: str, as_of_date: str, duration_days: int):
    lib.api_request(api_url, "POST", f"/experiments/{experiment_id}/start", {
        "as_of_date": as_of_date, "duration_days": duration_days,
    })


def wait_for_completion(state_machine_arn: str, experiment_ids: list, timeout_seconds: int = 600):
    section("Waiting for all 3 Step Functions executions to finish")
    sfn = lib.session.client("stepfunctions")
    deadline = time.time() + timeout_seconds
    pending = set(experiment_ids)
    while pending and time.time() < deadline:
        running_names = [e["name"] for e in sfn.list_executions(
            stateMachineArn=state_machine_arn, statusFilter="RUNNING")["executions"]]
        for eid in list(pending):
            if not any(name.startswith(eid) for name in running_names):
                pending.discard(eid)
                print(f"  {eid}: finished")
        if pending:
            time.sleep(6)
    if pending:
        print(f"WARNING: still running after {timeout_seconds}s: {pending}")


def print_summary(api_url: str, experiment_id: str, label: str):
    section(f"Result: {label} ({experiment_id})")
    exp = lib.api_request(api_url, "GET", f"/experiments/{experiment_id}")
    print(f"state: {exp.get('state')}")
    if exp.get("stop_reason"):
        print(f"stop_reason: {exp['stop_reason']}")
    if exp.get("analysis_result"):
        ar = exp["analysis_result"]
        print(f"control: n={ar['control_n']} mean={ar['control_mean']}  treatment: n={ar['treatment_n']} mean={ar['treatment_mean']}")
        print(f"lift: {ar['lift_pct']}%  p_value: {ar['p_value']}  significant: {ar['significant']}")
        print(f"guardrail_status: {ar['guardrail_status']}")
    if exp.get("readout"):
        print(f"\n--- Bedrock readout (grounding_check_passed={exp['readout']['grounding_check_passed']}) ---")
        print(exp["readout"]["report_text"])


def main():
    foundation = lib.stack_outputs("AuroraGamesFoundationStack")
    registry = lib.stack_outputs("AuroraGamesRegistryStack")
    orchestration = lib.stack_outputs("AuroraGamesOrchestrationStack")
    bucket, database, workgroup = foundation["LakeBucketName"], foundation["GlueDatabaseName"], foundation["AthenaWorkgroupName"]
    api_url = registry["ExperimentsApiUrl"]
    state_machine_arn = orchestration["StateMachineArn"]

    section("Creating draft experiments")
    winner_id, winner_seed = setup_data_experiment(
        api_url, "payout-tweak-game01-clean-winner", "game_01", "site_a",
        [{"metric": "sessions_7d", "direction": "min", "threshold": 0}],
    )
    print(f"clean_winner: {winner_id} (seed={winner_seed})")

    breach_id, breach_seed = setup_data_experiment(
        api_url, "art-ux-change-game02-guardrail-test", "game_02", "site_c",
        [{"metric": "ggr_usd_7d", "direction": "min", "threshold": 0}],
    )
    print(f"guardrail_breach: {breach_id} (seed={breach_seed})")

    srm_id = find_srm_experiment(api_url, database, workgroup)
    print(f"srm_violation: {srm_id}")

    inject_clean_winner_effect(bucket, database, workgroup, winner_id, winner_seed)
    inject_guardrail_breach_effect(bucket, database, workgroup, breach_id, breach_seed)

    rebuild_lake()

    section("Starting all 3 experiments (concurrent Step Functions executions)")
    start_experiment(api_url, winner_id, AS_OF_DATE, DURATION_DAYS)
    start_experiment(api_url, breach_id, AS_OF_DATE, DURATION_DAYS)
    start_experiment(api_url, srm_id, SRM_AS_OF_DATE, 5)
    print("All 3 started.")
    time.sleep(5)  # let the executions register before polling for RUNNING status

    wait_for_completion(state_machine_arn, [winner_id, breach_id, srm_id])

    print_summary(api_url, winner_id, "Clean winner")
    print_summary(api_url, breach_id, "Guardrail auto-stop")
    print_summary(api_url, srm_id, "SRM violation")


if __name__ == "__main__":
    main()
