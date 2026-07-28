# Aurora Games Partner Integration FAQ

Document ID: AG-FAQ-002 | Version 2.8 | Audience: integration partners

## §1 Authentication problems

### §1.1 I am getting 401 unauthorized

Check, in order: the token has not expired (tokens last 3600 seconds), the `Authorization` header
uses the `Bearer ` prefix, and the token was issued by the same environment you are calling.

### §1.2 I am getting 403 environment_mismatch

Your token was issued in one environment and used against another. Sandbox and production
credentials are not interchangeable.

### §1.3 My credentials stopped working after onboarding

Sandbox credentials issued during onboarding remain valid indefinitely. Production credentials are
only enabled after certification is passed.

## §2 Webhook problems

### §2.1 My webhook signature check keeps failing

The most common cause is verifying the signature against re-serialized JSON rather than the raw
request body. Byte-for-byte the raw body must be used. The second most common cause is using the
`client_secret` instead of the webhook signing secret.

### §2.2 I am receiving duplicate webhook events

Expected behaviour. Delivery is at-least-once, so consumers must de-duplicate on `event_id`.

### §2.3 I stopped receiving webhooks entirely

Check that your endpoint is returning 2xx within 5 seconds. Endpoints that fail continuously for 24
hours stop being retried for that event.

## §3 Settlement problems

### §3.1 My settlement file is missing

Files publish at 04:00 UTC. If a file has not appeared by 06:00 UTC, raise it with support.

### §3.2 My totals do not match

Confirm you are comparing the same UTC day and joining on `round_id`. Rounds that opened before
midnight and settled after are attributed to the day they settled.

## §4 Sandbox behaviour

### §4.1 My sandbox data disappeared

Sandbox resets every Sunday at 02:00 UTC. This is expected and is not a fault.

### §4.2 Can I load my own test players into sandbox

Yes, through the partner portal's test-data tool. Loaded players are also cleared by the weekly
reset.
