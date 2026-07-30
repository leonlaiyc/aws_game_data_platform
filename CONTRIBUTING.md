# Contributing

This is a business-first AWS Solutions Architect portfolio project. Small,
reviewable changes that preserve its four problem statements are welcome.

Before submitting a change:

1. Keep the default architecture scale-to-zero or request-priced. A new
   provisioned or hourly resource needs a documented cost unit, adoption
   trigger, teardown command, and independent teardown check.
2. Use synthetic data only. Never include credentials, real account IDs,
   partner documents, player records, or local environment files.
3. Preserve identity-derived tenant scope. Tenant identifiers supplied in a
   request body are not authorization.
4. Keep numeric and risk evidence code-rendered. An LLM may explain approved
   evidence; it may not invent a value or make a final fraud decision.
5. Add deterministic offline coverage and update the relevant cost,
   architecture, runbook, and known-boundary documentation.

Run the local acceptance checks:

```bash
python -m pytest -q
python -m compileall -q .
cd infra
cdk synth --quiet
```

Do not run `cdk deploy` as part of a contribution unless the repository owner
has explicitly approved the account, cost, and alert destination.
