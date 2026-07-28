# Aurora Games Maintenance Calendar

Document ID: AG-MNT-004 | Version 2026.07 | Audience: integration partners

## §1 Recurring maintenance

### §1.1 Sandbox weekly reset

Every Sunday, 02:00–02:30 UTC. Sandbox data is cleared and reseeded. Sandbox is unavailable during
the window. Production is unaffected.

### §1.2 Settlement file generation

Daily, 03:30–04:00 UTC. Settlement APIs may return stale data during generation. Files are
available from 04:00 UTC.

## §2 Planned maintenance windows

### §2.1 Standard window

Production maintenance, when required, is performed on the second Tuesday of each month,
01:00–03:00 UTC. Partners are notified at least 14 days in advance through the partner portal.

### §2.2 Emergency maintenance

Emergency maintenance may occur outside the standard window. Notification is sent as early as
circumstances allow, and always before the window opens where the issue permits.

## §3 During a maintenance window

### §3.1 Expected behaviour

APIs return `503 service_unavailable` with a `Retry-After` header. Clients should honour
`Retry-After` rather than retrying immediately.

### §3.2 Webhooks

Webhook delivery is paused, not dropped. Queued events are delivered after the window closes,
subject to the normal 24-hour retry policy.
