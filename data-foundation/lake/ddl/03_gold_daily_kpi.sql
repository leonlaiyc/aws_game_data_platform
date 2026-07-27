-- Gold: daily KPIs at dt x client_site_id grain. Small table (~ days x sites
-- rows), so unlike bronze/silver it isn't partitioned - partitioning a table
-- this size would add overhead for no benefit.
DROP TABLE IF EXISTS gold_daily_kpi;

CREATE TABLE gold_daily_kpi
WITH (
    format = 'PARQUET',
    external_location = 's3://$bucket/gold/daily_kpi/'
) AS
WITH site_days AS (
    SELECT DISTINCT dt, client_site_id, region FROM silver_events
),
session_agg AS (
    SELECT dt, client_site_id, COUNT(DISTINCT player_id) AS dau, COUNT(*) AS sessions
    FROM silver_events WHERE event_type = 'session_start' GROUP BY dt, client_site_id
),
reg_agg AS (
    SELECT dt, client_site_id, COUNT(*) AS new_players
    FROM silver_events WHERE event_type = 'player_registered' GROUP BY dt, client_site_id
),
bet_agg AS (
    SELECT dt, client_site_id,
        SUM(bet_amount_usd) AS gross_bets_usd,
        SUM(win_amount_usd) AS gross_wins_usd
    FROM silver_events WHERE event_type = 'bet_settled' GROUP BY dt, client_site_id
),
deposit_agg AS (
    SELECT dt, client_site_id, SUM(amount_usd) AS deposits_usd
    FROM silver_events WHERE event_type = 'deposit' AND payload.status = 'completed' GROUP BY dt, client_site_id
),
withdrawal_agg AS (
    SELECT dt, client_site_id, SUM(amount_usd) AS withdrawals_usd
    FROM silver_events WHERE event_type = 'withdrawal' AND payload.status = 'completed' GROUP BY dt, client_site_id
)
SELECT
    d.dt,
    d.client_site_id,
    d.region,
    COALESCE(sess.dau, 0) AS dau,
    COALESCE(sess.sessions, 0) AS sessions,
    COALESCE(reg.new_players, 0) AS new_players,
    ROUND(COALESCE(bet.gross_bets_usd, 0.0), 2) AS gross_bets_usd,
    ROUND(COALESCE(bet.gross_wins_usd, 0.0), 2) AS gross_wins_usd,
    ROUND(COALESCE(bet.gross_bets_usd, 0.0) - COALESCE(bet.gross_wins_usd, 0.0), 2) AS ggr_usd,
    ROUND(COALESCE(dep.deposits_usd, 0.0), 2) AS deposits_usd,
    ROUND(COALESCE(wd.withdrawals_usd, 0.0), 2) AS withdrawals_usd,
    ROUND(
        CASE WHEN COALESCE(sess.dau, 0) > 0
            THEN (COALESCE(bet.gross_bets_usd, 0.0) - COALESCE(bet.gross_wins_usd, 0.0)) / sess.dau
            ELSE 0.0
        END, 4
    ) AS arpu_usd
FROM site_days d
LEFT JOIN session_agg sess ON sess.dt = d.dt AND sess.client_site_id = d.client_site_id
LEFT JOIN reg_agg reg ON reg.dt = d.dt AND reg.client_site_id = d.client_site_id
LEFT JOIN bet_agg bet ON bet.dt = d.dt AND bet.client_site_id = d.client_site_id
LEFT JOIN deposit_agg dep ON dep.dt = d.dt AND dep.client_site_id = d.client_site_id
LEFT JOIN withdrawal_agg wd ON wd.dt = d.dt AND wd.client_site_id = d.client_site_id;
