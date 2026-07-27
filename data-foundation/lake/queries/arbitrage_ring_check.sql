-- Exploratory query proving the lake can answer module1's arbitrage question:
-- which devices are shared across an abnormal number of distinct player_ids?
-- (Full rule-based scoring lands in module1/arbitrage_detection; this just
-- confirms the raw signal is present and queryable.)
SELECT device_id, COUNT(DISTINCT player_id) AS distinct_players, ARRAY_AGG(DISTINCT player_id) AS player_ids
FROM silver_events
WHERE device_id IS NOT NULL
GROUP BY device_id
HAVING COUNT(DISTINCT player_id) > 1
ORDER BY distinct_players DESC;
