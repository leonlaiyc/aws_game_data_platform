# LEON Game Data Platform Game Provider Integration Guide

Document ID: AG-GPI-101 | Version 1.0 | Audience: game providers

## §1 Integration direction

This interface is for a game provider connecting game content to LEON Game Data Platform. It is not the
client-operator API used by 2C partners for settlement files and outbound webhooks.

## §2 Game launch

LEON Game Data Platform creates a short-lived launch token and calls the provider's launch endpoint with
`player_id`, `game_id`, `currency`, `language`, and `return_url`. The provider must validate the
token before creating a game session. A launch token is single-use and expires after 60 seconds.

If validation fails, return `401 invalid_launch_token`. If the game or currency is not enabled for
the calling client site, return `403 game_not_enabled`; do not silently substitute another game or
currency.

## §3 Wallet and round lifecycle

Provider-to-platform wallet calls use the ordered operations `balance`, `bet`, `win`, and
`cancel`. Every money operation requires `provider_transaction_id`, `round_id`, `player_id`,
`currency`, and a decimal `amount`.

`provider_transaction_id` is the idempotency key. Retrying the same identifier with the same
payload returns the original result. Reusing it with a different amount, player, or currency
returns `409 idempotency_conflict`.

A `win` may arrive after its matching `bet`, and a zero-value win is valid. A `cancel` reverses one
previous transaction and must name that transaction in `original_provider_transaction_id`.

## §4 Certification and go-live

Certification runs in sandbox and covers launch-token validation, duplicate bet handling, late
wins, cancel/rollback, insufficient balance, unsupported currency, and timeout retries. Production
enablement is per game and client site after certification passes.

For a new-game launch, submit the game manifest, supported currencies, RTP variants, asset URLs,
maintenance contact, and proposed release date at least 10 business days before go-live.

## §5 Operational notices

Providers must notify LEON Game Data Platform before planned maintenance and identify the affected game IDs,
start and end time in UTC, and expected player impact. Emergency incidents should include a stable
incident reference so status updates can be correlated.
