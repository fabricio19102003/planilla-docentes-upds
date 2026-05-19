## Verification Report

**Change**: docente-profile-photos-permissions
**Version**: N/A
**Mode**: Standard
**Final verdict**: PASS WITH WARNINGS

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 19 |
| Tasks complete | 19 |
| Tasks incomplete | 0 |

Task 4.4 is now complete for automated verification: focused backend pytest, backend compile, frontend lint, and frontend build all passed. Manual browser smoke remains recommended as a non-blocking follow-up because this shell verification cannot exercise an interactive browser.

### Build & Tests Execution
**Backend compile**: ✅ Passed
```text
python -m compileall backend/app backend/tests
Listing 'backend/app'...
Listing 'backend/app\\models'...
Listing 'backend/app\\routers'...
Listing 'backend/app\\scheduling'...
Listing 'backend/app\\schemas'...
Listing 'backend/app\\services'...
Listing 'backend/tests'...
Listing 'backend/tests\\routers'...
Listing 'backend/tests\\services'...
```

**Backend focused tests**: ✅ 14 passed, 1 warning
```text
$env:DATABASE_URL='sqlite:///C:/Users/pedro.melgar/AppData/Local/Temp/opencode/planilla_docentes_verify.sqlite';
$env:ASYNC_DATABASE_URL='sqlite+aiosqlite:///C:/Users/pedro.melgar/AppData/Local/Temp/opencode/planilla_docentes_verify.sqlite';
python -m pytest backend/tests/services/test_teacher_photo_service.py backend/tests/routers/test_teachers_photo_routes.py backend/tests/routers/test_docente_portal_permissions.py

collected 14 items
backend\tests\services\test_teacher_photo_service.py ....                [ 28%]
backend\tests\routers\test_teachers_photo_routes.py ...                  [ 50%]
backend\tests\routers\test_docente_portal_permissions.py .......         [100%]
======================== 14 passed, 1 warning in 7.08s ========================
```

**Frontend lint**: ✅ Passed
```text
npm run lint
> frontend@0.0.0 lint
> eslint .
```

**Frontend build**: ✅ Passed with bundle-size warning
```text
npm run build
> frontend@0.0.0 build
> tsc -b && vite build

✓ 2560 modules transformed.
dist/assets/index-CoGVsOQe.js   1,187.60 kB │ gzip: 323.57 kB
(!) Some chunks are larger than 500 kB after minification.
✓ built in 2.98s
```

**Coverage**: ➖ Not available — no coverage command configured/executed for this verify phase.

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Admin manages docente profile photo lifecycle | Admin uploads or replaces photo | `backend/tests/routers/test_teachers_photo_routes.py::test_admin_upload_replace_and_delete_teacher_photo` | ✅ COMPLIANT |
| Admin manages docente profile photo lifecycle | Admin removes photo | `backend/tests/routers/test_teachers_photo_routes.py::test_admin_upload_replace_and_delete_teacher_photo` | ✅ COMPLIANT |
| Avatar display uses photo with initials fallback | Photo exists | `backend/tests/routers/test_docente_portal_permissions.py::test_docente_profile_response_includes_permissions_and_avatar_url`, `::test_auth_payloads_include_docente_avatar_url`; frontend lint/build for contract wiring | ✅ COMPLIANT |
| Avatar display uses photo with initials fallback | No photo exists | `backend/tests/routers/test_teachers_photo_routes.py::test_admin_upload_replace_and_delete_teacher_photo`, `backend/tests/routers/test_docente_portal_permissions.py::test_docente_photo_upload_replace_and_delete_when_permission_enabled`; frontend fallback inspected in `Header.tsx`, `MyProfilePage.tsx`, `TeacherDetailPage.tsx` and build passed | ⚠️ PARTIAL — backend null-avatar behavior passed; no browser/UI runtime smoke was executed |
| Admin controls docente self-edit permissions | Admin updates settings | `backend/tests/routers/test_docente_portal_permissions.py::test_admin_settings_expose_and_update_docente_permission_flags` | ✅ COMPLIANT |
| Backend enforces docente edit authorization | Profile edit blocked by setting | `backend/tests/routers/test_docente_portal_permissions.py::test_docente_profile_update_is_blocked_when_permission_disabled` | ✅ COMPLIANT |
| Backend enforces docente edit authorization | Profile edit allowed by setting | `backend/tests/routers/test_docente_portal_permissions.py::test_docente_profile_update_is_allowed_when_permission_enabled` | ✅ COMPLIANT |
| Backend enforces docente photo authorization | Photo mutation blocked by setting | `backend/tests/routers/test_docente_portal_permissions.py::test_docente_photo_mutations_are_blocked_when_permission_disabled` | ✅ COMPLIANT |
| Backend enforces docente photo authorization | Photo mutation allowed by setting | `backend/tests/routers/test_docente_portal_permissions.py::test_docente_photo_upload_replace_and_delete_when_permission_enabled` | ✅ COMPLIANT |
| Image upload validation is safe and strict | Invalid file type | `backend/tests/services/test_teacher_photo_service.py::test_save_upload_file_rejects_invalid_content_type`, `backend/tests/routers/test_teachers_photo_routes.py::test_admin_photo_upload_rejects_invalid_type_without_mutating` | ✅ COMPLIANT |
| Image upload validation is safe and strict | Oversized file | `backend/tests/services/test_teacher_photo_service.py::test_save_upload_file_rejects_oversized_file`, `backend/tests/routers/test_teachers_photo_routes.py::test_admin_photo_upload_rejects_oversized_without_mutating` | ✅ COMPLIANT |

