"""Code-owned first-look diagnostic queries shared by alert and on-demand paths."""

from athena_utils import fetch_all_rows, run_athena_query

BASELINE_WINDOW_DAYS = 7
SITE_METRICS = [
    "dau",
    "ggr_usd",
    "sessions",
    "new_players",
    "deposits_usd",
    "withdrawals_usd",
]
HOURLY_METRICS = ["active_users", "sessions", "processed_events"]


def authorised_scope_cumulative_comparison(sites: list[str]) -> dict:
    """Aggregate the latest common hourly cutoff across authorised sites.

    Values and 30-day same-cutoff baselines are already prepared per site in
    Gold. Summing those site-local figures preserves tenant scope and avoids
    recomputing historical windows in the request path.
    """
    quoted_sites = ", ".join(f"'{site}'" for site in sites)
    rows = fetch_all_rows(run_athena_query(f"""
        WITH latest AS (
            SELECT MAX(event_hour) AS event_hour
            FROM gold_hourly_monitoring_features
            WHERE client_site_id IN ({quoted_sites})
        )
        SELECT
            CAST(feature.event_hour AS VARCHAR) AS event_hour,
            SUM(active_users) AS active_users,
            SUM(active_users_baseline) AS active_users_baseline,
            SUM(sessions) AS sessions,
            SUM(sessions_baseline) AS sessions_baseline,
            SUM(processed_events) AS processed_events,
            SUM(processed_events_baseline) AS processed_events_baseline,
            MIN(baseline_points) AS baseline_points
        FROM gold_hourly_monitoring_features feature
        JOIN latest ON feature.event_hour = latest.event_hour
        WHERE client_site_id IN ({quoted_sites})
        GROUP BY feature.event_hour
    """))
    if not rows:
        return {}
    row = rows[0]
    comparison = {}
    for metric in HOURLY_METRICS:
        actual = float(row[metric])
        baseline = float(row[f"{metric}_baseline"])
        comparison[metric] = {
            "actual": round(actual, 4),
            "baseline_avg_30d": round(baseline, 4),
            "pct_change": (
                round((actual - baseline) / baseline * 100, 2)
                if baseline else None
            ),
        }
    return {
        "event_hour": row["event_hour"],
        "baseline_points": int(row["baseline_points"]),
        "comparison": comparison,
    }


def hourly_baseline_comparison(site: str, event_hour: str) -> dict:
    """Read detector-ready evidence; no baseline is recomputed here."""
    rows = fetch_all_rows(run_athena_query(f"""
        SELECT *
        FROM gold_hourly_monitoring_features
        WHERE client_site_id = '{site}'
          AND event_hour = TIMESTAMP '{event_hour}'
        LIMIT 1
    """))
    if not rows:
        return {}
    row = rows[0]
    comparison = {}
    for metric in HOURLY_METRICS:
        actual = float(row[metric])
        baseline = float(row[f"{metric}_baseline"])
        comparison[metric] = {
            "actual": round(actual, 4),
            "baseline": round(baseline, 4),
            "lower_bound": round(float(row[f"{metric}_lower_bound"]), 4),
            "upper_bound": round(float(row[f"{metric}_upper_bound"]), 4),
            "pct_change": (
                round((actual - baseline) / baseline * 100, 2)
                if baseline else None
            ),
        }
    return comparison


def site_baseline_comparison(site: str, as_of_date: str) -> dict:
    sql = f"""
    SELECT dt, dau, ggr_usd, sessions, new_players, deposits_usd, withdrawals_usd
    FROM gold_daily_kpi
    WHERE client_site_id = '{site}' AND dt <= '{as_of_date}'
    ORDER BY dt DESC
    LIMIT {BASELINE_WINDOW_DAYS + 1}
    """
    rows = fetch_all_rows(run_athena_query(sql))
    if not rows or rows[0]["dt"] != as_of_date:
        return {}
    today, history = rows[0], rows[1:]
    comparison = {}
    for metric in SITE_METRICS:
        today_val = float(today[metric])
        hist_vals = [
            float(row[metric])
            for row in history
            if row.get(metric) is not None
        ]
        baseline_avg = sum(hist_vals) / len(hist_vals) if hist_vals else None
        pct_change = (
            ((today_val - baseline_avg) / baseline_avg * 100)
            if baseline_avg
            else None
        )
        comparison[metric] = {
            "actual": round(today_val, 4),
            "baseline_avg_7d": (
                round(baseline_avg, 4) if baseline_avg is not None else None
            ),
            "pct_change": (
                round(pct_change, 2) if pct_change is not None else None
            ),
        }
    return comparison


