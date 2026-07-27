-- Daily active users and gross gaming revenue (USD) per site, most recent 14 days.
SELECT dt, client_site_id, region, dau, sessions, new_players, ggr_usd, arpu_usd
FROM gold_daily_kpi
ORDER BY dt DESC, client_site_id
LIMIT 42;
