"""Runs three demo scenarios end to end; the first two execute concurrently:

1. clean_winner       - site_a/game_01: treatment gets a real, injected bet
                        volume boost -> should finish with a significant,
                        positive, grounded readout.
2. guardrail_breach   - site_c/game_02: treatment gets injected heavy-loss
                        events -> should auto-stop early via the guardrail
                        monitor, with an SNS alert.
3. srm_violation      - site_b: a deliberately broken randomizer whose split
                        logic disagrees with the experiment's declared 50/50
                        weights, producing a deterministic ~33/67 split. Fed
                        to the deployed SRM check, which rejects it.

                        The split is computed, not searched for: re-running
                        gives byte-identical counts. (Selecting experiments
                        until one happens to look skewed would demonstrate
                        multiple-comparisons cherry-picking rather than a
                        randomization bug - the opposite of the point.)

Requires: infra deployed, data-foundation lake + feature_registry +
orchestration Athena tables already built at least once (this script
rebuilds silver_events and gold_player_features itself after injecting
demo data, so a prior full build isn't strictly required, but the base
bronze events from event_simulator.cli must already exist in S3).
"""
import json
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

SRM_AS_OF_DATE = AS_OF_DATE
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


def buggy_assign_variant(_experiment_id: str, _seed: int, player_id: str, variants: list) -> str:
    """A deliberately broken randomizer, modelling a real and common class of
    assignment bug: **the split logic and the declared weights are maintained
    in two different places and have drifted apart.**

    The experiment config says 50/50. This stale assignment code ignores both
    the experiment and its seed, then says "treatment if the player hash is
    divisible by 3". That produces a stable ~33/67 split across every run.
    Nothing here is random or flaky - it is simply wrong, and wrong in a way
    that looks entirely reasonable in code review.

    That is what SRM is for: nobody notices the config and the code disagree,
    but the arrival counts do.
    """
    import hashlib
    digest = hashlib.md5(player_id.encode()).hexdigest()
    return variants[1]["name"] if int(digest, 16) % 3 == 0 else variants[0]["name"]


def setup_srm_experiment(api_url: str, database: str, workgroup: str) -> tuple:
    section("Scenario 3 setup: a genuinely broken randomizer (site_b)")
    player_ids = lib.eligible_players(database, workgroup, "site_b", SRM_AS_OF_DATE)
    print(f"Eligible population for site_b on {SRM_AS_OF_DATE}: {len(player_ids)} players")
    if len(player_ids) < 100:
        raise RuntimeError(
            "SRM demo requires at least 100 eligible players; rebuild the deterministic lake first"
        )

    variants = [{"name": "control", "weight": 0.5}, {"name": "treatment", "weight": 0.5}]
    resp = lib.api_request(api_url, "POST", "/experiments", {
        "name": "srm-violation-demo",
        "owner": "growth-experimentation",
        "game_id": "game_03",
        "client_site_id": "site_b",
        "audience": {"client_site_id": "site_b"},
        "variants": variants,
        "oec_metric": "ggr_usd_7d",
        "guardrail_metrics": [],
    })
    experiment_id = resp["experiment_id"]
    seed = lib.derive_seed(experiment_id)

    counts = {v["name"]: 0 for v in variants}
    for pid in player_ids:
        counts[buggy_assign_variant(experiment_id, seed, pid, variants)] += 1

    fair_p, fair_counts = compute_split_p_value(experiment_id, seed, player_ids, variants)
    print(f"  The platform's real randomizer would split : {fair_counts}  (p={fair_p:.4f}, passes SRM)")
    print(f"  This experiment's broken randomizer splits : {counts}       (declared 50/50)")
    print("  The split is deterministic - re-running produces exactly the same counts.")
    return experiment_id, seed, counts, len(player_ids), variants


def setup_data_experiment(api_url: str, name: str, game_id: str, client_site_id: str, guardrail_metrics: list) -> tuple:
    resp = lib.api_request(api_url, "POST", "/experiments", {
        "name": name,
        "owner": "growth-experimentation",
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
        # This scenario intentionally replays historical simulated days in a
        # few minutes. The default API mode is now live and waits in real
        # wall-clock time while accepting product exposure events.
        "mode": "replay",
        "as_of_date": as_of_date,
        "duration_days": duration_days,
    })


