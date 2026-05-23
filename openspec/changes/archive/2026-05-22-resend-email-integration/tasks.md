# Tasks: Resend Email Integration

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 480–700 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (template+transport) → PR 2 (service+wiring) → PR 3 (router integration tests) |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Build rendering and provider transport base | PR 1 | Includes template + transport + unit tests; no router changes. |
| 2 | Add email service and publication wiring | PR 2 | Depends on PR 1; includes config gating and aggregation logs. |
| 3 | Prove post-commit best-effort behavior end-to-end | PR 3 | Depends on PR 2; router-level failure-survival tests. |

## Phase 1: Foundation (Config + Contracts)

- [x] 1.1 Update `backend/app/config.py` with `EMAIL_ENABLED`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `RESEND_API_URL`, `EMAIL_TIMEOUT_SECONDS` defaults.
- [x] 1.2 Update `backend/.env.example` with disabled-by-default email settings and verified sender guidance.
- [x] 1.3 Create typed email contracts in `backend/app/services/email_service.py` (recipient, row, send result, batch result, transport interface).

## Phase 2: Core Implementation (Template + Transport + Service)

- [x] 2.1 Create `backend/app/services/billing_email_template.py` to render UPDS HTML/text with escaped dynamic values and fixed table columns.
- [x] 2.2 Implement zebra rows (`#ffffff/#f9f9f9`) and TOTAL row (`#e8f0fe`, right-aligned `TOTAL:`, red exact total, `colspan="2"`) from snapshot designations only.
- [x] 2.3 Create `backend/app/services/resend_email_transport.py` using `httpx.Client` POST `{RESEND_API_URL}/emails`, bearer auth, timeout, and non-2xx error mapping.
- [x] 2.4 Implement `EmailService` in `backend/app/services/email_service.py`: config gating, recipient filtering (`User.email` then `Teacher.email`), CI-to-snapshot match, and per-recipient send loop.
- [x] 2.5 Add batch outcome logging (`eligible/sent/failed/skipped`) and ensure provider/config/recipient issues never raise outside service send path.

## Phase 3: Integration Wiring (Billing Publication)

- [x] 3.1 Modify `backend/app/routers/billing_publication.py` to load active docentes with `joinedload(User.teacher)` before publication response.
- [x] 3.2 After `db.commit()` and `db.refresh(publication)`, invoke `EmailService.send_billing_published(...)` inside nested local `try/except`.
- [x] 3.3 Ensure email exceptions are logged and swallowed so publication response and internal `Notification` rows remain successful.

## Phase 4: Testing / Verification

- [x] 4.1 Create `backend/tests/services/test_billing_email_template.py` for static sections, highlighted docente name, footer contact, zebra rows, and exact TOTAL row contract.
- [x] 4.2 Add template assertions for fixed headers (`Materia`, `Monto a facturar`, `Grupo`, `Semestre`) and `colspan="2"` in TOTAL row.
- [x] 4.3 Create `backend/tests/services/test_resend_email_transport.py` with `httpx.MockTransport` for payload, auth header, timeout/provider failure mapping.
- [x] 4.4 Create `backend/tests/services/test_email_service.py` for disabled config, missing provider config, missing recipient email, successful send, and provider failure aggregation.
- [x] 4.5 Create `backend/tests/routers/test_billing_publication_email.py` to prove post-commit best-effort: publication stays 200 and internal notifications persist on email failure.

## Phase 5: Final Checks

- [x] 5.1 Run `pytest backend/tests/services/test_billing_email_template.py backend/tests/services/test_resend_email_transport.py backend/tests/services/test_email_service.py backend/tests/routers/test_billing_publication_email.py`.
- [ ] 5.2 Run full `pytest` and capture any flakiness/risk notes for apply handoff.
