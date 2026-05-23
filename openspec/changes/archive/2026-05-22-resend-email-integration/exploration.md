## Exploration: resend-email-integration

### Current State
El backend es FastAPI monolítico por capas ligeras (routers/services/models). No existe integración saliente de email hoy: al publicar facturación (`POST /api/billing/publish`) se crean notificaciones internas en DB (`notifications`) para docentes, visibles por endpoints del portal (`/api/portal/notifications*`).

La configuración central usa `Settings` de `pydantic-settings` en `backend/app/config.py` (lee `.env` con `case_sensitive=True`). `requirements.txt` ya incluye `httpx`, pero no `resend`.

### Affected Areas
- `backend/app/config.py` — agregar variables de configuración de Resend (API key, sender, flags de habilitación).
- `backend/app/routers/billing_publication.py` — punto de disparo natural para primer caso de uso (publicación de facturación).
- `backend/app/models/notification.py` — permanece como canal interno; email debe complementar, no reemplazar.
- `backend/app/routers/docente_portal.py` — referencia funcional del consumo de notificaciones actuales (para mantener comportamiento existente).
- `backend/requirements.txt` — solo si se elige SDK (`resend`).
- `backend/tests/` — no hay pruebas específicas de billing publication; se deben crear pruebas de integración de flujo con mailer desacoplado.

### Approaches
1. **Resend Python SDK** — usar `resend` package y `resend.Emails.send(...)`.
   - Pros: API oficial tipada para Python, menor código HTTP propio, actualización semántica alineada con proveedor.
   - Cons: dependencia nueva adicional; testing requiere mock sobre SDK global (`resend.api_key` + llamada estática).
   - Effort: Medium.

2. **HTTP directo con `httpx`** — invocar `POST https://api.resend.com/emails` con `Authorization: Bearer ...`.
   - Pros: sin nuevas dependencias, reutiliza `httpx` ya instalado, control explícito de timeouts/retries/logging y fácil test por transporte mockeado.
   - Cons: más código de bajo nivel (headers, payload, parseo de errores), mayor superficie de mantenimiento propia.
   - Effort: Low/Medium.

### Recommendation
**Elegir HTTP directo con `httpx` para el primer slice.**

Razón: el proyecto ya usa stack simple y no tiene capa de proveedores externos aún; para un alcance inicial mínimo conviene introducir una abstracción chica (`email_service`) sin sumar dependencia nueva. Esto reduce riesgo de integración, acelera pruebas y deja puerta abierta para migrar a SDK luego sin romper contratos internos.

**Primer alcance útil (intencionalmente pequeño):**
- Evento único: publicación de facturación exitosa.
- Destinatarios: solo docentes activos con email válido.
- Canal: mantener notificación interna existente y **agregar** email best-effort (si falla email, no revierte publicación).
- Observabilidad: log estructurado con conteos `eligible/sent/failed/skipped`.

### Risks
- **Riesgo de entrega parcial**: publicación puede completar aunque fallen emails; debe quedar explícito en logs y respuesta operativa.
- **Datos incompletos**: algunos docentes pueden no tener email o tener formato inválido.
- **Bloqueo por red**: llamada síncrona a proveedor externo dentro del request puede aumentar latencia.
- **Secretos/config**: con `case_sensitive=True`, `RESEND_API_KEY` mal escrita no se detecta como alias.
- **Remitente no verificado**: Resend rechaza `from` sin dominio/verificación correcta.

### Ready for Proposal
Yes — listo para pasar a propuesta con alcance MVP:
1) infraestructura de configuración + cliente HTTP, 2) integración en `publish_billing`, 3) pruebas de comportamiento (no romper publicación ante falla de email), 4) documentación de variables `.env`.
