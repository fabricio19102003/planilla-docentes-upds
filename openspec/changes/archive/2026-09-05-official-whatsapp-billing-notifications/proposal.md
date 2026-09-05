# Proposal: Official WhatsApp Billing Notifications

## Intent

Deliver auditable production WhatsApp billing notices without duplicate or unconsented sends, preserving email only as a defined alternative.

## Scope

### In Scope
- Billing-only Utility templates for publication snapshots.
- Explicit evidenced consent on canonical verified E.164 numbers; opt-out cancels pending jobs.
- Masked admin preview and digest-bound confirmation.
- PostgreSQL outbox, dedicated worker, bounded reconciliation, and durable status.
- Fail-closed readiness requiring sender `ONLINE` and every current Content SID Approved Utility.
- Repeatable expiring PDF media (`HEAD`/`GET`, `application/pdf`, maximum 15,000,000 bytes).
- Verified idempotent, monotonic callbacks; email only for no consent or definite terminal failure, never ambiguity.

### Out of Scope
- General notices, Marketing, pricing logic, and automatic publication sends.

## Capabilities

### New Capabilities
- `whatsapp-billing-notifications`: Consent, confirmation, durable dispatch, readiness, media, callbacks, reconciliation, opt-out, and status.

### Modified Capabilities
- `email-notifications`: Restrict billing email selection to recipients without WhatsApp consent or with definite terminal WhatsApp failure.

## Approach

Create an immutable batch from `BillingPublication` plus version. Bind confirmation to recipients, consent revisions, channels, Content SIDs, and PDF identities. Commit jobs transactionally; a leased PostgreSQL worker dispatches with a Restricted API Key. Keep the Auth Token separate for canonical-URL signature validation. Unknown outcomes remain WhatsApp-only until callback or lookup resolves them.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `backend/app/{models,services,routers}`; `backend/alembic/versions/` | Modified/New | Consent, outbox, worker, Twilio, callbacks, media, email policy |
| `frontend/src/{api/hooks,pages}` | Modified | Preview, confirmation, readiness, and delivery status |
| `deploy/`; `backend/app/config.py` | Modified | Worker, media, URLs, credentials, readiness |
| `backend/tests/`; `frontend/` tests | Modified | Delivery and UI contracts |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Duplicate or misrouted notices | Medium | Digest checks, immutable jobs, monotonic events, no ambiguous fallback |
| Provider/configuration drift | High | Live fail-closed readiness and deployment revalidation |
| Sensitive PDF exposure | Medium | Private storage, opaque hashed tokens, expiry, revocation, `no-store` |

## Rollback Plan

Disable official WhatsApp and stop the worker; cancel unleased jobs, revoke media tokens, preserve audits, and revert UI/config routing. Additive database objects remain inert; operators explicitly restore the prior email policy.

## Dependencies

- Twilio sender, approved Utility Content SIDs, Advanced Opt-Out, separated credentials, canonical HTTPS callbacks, PostgreSQL, and private media storage.

## Success Criteria

- [ ] Confirmed eligible recipients receive one snapshot-bound WhatsApp job with auditable terminal state.
- [ ] Stale digests, unverified consent, non-ready provider state, invalid callbacks, expired/oversized media, and ambiguous sends fail safely.
- [ ] Opt-out prevents future sends and cancels pending work; email follows only the two approved fallback cases.
