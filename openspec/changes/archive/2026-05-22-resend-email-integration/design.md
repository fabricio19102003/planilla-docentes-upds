# Design: Resend Email Integration

## Technical Approach

Add a backend-only outbound email slice behind environment config. `publish_billing` keeps the publication + internal notification transaction unchanged, commits, refreshes the publication, then performs a locally caught best-effort email step. The email body is rendered from the committed `BillingPublication.billing_snapshot`; no email code recalculates payroll.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| Transport | Direct `httpx.Client` POST to Resend `/emails` | Resend SDK | `httpx==0.28.1` already exists, avoids a new dependency, and is easy to mock with `MockTransport`. |
| Execution | Synchronous post-commit send in the existing sync route | async client, queue, `BackgroundTasks` | Current router is sync and there is no worker/queue. Post-commit keeps behavior simple; short timeout bounds latency. |
| Failure boundary | Catch all email exceptions inside the email step | Let router outer `except` handle it | Email failures must never rollback or mask successful publication/internal notifications. |
| Recipient source | Active docente `User` rows, using `user.email` then linked `Teacher.email` fallback | Only teachers in billing snapshot | Matches existing internal-notification recipient set; docentes without snapshot rows are skipped for email content and logged. |
| Template rendering | `backend/app/services/billing_email_template.py` with explicit Python functions | Jinja/template strings with Excel-style `${...}` placeholders | Backend-safe: no `eval`, no user placeholder interpolation, HTML values escaped with `html.escape(..., quote=True)`. |
| Amount source | Render each row from snapshot `designations[*].payment`; TOTAL is the Decimal sum of those existing snapshot row amounts | Re-run `PlanillaGenerator` or query live designations | Snapshot is the publication source of truth. Summing already-consolidated row amounts is presentation math, not a new payroll algorithm. |
| Outcome storage | Structured logs only: eligible/sent/failed/skipped | New DB table for attempts | Spec only needs operational results; attempt history/retries are out of scope. |

## Data Flow

```text
POST /api/billing/publish
  -> validate approved PlanillaOutput
  -> upsert BillingPublication + recreate Notification rows
  -> log activity -> db.commit() -> db.refresh(publication)
  -> EmailService.send_billing_published(publication, docente_users)
       -> match user.teacher_ci to billing_snapshot.teacher_details[*].teacher_ci
       -> render UPDS HTML table from teacher_data.designations
       -> ResendEmailTransport.send_email() via httpx
       -> log counts/failures
  -> return PublicationResponse
```

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/app/config.py` | Modify | Add `EMAIL_ENABLED: bool = False`, `RESEND_API_KEY: Optional[str]`, `RESEND_FROM_EMAIL: Optional[str]`, `RESEND_API_URL`, `EMAIL_TIMEOUT_SECONDS: float = 3.0`. |
| `backend/.env.example` | Modify | Document disabled-by-default Resend settings and verified sender requirement. |
| `backend/app/services/billing_email_template.py` | Create | Render UPDS-branded HTML/text email: header, docente name, billing month, fixed table columns, zebra rows, TOTAL row, and Gestión Humana footer. Escape all dynamic HTML. |
| `backend/app/services/email_service.py` | Create | `EmailService`, result dataclasses, recipient filtering, snapshot-to-template mapping, aggregate logging. |
| `backend/app/services/resend_email_transport.py` | Create | Small Resend HTTP transport using `httpx.Client(timeout=...)`, bearer auth, JSON payload, non-2xx handling. |
| `backend/app/routers/billing_publication.py` | Modify | After commit/refresh, call email service in nested `try/except`; never raise email errors. Query docentes with `joinedload(User.teacher)` before sending. |
| `backend/tests/services/test_billing_email_template.py` | Create | Unit tests for escaping, fixed columns, zebra striping, TOTAL row/`colspan`, footer contact, and month/docente interpolation. |
| `backend/tests/services/test_email_service.py` | Create | Unit tests for disabled config, missing provider config, invalid/missing emails, missing snapshot rows, success/failure aggregation. |
| `backend/tests/services/test_resend_email_transport.py` | Create | `httpx.MockTransport` tests for request payload, auth header, timeout/provider error mapping. |
| `backend/tests/routers/test_billing_publication_email.py` | Create | Router-level proof that publication and `Notification` rows survive email transport failure. |

## Interfaces / Contracts

```python
EmailRecipient(user_id: int, name: str, email: str)
BillingEmailRow(subject: str, amount: Decimal, group: str, semester: str)
EmailSendResult(status: Literal["sent", "failed", "skipped"], error: str | None = None)
EmailBatchResult(eligible: int, sent: int, failed: int, skipped: int)
```

Snapshot mapping: `teacher_details[*]` is matched by `teacher_ci == User.teacher_ci`. Each `designations[*]` maps `subject -> Materia`, `payment -> Monto a facturar`, `group -> Grupo`, `semester -> Semestre`. `TOTAL` uses `sum(Decimal(str(row["payment"])))` over rendered snapshot rows and is formatted consistently as Bolivianos. Missing/invalid snapshot detail skips only that docente email.

Template rendering: convert Excel-style placeholders to function arguments (`docente_name`, `month_name`, `year`, `rows`). Dynamic HTML uses `html.escape`; amounts use `Decimal` formatting. Resend request: `POST {RESEND_API_URL}/emails` with `Authorization: Bearer {RESEND_API_KEY}` and JSON `{from,to,subject,html,text}`.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | Template rendering contract | Snapshot fixtures; assert escaped values, institutional colors, fixed headers, zebra `#ffffff/#f9f9f9`, TOTAL `#e8f0fe`, red amount, `colspan="2"`, Lisseth contact. |
| Unit | Config gating, recipient filtering, snapshot mapping, aggregation | Instantiate `EmailService` with fake transport/settings; assert no `PlanillaGenerator` use. |
| Transport | Resend payload/auth and error mapping | `httpx.MockTransport`; no network calls. |
| Integration | Billing publish remains successful when email fails | FastAPI `TestClient`, seed approved `PlanillaOutput` + docente user, monkeypatch email service/transport to raise, assert 200 + notifications exist. |

## Migration / Rollout

No DB migration required. Roll out disabled by default; enable only after `RESEND_API_KEY` and verified `RESEND_FROM_EMAIL` are present. Rollback is setting `EMAIL_ENABLED=false`.

## Open Questions

- [ ] Confirm final sender identity/domain outside code before production enablement.
