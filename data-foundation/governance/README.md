# Client Data Isolation

Demonstrates the multi-tenant security boundary: one IAM role per client site
(`aurora-games-analyst-site_a/b/c`, created by `infra/infra/governance_stack.py`), each able to
query `gold_daily_kpi` — a single table holding all 3 sites' rows — and see **only its own site's
rows**, enforced by an **AWS Lake Formation row-level Data Filter**, not by application-level
`WHERE` clauses that a bug could omit.

## Why this matters for a B2B platform

Aurora Games' client sites are separate business customers. A dashboard, an ad hoc query, or a
future BI tool must never be able to show one client another client's numbers — that's not a bug
class you want to depend on every future SQL query getting right by convention. Enforcing it at
the data-access layer (Lake Formation) means the boundary holds even if an analyst writes
`SELECT * FROM gold_daily_kpi` with no `WHERE` clause at all.

## Setup and rebuild safety

```bash
cd infra && cdk deploy AuroraGamesGovernanceStack   # creates the 3 IAM roles
cd ../data-foundation/governance
../.venv/Scripts/python.exe setup_client_isolation.py   # Lake Formation filters + grants
../.venv/Scripts/python.exe verify_isolation.py         # proves it
```

The setup script is idempotent, but it is not literally a one-time concern:
the lake builder uses Athena `DROP/CREATE` for idempotent Gold rebuilds, and
that replacement removes data-cell filters attached to the old Glue table.
`build_lake.py` therefore invalidates the completion marker, rebuilds the
tables, reapplies this setup, and only then publishes the new completion
marker. If governance reapplication fails, consumers see no completed
publication.

**Why the Lake Formation setup is a script, not a CDK resource:** `cdk deploy` runs as the CDK
bootstrap's CloudFormation execution role, which is not a registered Lake Formation Data Lake
Administrator — creating `AWS::LakeFormation::DataCellsFilter`/`PrincipalPermissions` resources
that way would hit the same `Insufficient permissions` wall documented in
`module2-experimentation-platform/orchestration/README.md`. `setup_client_isolation.py` runs with
the account's own admin credentials instead, consistent with how that was resolved.

## The gotcha that would have silently defeated this

Every new Glue table gets an automatic `IAM_ALLOWED_PRINCIPALS` grant — Lake Formation's
backward-compatibility mode that means "defer entirely to IAM policies". If left in place, **any
principal whose own IAM policy allows `glue:GetTable` etc. gets full, unfiltered access**,
regardless of any row-level Data Filter granted separately — the filter would look like it was
configured correctly but do nothing. `setup_client_isolation.py` explicitly revokes this grant on
`gold_daily_kpi` specifically (not the whole database — other tables keep the default behavior)
before creating the filters, which is what actually makes them take effect.

## Verified output (actual run)

```
=== Baseline: caller's own (unfiltered admin) credentials ===
  Sees 3 site(s): [{'client_site_id': 'site_a', 'rows': '60'}, {'client_site_id': 'site_b', 'rows': '59'}, {'client_site_id': 'site_c', 'rows': '60'}]

=== Assumed role for site_a ===
  Sees 1 site(s): [{'client_site_id': 'site_a', 'rows': '60'}]
  PASS: expected to see only 'site_a'
=== Assumed role for site_b ===
  Sees 1 site(s): [{'client_site_id': 'site_b', 'rows': '59'}]
  PASS
=== Assumed role for site_c ===
  Sees 1 site(s): [{'client_site_id': 'site_c', 'rows': '60'}]
  PASS
```

## Scope of this demo (what it doesn't cover)

- Only `gold_daily_kpi` is filtered — extending to `gold_player_features`/`gold_cohort_retention`
  is the same pattern (one more `create_data_cells_filter` + `grant_permissions` call each), not
  done here to keep the demo focused.
- The analyst roles' trust policy is simplified to the account root (any principal in-account
  that has `sts:AssumeRole` permission can assume them). A real deployment would scope trust to a
  specific external identity — a federated SSO group per client, or a cross-account role — not an
  in-account demo assumption.
- Cost: Lake Formation Data Filters and grants are a control-plane feature with no additional
  charge; Athena billing (`$5/TB scanned`) is unaffected by whether a query is filtered.

## Teardown

```bash
# Reverse order: revoke grants/filters (Lake Formation), then destroy the IAM roles (CDK)
aws lakeformation revoke-permissions --principal '{"DataLakePrincipalIdentifier":"<role-arn>"}' \
  --resource '{"DataCellsFilter":{"TableCatalogId":"<account>","DatabaseName":"aurora_games_lake","TableName":"gold_daily_kpi","Name":"<site>_only"}}' \
  --permissions SELECT
aws lakeformation delete-data-cells-filter --table-catalog-id <account> --database-name aurora_games_lake \
  --table-name gold_daily_kpi --name <site>_only
# Restore the default IAM-allowed access other tables still use:
aws lakeformation grant-permissions --principal '{"DataLakePrincipalIdentifier":"IAM_ALLOWED_PRINCIPALS"}' \
  --resource '{"Table":{"DatabaseName":"aurora_games_lake","Name":"gold_daily_kpi"}}' --permissions ALL
cd infra && cdk destroy AuroraGamesGovernanceStack
```
