# Security Policy

## Scope

This repository is a portfolio proof of concept. Its companies, tenants,
players, credentials, identifiers, events, and operational scenarios are
synthetic. It must not be used with production partner or player data without
replacing the documented PoC identity, ingestion, isolation, and operations
boundaries.

## Reporting a vulnerability

Please use GitHub's **Report a vulnerability** flow on the repository Security
tab. Do not open a public issue containing an exploit, credential, personal
data, or tenant-isolation detail.

Include the affected path, reproduction steps, likely impact, and a minimal
proof of concept. Please do not test against infrastructure or accounts that
you do not own.

## Secrets and sample data

- Never commit AWS credentials, session tokens, private keys, `.env` files,
  Terraform state, real partner documents, or real player data.
- Use fictitious 12-digit AWS account IDs only in tests.
- Treat generated simulator output as local data; it is ignored by Git.
- Scope AWS deployments to a disposable development account, run the
  paid-account preflight, and destroy metered demo resources immediately.

The repository's threat model and residual production risks are documented in
[`docs/threat-model.md`](docs/threat-model.md) and
[`docs/project-closeout.md`](docs/project-closeout.md).
