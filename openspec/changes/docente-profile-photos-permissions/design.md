# Design: Docente Profile Photos and Permissions

## Technical Approach

Add nullable photo metadata to `teachers`, store validated images under `settings.UPLOAD_DIR/teacher-photos`, expose public backend-served avatar URLs, and enforce docente self-service permissions in portal routes. Admin remains able to manage any docente photo regardless of the self-service flags.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| Storage | Local files + `teachers.photo_filename`, `photo_content_type`, `photo_updated_at` | BLOBs; external object storage | Matches current local upload model and keeps DB small; external storage is out of scope. |
| Serving | Mount `/uploads/teacher-photos` with `StaticFiles`; expose `avatar_url` built from filename | JWT-protected image endpoint | `<img>` cannot send current bearer token reliably; UUID filenames avoid exposing CI and keep UI simple. |
| Validation | Accept MIME `image/jpeg`, `image/png`, `image/webp`; extensions `.jpg`, `.jpeg`, `.png`, `.webp`; max `2 MiB` | Larger files; SVG/GIF | Small enough for avatars, avoids SVG script risk and animated GIF abuse. |
| Cleanup | On replace/remove, commit DB change first, then best-effort delete old file; orphan cleanup can be manual | Delete before commit | Prevents broken DB references if commit fails. Best-effort deletion avoids failing user action because filesystem cleanup failed. |
| Permissions | Global app settings `DOCENTE_CAN_EDIT_PROFILE`, `DOCENTE_CAN_EDIT_PHOTO`, default `false` | Per-docente settings | Spec asks for global admin toggles; default closed is safer for payroll/profile data. |
| Migration | Add Alembic revision and extend `_run_column_migrations()` | Runtime only | Project already uses runtime column migration for existing DBs, but Alembic keeps schema history honest. |

## Data Flow

```text
Admin/Docente upload ─→ FastAPI route ─→ validate MIME/ext/size
                   └─→ save UUID file ─→ update teachers photo fields ─→ commit
                                                  └─→ delete old file best-effort

Profile/Auth/Teacher API ─→ avatar_url from photo_filename ─→ React Avatar img
                                                └─→ initials fallback when null/error
```

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/app/models/teacher.py` | Modify | Add nullable photo metadata columns. |
| `backend/app/schemas/teacher.py` | Modify | Include `avatar_url` in teacher responses. |
| `backend/app/services/teacher_photo_service.py` | Create | Validate, save, replace/remove, build avatar URL. |
| `backend/app/config.py` | Modify | Add avatar validation constants or reuse hardcoded service constants. |
| `backend/app/main.py` | Modify | Mount static photo directory; runtime column migration; seed new settings. |
| `backend/alembic/versions/*_teacher_profile_photos.py` | Create | Add photo columns. |
| `backend/app/services/app_settings_service.py` | Modify | Add keys/getters for both docente edit flags. |
| `backend/app/routers/admin_settings.py` | Modify | Expose/update boolean settings. |
| `backend/app/routers/teachers.py` | Modify | Admin `PUT /api/teachers/{ci}/photo`, `DELETE /api/teachers/{ci}/photo`; cleanup on delete. |
| `backend/app/routers/docente_portal.py` | Modify | Return `avatar_url`; block `PUT /profile` when profile flag false; add own photo PUT/DELETE gated by photo flag. |
| `backend/app/routers/auth.py`, `backend/app/schemas/auth.py` | Modify | Include docente `avatar_url` in login/me user payload for Header. |
| `frontend/src/api/types.ts` | Modify | Add avatar/settings/photo upload types. |
| `frontend/src/api/hooks/useAuth.ts`, `useTeachers.ts`, `useAppSettings.ts` | Modify | Add profile/photo mutations and query invalidation. |
| `frontend/src/components/layout/Header.tsx` | Modify | Render image avatar with initials fallback. |
| `frontend/src/pages/MyProfilePage.tsx` | Modify | Avatar card; hide/disable profile/photo edits based on flags. |
| `frontend/src/pages/SettingsPage.tsx` | Modify | Add two permission toggles with clear help text. |
| `frontend/src/pages/TeacherDetailPage.tsx` | Modify | Admin upload/change/remove docente photo. |

## Interfaces / Contracts

- `TeacherResponse.avatar_url: str | null`; `ProfileResponse.avatar_url: str | null`; `AuthUser.avatar_url?: string | null`.
- `SettingsResponse.docente_can_edit_profile: bool`, `docente_can_edit_photo: bool`; update payload accepts same optional booleans.
- Admin photo API: `PUT /api/teachers/{ci}/photo` multipart `file`; `DELETE /api/teachers/{ci}/photo`.
- Docente photo API: `PUT /api/portal/profile/photo`; `DELETE /api/portal/profile/photo`.
- Rejection statuses: invalid type/size `400`; disabled docente permission `403`.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | Photo validation and cleanup paths | pytest with temp upload dir and fake `UploadFile`. |
| Integration | Admin upload/replace/remove; docente flags enforced; avatar_url appears | FastAPI TestClient/httpx + DB session fixtures. |
| Frontend quality | Type safety and build | `tsc -b` and `vite build`; manual UI smoke for avatar fallback and toggles. |

## Migration / Rollout

Add nullable columns and default app settings. Existing docentes show initials until a photo is uploaded. No destructive data migration required.

## Open Questions

- [ ] Should old avatar files be periodically swept from disk, or is best-effort delete sufficient for this deployment?
