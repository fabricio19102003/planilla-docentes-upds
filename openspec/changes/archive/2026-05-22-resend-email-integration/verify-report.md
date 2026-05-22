## Verification Report

**Change**: resend-email-integration  
**Version**: N/A  
**Mode**: Standard (`openspec/config.yaml` has `strict_tdd: false`)  
**Verified on**: 2026-05-22  
**Verdict**: PASS WITH WARNINGS

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 19 |
| Tasks complete | 18 |
| Tasks incomplete | 1 |

Task 5.2 remains unchecked in `tasks.md` because the full backend suite exits non-zero. Re-run evidence confirms the two failures are outside the email integration slice.

### Build & Tests Execution

**Build / syntax check**: ✅ Passed

```text
Command: python -m compileall -q app
Working directory: backend
Result: exit 0, no output
```

**Focused email tests**: ✅ 14 passed / 0 failed / 0 skipped

```text
Command:
$env:DATABASE_URL='sqlite:///test.db'; $env:ASYNC_DATABASE_URL='sqlite+aiosqlite:///test.db'; python -m pytest tests/services/test_billing_email_template.py tests/services/test_resend_email_transport.py tests/services/test_email_service.py tests/routers/test_billing_publication_email.py

Result:
collected 14 items
tests\services\test_billing_email_template.py ...
tests\services\test_resend_email_transport.py ...
tests\services\test_email_service.py ......
tests\routers\test_billing_publication_email.py ..
======================== 14 passed, 1 warning in 4.64s ========================
```

**Full backend tests**: ⚠️ 181 passed / 2 failed / 18 skipped

```text
Command:
$env:DATABASE_URL='sqlite:///test.db'; $env:ASYNC_DATABASE_URL='sqlite+aiosqlite:///test.db'; python -m pytest

Result:
collected 201 items
FAILED tests/test_e2e_real_data.py::test_e2e_full_flow
  AssertionError: Biometric file not found: C:\Users\pedro.melgar\WorkSpace\repositorios\planilla-docentes\reporte biometrico marzo_docentes.xls

FAILED tests/test_phase3_api_smoke.py::test_teacher_planilla_and_dashboard_endpoints
  TypeError: fake_generate() got an unexpected keyword argument 'discount_mode'

=========== 2 failed, 181 passed, 18 skipped, 2 warnings in 55.30s ============
```

Classification: both failures are pre-existing/non-email failures. The first requires a local biometric XLS fixture. The second is a smoke-test monkeypatch signature mismatch for `PlanillaGenerator.generate(discount_mode=...)`. Neither touches `backend/app/services/*email*` nor `backend/app/routers/billing_publication.py` email behavior.

**Coverage**: ➖ Not available — `openspec/config.yaml` says pytest-cov is not configured and threshold is `0`.

### Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Config-gated outbound email | Email disabled by configuration | `tests/services/test_email_service.py::test_email_service_skips_without_transport_when_disabled`; `tests/test_config.py::test_email_config_defaults_to_disabled_without_resend_credentials` passed in full suite | ✅ COMPLIANT |
| Config-gated outbound email | Provider credentials missing | `tests/services/test_email_service.py::test_email_service_skips_without_transport_when_provider_config_is_missing` | ✅ COMPLIANT |
| Recipient eligibility filtering | Missing recipient email | `tests/services/test_email_service.py::test_email_service_skips_missing_recipient_email` | ✅ COMPLIANT |
| Successful outbound delivery attempt | Successful send attempt | `tests/services/test_email_service.py::test_email_service_sends_billing_email_from_snapshot_and_teacher_email_fallback`; `tests/routers/test_billing_publication_email.py::test_publish_billing_sends_email_after_successful_commit` | ✅ COMPLIANT |
| UPDS-branded billing email template contract | Template includes mandatory static sections | `tests/services/test_billing_email_template.py::test_template_renders_static_sections_and_escapes_dynamic_values` | ✅ COMPLIANT |
| Billing table mirrors consolidated snapshot items | Multiple items render zebra rows and exact total | `tests/services/test_billing_email_template.py::test_template_renders_fixed_headers_zebra_rows_and_exact_total` | ✅ COMPLIANT |
| Provider failure is best-effort | Provider failure during send | `tests/services/test_resend_email_transport.py::test_resend_transport_maps_provider_failure_to_failed_result`; `tests/services/test_resend_email_transport.py::test_resend_transport_maps_network_failure_to_failed_result`; `tests/services/test_email_service.py::test_email_service_aggregates_provider_failure_without_raising`; `tests/routers/test_billing_publication_email.py::test_publish_billing_survives_email_service_failure_and_keeps_notifications` | ✅ COMPLIANT |

