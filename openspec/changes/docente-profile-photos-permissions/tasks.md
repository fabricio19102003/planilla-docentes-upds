# Tasks: Docente Profile Photos and Permissions

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 520-760 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (backend photo infra+admin APIs) → PR 2 (docente permissions+portal/auth wiring) → PR 3 (frontend UI/settings wiring+verification) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Add teacher photo storage, static serving, admin photo lifecycle endpoints | PR 1 | Base: main; includes backend integration tests |
| 2 | Enforce docente edit/photo flags in portal and auth/profile payloads | PR 2 | Base: PR 1; includes backend permission tests |
| 3 | Wire frontend avatar/settings/profile/admin detail flows and run quality checks | PR 3 | Base: PR 2; includes `tsc -b`, `vite build`, manual smoke checklist |

## Phase 1: Infrastructure

- [x] 1.1 Add `teachers.photo_filename`, `photo_content_type`, `photo_updated_at` in `backend/app/models/teacher.py` and Alembic revision `backend/alembic/versions/*_teacher_profile_photos.py`.
- [x] 1.2 Extend runtime migration in `backend/app/main.py` to backfill nullable photo columns safely for existing DBs.
- [x] 1.3 Create `backend/app/services/teacher_photo_service.py` for MIME/ext/size validation (2 MiB), UUID naming, save/replace/remove, avatar URL builder.
- [x] 1.4 Mount `settings.UPLOAD_DIR/teacher-photos` via `StaticFiles` in `backend/app/main.py` and ensure directory creation on startup.

## Phase 2: Core Implementation

- [x] 2.1 Add admin photo routes in `backend/app/routers/teachers.py`: `PUT /api/teachers/{ci}/photo` (multipart) and `DELETE /api/teachers/{ci}/photo` with best-effort old-file cleanup.
- [ ] 2.2 Add `DOCENTE_CAN_EDIT_PROFILE` and `DOCENTE_CAN_EDIT_PHOTO` defaults/getters/setters in `backend/app/services/app_settings_service.py` and expose in `backend/app/routers/admin_settings.py`.
- [ ] 2.3 Enforce profile edit gate in `backend/app/routers/docente_portal.py` (`PUT /profile` returns 403 when disabled).
- [ ] 2.4 Add docente own-photo routes in `backend/app/routers/docente_portal.py`: `PUT/DELETE /api/portal/profile/photo`, gated by photo setting.
- [ ] 2.5 Add `avatar_url` to backend contracts in `backend/app/schemas/teacher.py`, `backend/app/schemas/auth.py`, and `backend/app/routers/auth.py` responses.

## Phase 3: Integration and Frontend Wiring

- [ ] 3.1 Update `frontend/src/api/types.ts` for `avatar_url`, docente permission settings, and photo upload payload/response shapes.
- [ ] 3.2 Extend `frontend/src/api/hooks/useTeachers.ts`, `useAppSettings.ts`, and `useAuth.ts` with photo/settings mutations plus query invalidation.
- [ ] 3.3 Update `frontend/src/components/layout/Header.tsx` to render uploaded avatar image with initials fallback on missing/error.
- [ ] 3.4 Update `frontend/src/pages/MyProfilePage.tsx` to conditionally allow profile edits/photo actions from settings and show disabled-state messaging.
- [ ] 3.5 Update `frontend/src/pages/TeacherDetailPage.tsx` for admin upload/change/remove docente photo controls.
- [ ] 3.6 Update `frontend/src/pages/SettingsPage.tsx` to manage both docente permission toggles with helper text.

## Phase 4: Testing and Verification

- [x] 4.1 Add backend unit tests for photo validation and service lifecycle paths in `backend/tests/services/test_teacher_photo_service.py`.
- [x] 4.2 Add backend integration tests for admin upload/replace/remove, invalid type/size 400, and avatar URL presence in `backend/tests/routers/test_teachers_photo_routes.py`.
- [ ] 4.3 Add backend integration tests for docente permission enforcement (`DOCENTE_CAN_EDIT_PROFILE`, `DOCENTE_CAN_EDIT_PHOTO`) in `backend/tests/routers/test_docente_portal_permissions.py`.
- [ ] 4.4 Run `pytest` (backend), `tsc -b`, and `vite build` (frontend); record manual smoke checks for avatar fallback and toggle behavior.
