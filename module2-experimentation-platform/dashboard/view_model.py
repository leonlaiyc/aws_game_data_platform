"""Pure view-model helpers for the zero-hosting-cost local operations view."""

STATE_ORDER = {
    "running": 0,
    "draft": 1,
    "stopped_early": 2,
    "completed": 3,
    "analyzed": 4,
}


def _health(experiment: dict) -> tuple[str, str]:
    state = experiment.get("state", "unknown")
    monitoring = experiment.get("monitoring_status") or {}
    guardrail = monitoring.get("guardrails") or {}
    srm = monitoring.get("srm") or {}
    if state == "stopped_early":
        return "action", experiment.get("stop_reason", "stopped early")
    if state == "running" and experiment.get("allocation_enabled") is not True:
        return "action", "allocation kill switch is disabled"
    if guardrail.get("status") == "breached" or srm.get("status") == "breached":
        return "action", "monitoring breach"
    if state == "running" and srm.get("status") == "insufficient_sample":
        return "watch", (
            f"SRM waiting for sample ({srm.get('total_exposed', 0)}/"
            f"{srm.get('minimum_exposures', 100)})"
        )
    if state == "running":
        return "healthy", "running; allocation enabled"
    if state == "draft":
        return "neutral", "not started"
    return "neutral", state.replace("_", " ")


def build_view_model(experiments: list[dict]) -> dict:
    rows = []
    for experiment in experiments:
        health, health_detail = _health(experiment)
        monitoring = experiment.get("monitoring_status") or {}
        srm = monitoring.get("srm") or {}
        rows.append({
            "experiment_id": experiment.get("experiment_id"),
            "name": experiment.get("name"),
            "owner": experiment.get("owner", "unassigned"),
            "created_by": experiment.get("created_by"),
            "client_site_id": experiment.get("client_site_id"),
            "game_id": experiment.get("game_id"),
            "state": experiment.get("state", "unknown"),
            "health": health,
            "health_detail": health_detail,
            "allocation_enabled": experiment.get("allocation_enabled") is True,
            "execution_mode": experiment.get("execution_mode", "not_started"),
            "total_exposed": srm.get("total_exposed"),
            "srm_status": srm.get("status", "not_checked"),
            "last_checked_at": monitoring.get("checked_at"),
            "planned_end_at": experiment.get("planned_end_at"),
            "related_experiment_id": experiment.get("related_experiment_id"),
        })
    rows.sort(
        key=lambda row: (
            STATE_ORDER.get(row["state"], 99),
            row.get("client_site_id") or "",
            row.get("name") or "",
        )
    )
    return {
        "summary": {
            "total": len(rows),
            "running": sum(row["state"] == "running" for row in rows),
            "needs_action": sum(row["health"] == "action" for row in rows),
            "draft": sum(row["state"] == "draft" for row in rows),
        },
        "experiments": rows,
    }