**Compliance summary**: 7/7 scenarios compliant.

### Correctness (Static Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| Disabled-by-default email config | ✅ Implemented | `backend/app/config.py` defaults `EMAIL_ENABLED=False`, `RESEND_API_KEY=None`, `RESEND_FROM_EMAIL=None`, `RESEND_API_URL=https://api.resend.com`, `EMAIL_TIMEOUT_SECONDS=3.0`; `.env.example` documents verified sender/domain. |
| Provider transport | ✅ Implemented | `backend/app/services/resend_email_transport.py` posts `{RESEND_API_URL}/emails` with bearer auth and JSON `{from,to,subject,html,text}`, maps request/non-2xx failures to `EmailSendResult(status="failed")`. |
| Email service gating/filtering | ✅ Implemented | `backend/app/services/email_service.py` skips disabled/missing provider config, resolves `User.email` then `Teacher.email`, matches `teacher_ci` to snapshot rows, and aggregates `eligible/sent/failed/skipped`. |
| Template contract | ✅ Implemented | `backend/app/services/billing_email_template.py` renders escaped HTML/text, institutional colors, fixed headers, zebra rows, and exact Decimal total from rendered snapshot rows. |
| Post-commit best-effort routing | ✅ Implemented | `backend/app/routers/billing_publication.py` commits and refreshes publication before a nested `try/except` email step; failures are logged and swallowed. |

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| Direct `httpx.Client` POST instead of Resend SDK | ✅ Yes | No new SDK dependency; transport is covered with `httpx.MockTransport`. |
| Synchronous post-commit send | ✅ Yes | Router calls email after `db.commit()` and `db.refresh(publication)`. |
| Catch all email exceptions locally | ✅ Yes | Router has nested defensive boundary; service also maps transport exceptions to failed attempts. |
| Active docente `User` rows with `Teacher` fallback | ✅ Yes | Router queries active docentes with `joinedload(User.teacher)`; service resolves `user.email` then `teacher.email`. |
| Render from committed snapshot only | ✅ Yes | Service maps `billing_snapshot.teacher_details[*].designations`; no `PlanillaGenerator` use in email service. |
| Structured logs only for outcomes | ✅ Yes | Service/router log `eligible/sent/failed/skipped`; no DB attempt table added. |

### Issues Found

**CRITICAL**: None for the `resend-email-integration` spec scenarios.

**WARNING**:
- Full configured backend pytest is still red due two unrelated failures: missing local biometric XLS fixture and existing smoke-test fake missing the `discount_mode` parameter.
- `tasks.md` task 5.2 remains unchecked because the full suite is not green, despite being re-run and classified.

**SUGGESTION**:
- Fix or quarantine the two unrelated full-suite failures so future SDD verification can use `pytest` as a clean project-wide gate.
- Set `asyncio_default_fixture_loop_scope` explicitly to silence the pytest-asyncio deprecation warning.

### Verdict

PASS WITH WARNINGS

All email-notification spec scenarios have passing runtime evidence and the implementation matches the proposal/design. The only blocker to a clean PASS is the project-wide `pytest` command failing on two unrelated existing tests.
