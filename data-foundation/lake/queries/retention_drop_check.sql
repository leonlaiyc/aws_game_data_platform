-- Confirms the scripted retention drop is visible: site_b's D1 retention
-- should dip sharply for cohorts registered just before the drop window
-- (see scenario_manifest.json for exact dates), then recover.
SELECT registration_date, client_site_id, cohort_size, d1_retention_rate, d7_retention_rate
FROM gold_cohort_retention
WHERE client_site_id = 'site_b'
ORDER BY registration_date;
