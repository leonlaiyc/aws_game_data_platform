# Aurora Games Platform Release Notes

Document ID: AG-REL-003 | Version 2026.07 | Audience: integration partners

## §1 Release 2026.07 (current)

### §1.1 Added

- Settlement files now include a `game_provider_id` column, allowing partners operating multiple
  providers to split reconciliation without a separate lookup.
- Webhook payloads now carry `event_id` on every event type. Previously some event types omitted
  it, which made de-duplication unreliable.

### §1.2 Changed

- Token lifetime standardised at 3600 seconds across both environments. Sandbox previously issued
  7200-second tokens, which caused partners to build against the wrong assumption.

### §1.3 Deprecated

- The `/v1/rounds/lookup` endpoint is deprecated in favour of `/v2/rounds/search`. `/v1` remains
  available through 2026-12-31.

## §2 Release 2026.04

### §2.1 Added

- Sandbox test-data tool in the partner portal, allowing partners to load their own test players.

### §2.2 Fixed

- Webhook retries occasionally stopped early when an endpoint returned 3xx. Redirects are now
  treated as failures and retried correctly.

## §3 Release 2026.01

### §3.1 Changed

- Settlement file publication moved from 06:00 UTC to 04:00 UTC to give partners more time for
  same-day reconciliation.

### §3.2 Deprecated

- MD5 webhook signatures removed. HMAC-SHA256 is now the only supported signature algorithm.