def wait_for_completion(state_machine_arn: str, experiment_ids: list, timeout_seconds: int = 600):
    section("Waiting for both Step Functions executions to finish")
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
        raise TimeoutError(f"still running after {timeout_seconds}s: {sorted(pending)}")


def print_summary(api_url: str, experiment_id: str, label: str) -> dict:
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
    return exp


def run_srm_check(experiment_id: str, counts: dict, total: int, variants: list):
    """Feeds the broken randomizer's output to the deployed SRM check.

    This scenario invokes the real srm_check Lambda directly rather than
    running the state machine, because the platform's own assignment step is
    not broken - it would produce a fair split and correctly pass. What is
    being demonstrated is the check's behaviour on a broken *upstream*, so the
    broken upstream is what gets supplied.

    The Choice state immediately after this step in the state machine branches
    on `passed`, so a false here is what halts an experiment before it can
    consume any analysis.
    """
    import boto3
    section("Result: SRM violation (broken randomizer caught)")
    fn = [r["PhysicalResourceId"] for r in boto3.client("cloudformation").describe_stack_resources(
        StackName="AuroraGamesOrchestrationStack")["StackResources"]
        if r["LogicalResourceId"].startswith("SrmCheck")][0]

    payload = {"assignment": {"experiment": {"experiment_id": experiment_id, "variants": variants},
                               "variant_counts": counts, "total_assigned": total}}
    resp = boto3.client("lambda").invoke(
        FunctionName=fn, Payload=json.dumps(payload).encode("utf-8"))
    result = json.loads(resp["Payload"].read())

    expected = {v["name"]: round(total * float(v["weight"]), 1) for v in variants}
    print(f"observed: {counts}")
    print(f"expected: {expected}   (from the declared 50/50 weights)")
    print(f"chi2={result['chi2']}  p_value={result['p_value']}  threshold={result['threshold']}")
    print(f"passed={result['passed']}")
    if result["passed"]:
        raise SystemExit("FAIL: SRM check passed a deterministically skewed split")
    print("\n-> PASS: the experiment is halted before analysis. Nothing downstream "
          "sees a comparison built on a broken split.")


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

    srm_id, srm_seed, srm_counts, srm_total, srm_variants = setup_srm_experiment(
        api_url, database, workgroup)
    print(f"srm_violation: {srm_id}")

    inject_clean_winner_effect(bucket, database, workgroup, winner_id, winner_seed)
    inject_guardrail_breach_effect(bucket, database, workgroup, breach_id, breach_seed)

    rebuild_lake()

    section("Starting the 2 data-driven experiments (concurrent Step Functions executions)")
    start_experiment(api_url, winner_id, AS_OF_DATE, DURATION_DAYS)
    start_experiment(api_url, breach_id, AS_OF_DATE, DURATION_DAYS)
    print("Both started.")
    time.sleep(5)  # let the executions register before polling for RUNNING status

    wait_for_completion(state_machine_arn, [winner_id, breach_id])

    winner = print_summary(api_url, winner_id, "Clean winner")
    breach = print_summary(api_url, breach_id, "Guardrail auto-stop")

    failures = []
    analysis = winner.get("analysis_result") or {}
    if winner.get("state") != "analyzed":
        failures.append(f"clean winner state expected analyzed, got {winner.get('state')}")
    if not analysis.get("significant") or (analysis.get("lift_pct") or 0) <= 0:
        failures.append(
            "clean winner did not produce a significant positive treatment effect"
        )
    if not winner.get("readout", {}).get("report_text"):
        failures.append("clean winner produced no experiment readout")

    if not str(breach.get("stop_reason", "")).startswith("guardrail_breach:"):
        failures.append(
            f"guardrail experiment has no guardrail_breach stop_reason: {breach.get('stop_reason')!r}"
        )
    if breach.get("state") != "stopped_early":
        failures.append(
            f"guardrail experiment expected stopped_early, got {breach.get('state')!r}"
        )
    if breach.get("analysis_result") or breach.get("readout"):
        failures.append("guardrail experiment continued into analysis/readout after stopping")

    run_srm_check(srm_id, srm_counts, srm_total, srm_variants)

    if failures:
        section("FAILED")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    section("Result")
    print("All three experiment scenarios passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
