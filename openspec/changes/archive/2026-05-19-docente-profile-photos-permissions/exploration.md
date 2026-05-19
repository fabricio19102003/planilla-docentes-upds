# Exploration: Docente Profile Photos and Permissions

## Summary

Explored current profile/photo flows, permission settings, and upload handling to confirm a safe architecture for docente avatars and self-service permission toggles.

## Findings

- Admin-backed photo management fits the existing role model and avoids exposing upload control to docentes when disabled.
- Local file storage plus static serving is consistent with the current deployment model.
- A backend-served `avatar_url` is the simplest client contract for `<img>` rendering and fallback handling.
- Global settings are the right scope for `DOCENTE_CAN_EDIT_PROFILE` and `DOCENTE_CAN_EDIT_PHOTO`; per-docente rules would add complexity without a current requirement.