**Compliance summary**: 10/11 scenarios fully compliant; 1/11 partially compliant due missing interactive UI smoke for initials fallback. All backend behavioral scenarios have passing runtime tests.

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| Admin photo lifecycle | ✅ Implemented | `backend/app/routers/teachers.py` exposes admin `PUT/DELETE /api/teachers/{ci}/photo`, commits metadata before best-effort old-file deletion, and no longer rolls back on intentional `HTTPException` paths in photo routes. |
| Avatar photo/reference exposure | ✅ Implemented | `Teacher.avatar_url`, `TeacherResponse.avatar_url`, portal profile, auth payloads, and frontend avatar rendering are wired. |
| Admin permission flags | ✅ Implemented | `DOCENTE_CAN_EDIT_PROFILE` and `DOCENTE_CAN_EDIT_PHOTO` defaults/getters/setters exist and are exposed through admin settings. |
| Backend profile edit gate | ✅ Implemented | `PUT /api/portal/profile` returns 403 when `get_docente_can_edit_profile()` is false. |
| Backend photo mutation gate | ✅ Implemented | `PUT/DELETE /api/portal/profile/photo` return 403 when `get_docente_can_edit_photo()` is false; photo routes avoid rollback on intentional `HTTPException` paths. |
| Safe image validation | ✅ Implemented | Service accepts JPEG/PNG/WebP extensions and MIME types, enforces 2 MiB max, rejects empty files, and uses UUID filenames. |
| Frontend permission-aware UI | ✅ Implemented | `MyProfilePage.tsx`, `SettingsPage.tsx`, `TeacherDetailPage.tsx`, `Header.tsx`, and API hooks/types are wired; lint/build passed. |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Local files + teacher photo metadata | ✅ Yes | Model fields and Alembic/runtime migration are present. |
| Serve `/uploads/teacher-photos` via StaticFiles | ✅ Yes | Mounted in `backend/app/main.py`; Vite dev proxy includes `/uploads`. |
| JPEG/PNG/WebP, 2 MiB validation | ✅ Yes | Enforced in `teacher_photo_service.py`; frontend file inputs mirror accepted types. |
| Commit DB before best-effort cleanup | ✅ Yes | Admin/docente replace/delete routes commit before `delete_photo_file(old_filename)`. |
| Global permission settings default false | ✅ Yes | Defaults and startup seed use `false`. |
| Alembic + runtime migration | ✅ Yes | Revision `7d52c8e1a4f3_add_teacher_profile_photos.py` plus `_run_column_migrations()` are present. |

### Issues Found
**CRITICAL**: None.

**WARNING**:
- Frontend build emits Vite's large chunk warning for `index-CoGVsOQe.js` at ~1.19 MB minified. This is not a functional failure, but bundle splitting should be considered later.
- Initials fallback is verified by source inspection plus successful frontend lint/build, and backend null-avatar behavior has passing tests, but no interactive browser smoke/UI runtime test was executed in this shell verify.

**SUGGESTION**:
- Run manual browser smoke before/after archive if an interactive environment is available: admin upload/change/delete, docente upload/delete with permission enabled, disabled-state messaging with settings off, and broken/missing-image fallback.
- Consider adding a lightweight frontend component test for avatar image error fallback to turn the current UI smoke recommendation into automated coverage.

### Verdict
PASS WITH WARNINGS

The change satisfies the SDD backend behavioral requirements with passing focused pytest, compileall, lint, and production build evidence. Remaining findings are non-blocking quality/verification warnings around frontend bundle size and manual/UI smoke coverage.
