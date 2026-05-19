# Proposal: Docente Profile Photos and Permissions

## Intent

Allow admins to upload a docente profile photo and use it as the docente avatar. Add admin-controlled permissions so docentes may be allowed or blocked from editing their own profile data and from uploading/changing their own photo.

## Scope

### In Scope
- Add docente photo/avatar support linked to `teachers`.
- Admin upload/change/remove docente photos.
- Global settings for `DOCENTE_CAN_EDIT_PROFILE` and `DOCENTE_CAN_EDIT_PHOTO`.
- Backend enforcement of docente edit/photo permissions.
- Frontend profile/header avatar display with initials fallback.

### Out of Scope
- Per-docente or per-field permission rules.
- External object storage/CDN integration.
- Image cropping/editor UX beyond basic upload validation.

## Capabilities

### New Capabilities
- `docente-profile-management`: Covers docente profile data, avatar/photo lifecycle, and admin-configurable self-service permissions.

### Modified Capabilities
- None — `openspec/specs/` has no existing capability specs to update.

## Approach

Store photo metadata/path on `teachers` and serve validated image assets through backend-controlled URLs. Reuse `app_settings` for global permission flags, expose `avatar_url` in docente profile responses, and enforce permissions in API routes before accepting docente profile/photo mutations. UI should hide disabled actions but rely on server checks as the source of truth.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/models/teacher.py` | Modified | Add photo/avatar fields. |
| `backend/main.py` / migrations | Modified | Add DB migration/runtime compatibility for new columns. |
| `backend/services/app_settings_service.py` | Modified | Add default permission settings. |
| `backend/routers/admin_settings.py` | Modified | Expose/administer new flags. |
| `backend/routers/teachers.py` / admin photo route | Modified/New | Admin photo upload/change/remove. |
| `backend/routers/docente_portal.py` | Modified | Return avatar URL and enforce docente permissions. |
| `frontend/src/api/types.ts` | Modified | Add avatar/settings fields. |
| `frontend/src/pages/MyProfilePage.tsx` | Modified | Show avatar and conditionally allow edits/photo upload. |
| `frontend/src/components/layout/Header.tsx` | Modified | Use uploaded avatar with initials fallback. |
| `frontend/src/pages/SettingsPage.tsx` | Modified | Add toggles for docente permissions. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Unsafe image upload/serving | Med | Validate type/size, sanitize filenames, store outside executable paths. |
| UI/API permission mismatch | Med | Enforce flags server-side; UI only mirrors state. |
| Settings cache staleness | Low | Use existing invalidation/update pattern. |
| Runtime migration startup issue | Low | Keep additive nullable fields and safe defaults. |

## Rollback Plan

Disable both new settings, hide upload UI, and revert API/UI changes. Leave nullable photo columns/files unused, or run a cleanup migration after confirming no rollback is needed.

## Dependencies

- Existing auth roles and `app_settings` infrastructure.
- Local/server file storage path for uploaded images.

## Success Criteria

- [ ] Admin can upload/change/remove a docente photo.
- [ ] Uploaded photo appears in docente profile and header avatar.
- [ ] Docente profile edits are blocked when `DOCENTE_CAN_EDIT_PROFILE=false`.
- [ ] Docente photo uploads are blocked when `DOCENTE_CAN_EDIT_PHOTO=false`.
- [ ] Initials fallback remains when no photo exists.
