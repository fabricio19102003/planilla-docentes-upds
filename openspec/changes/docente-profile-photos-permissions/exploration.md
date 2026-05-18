## Exploration: docente-profile-photos-permissions

### Current State
- **No existe soporte de foto/avatar** en backend ni frontend:
  - `teachers` y `users` no tienen campos de foto (`backend/app/models/teacher.py`, `backend/app/models/user.py`).
  - `/api/portal/profile` devuelve datos de perfil sin URL de imagen (`backend/app/routers/docente_portal.py`).
  - UI usa iniciales como avatar en `MyProfilePage` y `Header` (`frontend/src/pages/MyProfilePage.tsx`, `frontend/src/components/layout/Header.tsx`).
- **Docente puede editar su perfil siempre** via `PUT /api/portal/profile` sin feature flag (`backend/app/routers/docente_portal.py`).
- **Infra de settings ya existe** con `app_settings` (DB key/value), cacheada por `app_settings_service`, expuesta en `GET/PUT /api/admin/settings` y editable en `SettingsPage`.
- **Infra de uploads existe parcialmente** para Excel/JSON (`/api/teachers/upload`), pero no para imágenes ni serving público/versionado de archivos.

### Affected Areas
- `backend/app/models/teacher.py` — necesitaría persistir referencia de foto (ej. path/url).
- `backend/app/models/user.py` (opcional) — solo si se decide foto por usuario en vez de por docente.
- `backend/app/main.py` — runtime migration para nueva columna(s) y seed de nuevos settings.
- `backend/app/services/app_settings_service.py` — nuevas keys booleanas para permisos (`docente_edit_profile`, `docente_edit_photo`) y parseo robusto bool.
- `backend/app/routers/admin_settings.py` — incluir flags en response/update para control admin.
- `backend/app/routers/teachers.py` o nuevo router admin de fotos — endpoint admin para subir/reemplazar foto de docente.
- `backend/app/routers/docente_portal.py` —
  - incluir `avatar_url` en `GET /portal/profile`;
  - condicionar `PUT /portal/profile` por setting;
  - opcionalmente exponer endpoint docente para cambiar su foto, condicionado por setting.
- `frontend/src/api/types.ts` — ampliar tipos de profile/settings con `avatar_url` y flags.
- `frontend/src/api/hooks/useAuth.ts` + `useAppSettings` hooks — mutaciones/queries para foto y flags.
- `frontend/src/pages/MyProfilePage.tsx` — reemplazar avatar de inicial por imagen fallback + bloquear/ocultar edición según permisos.
- `frontend/src/components/layout/Header.tsx` y potencialmente `Sidebar` — usar imagen de perfil cuando exista.
- `frontend/src/pages/SettingsPage.tsx` — agregar toggles admin para permisos de edición de perfil/foto.

### Approaches
1. **Foto en `teachers` + permisos en `app_settings` (recomendado)**
   - Descripción: guardar `avatar_path/avatar_url` en tabla `teachers`, agregar endpoint admin para upload, y dos flags globales en `app_settings` para habilitar/deshabilitar edición docente.
   - Pros:
     - Encaja con modelo actual donde identidad docente vive en `teachers` y usuario docente se vincula por `teacher_ci`.
     - Menor impacto en auth (`/auth/me` no necesita ser fuente de avatar obligatoria).
     - Reusa patrón de configuración existente (admin settings + cache + audit log).
   - Cons:
     - Requiere resolver storage/serving de archivos (ruta local + endpoint de descarga o static mount controlado).
     - Si hay múltiples usuarios apuntando al mismo `teacher_ci`, comparten foto (normalmente deseado, pero hay que explicitarlo).
   - Effort: **Medium**.

2. **Foto en `users` + permisos en `app_settings`**
   - Descripción: avatar por cuenta de usuario (`users.avatar_*`), no por docente.
   - Pros:
     - Modelo más estándar “avatar de cuenta”.
   - Cons:
     - Inconsistencia con dominio actual (portal/profile usa `teacher` como fuente principal).
     - Más cambios en auth context (`/auth/me`, refresh global) y potencial duplicación con datos de docente.
   - Effort: **Medium/High**.

### Recommendation
Usar **Approach 1**: foto en `teachers` + **dos flags globales** en `app_settings`.

Decisiones de exploración para propuesta:
- `DOCENTE_CAN_EDIT_PROFILE` (bool): controla `PUT /portal/profile`.
- `DOCENTE_CAN_EDIT_PHOTO` (bool): controla endpoint docente de cambio de foto.
- Upload admin dedicado (por CI de docente) que también registre actividad.
- `GET /portal/profile` debe devolver `avatar_url` para alimentar `MyProfilePage` y `Header`.
- Mantener fallback visual por iniciales cuando no exista foto.

### Risks
- **Storage/serving**: hoy no hay convención explícita para servir imágenes de perfil; hay que definir ruta, naming seguro y límites de archivo (tipo/tamaño).
- **Migraciones runtime**: patrón actual usa `ALTER TABLE` en `main.py`; cualquier error afecta startup.
- **Cache de settings en multi-worker**: ya existe riesgo documentado en `app_settings_service`; cambios de permisos pueden no propagarse instantáneamente entre workers.
- **Permisos UX/API desalineados**: si frontend oculta edición pero backend no valida flag, hay bypass por API; validación debe ser server-side.
- **Privacidad**: evitar exponer rutas internas del filesystem; preferir URL controlada por endpoint.

### Ready for Proposal
**Yes** — hay suficiente información para redactar proposal con alcance, API contracts, migraciones, validaciones y rollback.