def game_breakdown(site: str, as_of_date: str) -> list:
    sql = f"""
    WITH today AS (
        SELECT game_id, SUM(bet_amount_usd) - SUM(win_amount_usd) AS ggr_usd
        FROM silver_events
        WHERE client_site_id = '{site}' AND event_type = 'bet_settled'
          AND dt = '{as_of_date}'
        GROUP BY game_id
    ),
    baseline AS (
        SELECT game_id,
               (SUM(bet_amount_usd) - SUM(win_amount_usd))
                   / {BASELINE_WINDOW_DAYS}.0 AS ggr_usd_avg
        FROM silver_events
        WHERE client_site_id = '{site}' AND event_type = 'bet_settled'
          AND dt BETWEEN
              CAST(date_add('day', -{BASELINE_WINDOW_DAYS}, DATE '{as_of_date}')
                   AS VARCHAR)
              AND CAST(date_add('day', -1, DATE '{as_of_date}') AS VARCHAR)
        GROUP BY game_id
    )
    SELECT COALESCE(t.game_id, b.game_id) AS game_id,
           COALESCE(t.ggr_usd, 0.0) AS ggr_usd_today,
           COALESCE(b.ggr_usd_avg, 0.0) AS ggr_usd_baseline_avg
    FROM today t FULL OUTER JOIN baseline b ON t.game_id = b.game_id
    """
    rows = fetch_all_rows(run_athena_query(sql))
    breakdown = []
    for row in rows:
        today_value = float(row["ggr_usd_today"])
        baseline_value = float(row["ggr_usd_baseline_avg"])
        pct_change = (
            ((today_value - baseline_value) / baseline_value * 100)
            if baseline_value
            else None
        )
        breakdown.append(
            {
                "game_id": row["game_id"],
                "ggr_usd_today": round(today_value, 2),
                "ggr_usd_baseline_avg": round(baseline_value, 2),
                "pct_change": (
                    round(pct_change, 2)
                    if pct_change is not None
                    else None
                ),
            }
        )
    breakdown.sort(
        key=lambda game: (
            game["pct_change"] is None,
            game["pct_change"],
        )
    )
    return breakdown


def render_report(
    site: str,
    as_of_date: str,
    comparison: dict,
    breakdown: list,
    headline: str,
) -> str:
    def pct(value) -> str:
        if value is None:
            return "n/a"
        return f"{'+' if value >= 0 else ''}{value}%"

    comp_lines = "\n".join(
        f"- {metric}: {value['actual']} vs 7d baseline avg "
        f"{value['baseline_avg_7d']} ({pct(value['pct_change'])})"
        for metric, value in comparison.items()
    )
    game_lines = "\n".join(
        f"- {game['game_id']}: {game['ggr_usd_today']} vs baseline avg "
        f"{game['ggr_usd_baseline_avg']} ({pct(game['pct_change'])})"
        for game in breakdown
    )
    dau_change = comparison.get("dau", {}).get("pct_change") or 0
    ggr_change = comparison.get("ggr_usd", {}).get("pct_change") or 0
    co_movement = (
        "DAU and GGR moved in the same direction - consistent with a broad "
        "usage change."
        if (dau_change < -5 and ggr_change < -5)
        or (dau_change > 5 and ggr_change > 5)
        else "GGR moved without a matching DAU shift - may be narrower than "
        "an overall usage change (e.g. a payout/game-math issue) rather than "
        "fewer people playing."
    )

    return (
        f"### First-Look Report: {site} on {as_of_date}\n\n"
        f"### Headline\n{headline}\n\n"
        f"### Site-Level vs 7-Day Baseline\n{comp_lines}\n\n"
        f"### Per-Game GGR Breakdown (vs 7-day baseline avg)\n"
        f"{game_lines}\n\n"
        f"### Co-Movement Check\n{co_movement}\n\n"
        f"### Suggested Next Steps\n"
        f"- Confirm whether this is isolated to the worst-performing game(s) "
        f"above or platform-wide.\n"
        f"- Check for a known deploy/incident on {as_of_date} for {site}.\n"
        f"- If deposits also dropped, prioritize checking the payment "
        f"provider integration."
    )
