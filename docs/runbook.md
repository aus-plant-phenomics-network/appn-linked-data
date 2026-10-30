# {{Service name}} runbook

For anything on-call-adjacent (§3.5). If you are reading this at 2am, the
answer you need should be above the fold.

## What this service does

{{One paragraph. What breaks for users if it is down?}}

## Ownership

| | |
|---|---|
| Owning team | {{team}} |
| Escalation | {{role-based contact, then technical lead}} |
| Hours of support | {{business hours / 24x7}} |

## Where it runs

| Environment | URL | Infrastructure | Logs | Dashboard |
|---|---|---|---|---|
| Production | {{url}} | {{resource group / cluster}} | {{link}} | {{link}} |
| Staging | {{url}} | {{...}} | {{link}} | {{link}} |

## Dependencies

| Dependency | What breaks without it | Owner |
|---|---|---|
| {{Postgres}} | {{All writes}} | {{team}} |
| {{Upstream catalogue API}} | {{Ingest stalls; existing data still served}} | {{external}} |

## Common operations

### Restart

```bash
{{command}}
```

### Check health

```bash
{{command}}
```

### Roll back a release

```bash
{{command}}
```

## Alerts

| Alert | What it means | First action |
|---|---|---|
| {{IngestLagHigh}} | {{No successful ingest in 2 hours}} | {{Check upstream status, then the ingest logs for 429s}} |

## Known failure modes

### {{Symptom}}

**Cause:** {{...}}
**Fix:** {{...}}
**Permanent fix tracked in:** {{#issue}}
