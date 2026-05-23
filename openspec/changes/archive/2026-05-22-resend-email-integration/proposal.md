# Proposal: Resend Email Integration

## Intent

Add a small, safe outbound-email capability so docentes can receive email when billing is published, while preserving the existing internal notification and publication workflow.

## Scope

### In Scope
- Add an `EmailService` abstraction with a Resend HTTP transport using existing `httpx`.
- Add Resend settings: API key, sender, enable flag, timeout.
- Send billing-published emails after successful DB publication commit.
- Keep email best-effort: failures are logged and never rollback publication or DB notifications.
- Add backend tests for disabled config, successful send, and provider failure.

### Out of Scope
- Email templates UI, queues/background workers, retries, unsubscribe flows.
- Other email events beyond billing publication.
- Resend Python SDK dependency in the MVP.

## Capabilities

### New Capabilities
- `email-notifications`: Outbound operational emails sent through an internal email service abstraction.

### Modified Capabilities
- None.

## Approach

Use direct HTTP (`httpx`) instead of the Resend SDK for the first slice because `httpx` already exists, keeps dependency surface smaller, and is easier to test with transport/client mocks. Add a narrow `EmailService` API plus `ResendEmailTransport`. `publish_billing` remains the first use case: create/update publication and internal notifications as today, commit them, then attempt emails for active docentes with valid email addresses. Log `eligible/sent/failed/skipped` counts.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/config.py` | Modified | Resend/email settings. |
| `backend/app/services/email_service.py` | New | Email abstraction and result types. |
| `backend/app/services/resend_email_transport.py` | New | Resend HTTP transport. |
| `backend/app/routers/billing_publication.py` | Modified | Trigger best-effort billing-published email. |
| `backend/tests/` | Modified | Add focused email/publication behavior tests. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Provider/network failure | Med | Best-effort after commit; log failures only. |
| Request latency | Med | Short timeout; defer queue/background worker. |
| Missing/invalid docente emails | Med | Skip invalid/missing recipients and log counts. |
| Misconfigured sender/API key | Med | Disabled-by-default flag and clear logs. |

## Rollback Plan

Disable email via config flag. If needed, revert the email service files and billing hook; publication and internal notifications stay unchanged.

## Dependencies

- Resend account, verified sender/domain, `RESEND_API_KEY` in backend environment.
- Existing `httpx==0.28.1`.

## Success Criteria

- [ ] Publishing billing still succeeds if Resend fails.
- [ ] Internal DB notifications remain unchanged.
- [ ] Valid active docente recipients receive one attempted billing-published email.
- [ ] Tests cover disabled email, success, and failure behavior.
