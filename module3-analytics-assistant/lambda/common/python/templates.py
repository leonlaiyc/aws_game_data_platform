"""The semantic layer: a small, closed set of parameterized Athena SQL
templates, one per KPI_DEFINITIONS.md metric. This is the whole reason
Module 3 doesn't do free-form text-to-SQL - the LLM's job is to pick one
of these and fill in its parameters, never to write SQL itself. See
module3-analytics-assistant/README.md for the templates-vs-text-to-SQL
trade-off write-up.

Every template's `sql` is only ever filled with values that have already
been validated against a strict whitelist/regex (see
lambda/ask_answer/handler.py's _validate_slots) - never with raw model
output - so this isn't "parameterized" in the SQL-driver bind-variable
sense (Athena's API doesn't support that), it's parameterized in the
sense that the LLM only ever selects from closed, pre-validated value
sets.
"""

VALID_CLIENT_SITES = ["site_a", "site_b", "site_c"]
VALID_GAMES = [
    "game_01", "game_02", "game_03", "game_04",
    "game_05", "game_06", "game_07", "game_08",
]
SITE_REGIONS = {"site_a": "sea", "site_b": "latam", "site_c": "eu"}

TEMPLATES = {
    "ggr": {
        "label": "GGR (Gross Gaming Revenue)",
        "unit": "USD",
        "kpi_definition_anchor": "ggr-gross-gaming-revenue",
        "description": "Total bets minus total wins, in USD, over a date range.",
        "source_table": "gold_daily_kpi",
        "game_source_table": "silver_events",
        "sql": """
            SELECT SUM(ggr_usd) AS value
            FROM gold_daily_kpi
            WHERE client_site_id = '{client_site_id}' AND dt BETWEEN '{start_date}' AND '{end_date}'
        """,
        "game_sql": """
            SELECT SUM(bet_amount_usd - win_amount_usd) AS value
            FROM silver_events
            WHERE client_site_id = '{client_site_id}'
              AND game_id = '{game_id}'
              AND event_type = 'bet_settled'
              AND dt BETWEEN '{start_date}' AND '{end_date}'
        """,
    },
    "dau": {
        "label": "DAU (Daily Active Users)",
        "unit": "average players/day",
        "kpi_definition_anchor": "dau-daily-active-users",
        "description": "Average daily active user count over a date range.",
        "source_table": "gold_daily_kpi",
        "game_source_table": "silver_events",
        "sql": """
            SELECT AVG(CAST(dau AS DOUBLE)) AS value
            FROM gold_daily_kpi
            WHERE client_site_id = '{client_site_id}' AND dt BETWEEN '{start_date}' AND '{end_date}'
        """,
        "game_sql": """
            SELECT AVG(CAST(dau AS DOUBLE)) AS value
            FROM (
                SELECT dt, COUNT(DISTINCT player_id) AS dau
                FROM silver_events
                WHERE client_site_id = '{client_site_id}'
                  AND game_id = '{game_id}'
                  AND event_type = 'session_start'
                  AND dt BETWEEN '{start_date}' AND '{end_date}'
                GROUP BY dt
            )
        """,
    },
    "arpu": {
        "label": "ARPU (Average Revenue Per User)",
        "unit": "USD/user",
        "kpi_definition_anchor": "arpu-average-revenue-per-user",
        "description": "Average revenue per active user over a date range (GGR / DAU, averaged per day).",
        "source_table": "gold_daily_kpi",
        "game_source_table": "silver_events",
        "sql": """
            SELECT AVG(arpu_usd) AS value
            FROM gold_daily_kpi
            WHERE client_site_id = '{client_site_id}' AND dt BETWEEN '{start_date}' AND '{end_date}'
        """,
        "game_sql": """
            SELECT AVG(CASE WHEN dau > 0 THEN ggr / dau ELSE 0 END) AS value
            FROM (
                SELECT dt,
                       COUNT(DISTINCT CASE WHEN event_type = 'session_start'
                                           THEN player_id END) AS dau,
                       SUM(CASE WHEN event_type = 'bet_settled'
                                THEN bet_amount_usd - win_amount_usd ELSE 0 END) AS ggr
                FROM silver_events
                WHERE client_site_id = '{client_site_id}'
                  AND game_id = '{game_id}'
                  AND dt BETWEEN '{start_date}' AND '{end_date}'
                GROUP BY dt
            )
        """,
    },
    "retention_d1": {
        "label": "D1 Retention",
        "unit": "fraction (0-1)",
        "kpi_definition_anchor": "d1--d7-retention",
        "description": "Average D1 (next-day) retention rate for cohorts registered in a date range.",
        "source_table": "gold_cohort_retention",
        "sql": """
            SELECT AVG(d1_retention_rate) AS value
            FROM gold_cohort_retention
            WHERE client_site_id = '{client_site_id}' AND registration_date BETWEEN '{start_date}' AND '{end_date}'
        """,
    },
    "retention_d7": {
        "label": "D7 Retention",
        "unit": "fraction (0-1)",
        "kpi_definition_anchor": "d1--d7-retention",
        "description": "Average D7 (7-day) retention rate for cohorts registered in a date range.",
        "source_table": "gold_cohort_retention",
        "sql": """
            SELECT AVG(d7_retention_rate) AS value
            FROM gold_cohort_retention
            WHERE client_site_id = '{client_site_id}' AND registration_date BETWEEN '{start_date}' AND '{end_date}'
        """,
    },
}

KPI_DEFINITIONS_VERSION = "v1"  # keep in sync with data-foundation/KPI_DEFINITIONS.md's version header
