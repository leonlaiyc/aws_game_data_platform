# Aurora Games Partner Integration Guide

Document ID: AG-INT-001 | Version 4.2 | Audience: integration partners

## §1 Authentication

### §1.1 Obtaining credentials

Every partner receives a `partner_id` and a `client_secret` during onboarding. Credentials are
issued separately per environment — sandbox credentials never work against production.

### §1.2 Requesting an access token

Exchange your credentials for a bearer token via the token endpoint. Tokens are valid for 3600
seconds. Request a new token before expiry; there is no refresh-token flow.

```
POST /oauth/token
grant_type=client_credentials&partner_id=...&client_secret=...
```

### §1.3 Using the token

Send the token as `Authorization: Bearer <token>` on every subsequent request. Requests without a
valid token return `401 unauthorized`. Requests with a token issued for a different environment
return `403 environment_mismatch`.

## §2 Environments and base URLs

### §2.1 Sandbox

Sandbox is a full-featured test environment seeded with synthetic players and games. Balances are
not real, settlement is simulated, and data is reset every Sunday at 02:00 UTC.

### §2.2 Production

Production carries real player balances and real settlement. Access requires completing
certification (see §5) before your partner account is enabled.

### §2.3 Environment selection

The base URL differs per environment. Confirm which environment you are targeting before
configuring your client — using a sandbox base URL with production credentials is the single most
common onboarding error.

## §3 Webhooks

### §3.1 Registering an endpoint

Register a webhook endpoint per environment through the partner portal. The endpoint must be
HTTPS, must respond within 5 seconds, and must return a 2xx status to acknowledge receipt.

### §3.2 Signature verification

Every webhook request carries an `X-Aurora-Signature` header containing an HMAC-SHA256 of the raw
request body, computed with your **webhook signing secret**. The signing secret is distinct from
your `client_secret`. Always verify the signature against the raw body before parsing — verifying
against re-serialized JSON will fail.

### §3.3 Retry behaviour

A webhook that does not receive a 2xx response is retried with exponential backoff for up to 24
hours. Duplicate deliveries are possible; consumers must be idempotent and should de-duplicate on
`event_id`.

## §4 Settlement

### §4.1 Daily settlement file

A settlement file is published per client site each day at 04:00 UTC covering the previous UTC day.

### §4.2 Reconciliation

Reconcile the settlement file against your own transaction records using `round_id` as the join
key. Discrepancies should be raised within 5 business days.

## §5 Certification

Before production access is granted, partners must pass certification: a scripted set of test
cases executed against sandbox, covering authentication, webhook signature verification, and
settlement reconciliation. Certification results are reviewed by the integration team.
