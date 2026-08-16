# Apply Progress: Medicine Schedule Assistant
**Mode**: Standard
**Delivery**: stacked-to-main, PR 1 `pr1-foundation`; no size exception
**Correction**: Maintainer-authorized native reset `pr1-rescope-correction`; prior 399-line/generic-404 evidence superseded after independent verification measured 442 lines.
## Completed Tasks
- [x] 1.1 Ownership boundary approved previously.
- [x] 1.2 Isolated Medicine models and additive migration.
- [x] 1.3 Model/router registration and default-disabled setting.
- [ ] 1.4 Medicine API schemas deferred coherently to the next backend work unit.
## Work Unit Evidence
| Evidence | Exact result |
|---|---|
| Focused tests | Docker Python 3.12: `pytest tests/test_medicine_schedule_versioning.py` → exit 0; 2 passed, 6 warnings. |
| Actual app gate harness | `pytest -q tests/test_medicine_schedule_versioning.py::test_feature_is_default_disabled_and_registered` → exit 0; registered `GET /api/medicine-schedules/status` returned 404 disabled and `{"enabled": true}` enabled; 1 passed, 6 warnings. |
| Settings regression | `pytest -q tests/routers/test_docente_portal_permissions.py::test_admin_settings_expose_and_update_docente_permission_flags` → exit 0; 1 passed, 5 warnings. |
| Migration/import | Alembic Operations SQLite round-trip → exit 0; 7 tables upgraded and downgraded. `app.main`, `app.models`, and Medicine router imports → `imports: ok`. |
| Scope integrity | `git diff --check` → exit 0. Candidate methodology counts complete untracked candidate files plus tracked additions/deletions, including full `tasks.md` and `apply-progress.md`. |
| Rollback / boundary / size | Revert Medicine models, migration, status route/test, and setting/registration lines only; schemas move to task 1.4. No designation, attendance, payroll, scheduling, parser, or lifecycle behavior changed. PR 1 remains dark foundation at 356 changed lines. |
