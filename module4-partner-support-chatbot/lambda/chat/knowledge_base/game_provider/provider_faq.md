# Aurora Games Game Provider Integration FAQ

Document ID: AG-GPF-102 | Version 1.0 | Audience: game providers

## §1 Launch problems

### §1.1 Launch tokens are rejected

Confirm the token is used only once, within 60 seconds, and against the same environment that
issued it. Sandbox tokens do not work in production.

### §1.2 A game returns game_not_enabled

Production enablement is scoped to both game ID and client site. Confirm certification is complete
and the requested currency is included in the approved manifest.

## §2 Wallet problems

### §2.1 A bet timed out and I do not know whether to retry

Retry with the same `provider_transaction_id` and identical payload. The platform returns the
original result without applying the debit twice.

### §2.2 I receive idempotency_conflict

The identifier was already used with a different player, currency, amount, or operation. Do not
generate a replacement identifier for the same logical transaction; investigate the payload
change and escalate with the original identifier.

### §2.3 A cancel is rejected

Confirm `original_provider_transaction_id` identifies a successful bet or win, the currencies
match, and the transaction has not already been cancelled.

## §3 New games and maintenance

### §3.1 What is required for a new game?

Provide the game manifest, currencies, RTP variants, assets, maintenance contact, and target
release date. Allow at least 10 business days for certification and enablement.

### §3.2 How do I report maintenance?

Provide affected game IDs, start and end time in UTC, expected player impact, and an incident or
change reference. Do not use the client-operator notification interface for provider maintenance.
