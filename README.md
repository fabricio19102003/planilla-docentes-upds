# SIPAD — Sistema Integrado de Pago Docente

<p align="center">
  <strong>Sistema web para la gestión integral de pagos docentes</strong><br>
  Universidad Privada Domingo Savio (UPDS) — Sede Cobija, Pando, Bolivia
</p>

---

## Descripcion General

SIPAD procesa designaciones docentes, datos biometricos de asistencia y genera planillas de pago con calculo automatizado. Incluye retencion RC-IVA 13%, ajustes manuales del admin, publicacion de facturacion para docentes, generacion de contratos PDF, reportes multiples, auditoria de asistencia y registro completo de actividad.

## Stack Tecnologico

| Capa | Tecnologia |
|------|-----------|
| **Backend** | Python 3.11 · FastAPI · SQLAlchemy · PostgreSQL |
| **Frontend** | React 19 · TypeScript · Vite · Tailwind CSS 4 · Shadcn UI |
| **PDFs** | ReportLab 4.4 |
| **Graficos** | Recharts |
| **Exportacion** | html-to-image (PNG) · openpyxl (Excel parsing) · xlrd (XLS parsing) |
| **Autenticacion** | JWT (PyJWT) · bcrypt |

## Guia Rapida (TL;DR)

Si ya tenes todo instalado (Python, Node, PostgreSQL) y solo queres arrancar:

```bash
# 1. Crear la BD (una sola vez)
createdb planilla_docentes_upds

# 2. Backend (Terminal 1)
cd backend
python -m venv venv          # solo la primera vez
venv\Scripts\activate        # Windows CMD (o .\venv\Scripts\Activate.ps1 en PowerShell)
pip install -r requirements.txt  # solo la primera vez
cp .env.example .env         # solo la primera vez — editar con tu password de PostgreSQL
uvicorn app.main:app --reload --port 8000

# 3. Frontend (Terminal 2)
cd frontend
npm install                  # solo la primera vez
npm run dev
```

Abri http://localhost:5173 y logueate con cualquiera de los 3 admins que se crean automaticamente:

| Usuario | Contraseña |
|---------|-----------|
| `admin` | `Admin123` |
| `daniel` | `Admin123` |
| `pedro` | `Admin123` |

---

## Requisitos Previos

- **Python 3.11+** ([descargar](https://www.python.org/downloads/))
- **Node.js 18+** y npm ([descargar](https://nodejs.org/))
- **PostgreSQL 14+** corriendo localmente (con `pg_dump` accesible en PATH para backups)
- Git

## Instalacion Paso a Paso

### 1. Clonar el repositorio

```bash
git clone https://github.com/fabricio19102003/planilla-docentes-upds.git
cd planilla-docentes-upds
```

### 2. Base de datos PostgreSQL

Asegurate de tener PostgreSQL corriendo. Luego crea la base de datos:

```bash
# Desde cualquier terminal con acceso a PostgreSQL
createdb planilla_docentes_upds
```

> Si usas pgAdmin, crea una base de datos llamada `planilla_docentes_upds` manualmente.

### 3. Backend (Python + FastAPI)

#### 3.1 Crear el entorno virtual

El entorno virtual aisla las dependencias del proyecto para no afectar tu sistema.

```bash
cd backend

# Crear el entorno virtual (solo la primera vez)
python -m venv venv
```

> Esto crea una carpeta `venv/` dentro de `backend/`. **No la subas a git** (ya esta en `.gitignore`).

#### 3.2 Activar el entorno virtual

**Hay que activar el entorno virtual CADA VEZ que abras una terminal nueva** para trabajar con el backend.

**Windows (CMD):**
```cmd
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

> Si PowerShell te bloquea con un error de "execution policy", ejecuta primero:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

**Linux / macOS:**
```bash
source venv/bin/activate
```

Sabras que esta activo cuando veas `(venv)` al inicio de la linea de tu terminal:
```
(venv) C:\...\backend>
```

#### 3.3 Instalar dependencias

Con el entorno virtual activo:

```bash
pip install -r requirements.txt
```

#### 3.4 Configurar variables de entorno

```bash
# Copiar el archivo de ejemplo
cp .env.example .env
```

Edita `backend/.env` con los datos de **tu** PostgreSQL local:

```env
# Reemplaza "tu_password" con la contraseña de tu usuario postgres
DATABASE_URL=postgresql+psycopg2://postgres:tu_password@localhost:5432/planilla_docentes_upds
ASYNC_DATABASE_URL=postgresql+asyncpg://postgres:tu_password@localhost:5432/planilla_docentes_upds
```

> Las demas variables ya vienen con valores por defecto funcionales. Solo necesitas cambiar la contraseña de PostgreSQL.

### 4. Frontend (React + Vite)

```bash
cd frontend
npm install
```

## Configuracion

### Variables de entorno (`backend/.env`)

```env
# ─── Base de datos PostgreSQL ──────────────────────────────
DATABASE_URL=postgresql+psycopg2://postgres:tu_password@localhost:5432/planilla_docentes_upds
ASYNC_DATABASE_URL=postgresql+asyncpg://postgres:tu_password@localhost:5432/planilla_docentes_upds

# ─── CORS ──────────────────────────────────────────────────
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# ─── JWT — CAMBIAR en produccion ───────────────────────────
JWT_SECRET=tu-clave-secreta-segura-cambiar-en-produccion

# ─── Uploads ───────────────────────────────────────────────
UPLOAD_DIR=./data/uploads

# ─── Admin Bootstrap ──────────────────────────────────────
# Contraseña para los admins por defecto (admin, daniel, pedro)
# Debe cumplir: 8+ chars, 1 mayuscula, 1 minuscula, 1 numero
ADMIN_DEFAULT_PASSWORD=Admin123

# ─── Periodo Academico ────────────────────────────────────
ACTIVE_ACADEMIC_PERIOD=I/2026

# ─── Tarifa ───────────────────────────────────────────────
HOURLY_RATE=70
```

### Primer inicio (seed automatico)

Al iniciar el backend por primera vez con una base de datos vacia:

1. Se crean todas las tablas automaticamente
2. Se ejecutan las migraciones de columnas nuevas
3. Se crean **3 usuarios admin** por defecto (si `ADMIN_DEFAULT_PASSWORD` esta configurado):

| Usuario | Contraseña | Rol |
|---------|-----------|-----|
| `admin` | `Admin123` | Admin |
| `daniel` | `Admin123` | Admin |
| `pedro` | `Admin123` | Admin |

4. Se vinculan usuarios docentes a sus docentes correspondientes

> **Nota:** En el primer login el sistema pide cambiar la contraseña. Todos los admins seed tienen `must_change_password=true`.

## Ejecucion

Necesitas **dos terminales** corriendo simultaneamente.

### Terminal 1 — Backend

**Paso 1:** Abri una terminal y navega a la carpeta del backend:

```bash
cd backend
```

**Paso 2:** Activa el entorno virtual:

**Windows (CMD):**
```cmd
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

Confirma que esta activo — vas a ver `(venv)` en la terminal:
```
(venv) C:\...\backend>
```

**Paso 3:** Levanta el servidor:

```bash
uvicorn app.main:app --reload --port 8000
```

Si todo funciona vas a ver algo como:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Created 3 default admin(s): admin, daniel, pedro (must change password on first login)
```

> Si ves errores de conexion a la BD, revisa la seccion de [Troubleshooting](#troubleshooting-comun).

### Terminal 2 — Frontend

**Paso 1:** Abri una **segunda** terminal (dejando el backend corriendo en la primera):

```bash
cd frontend
```

**Paso 2:** Levanta el servidor de desarrollo:

```bash
npm run dev
```

Vas a ver:
```
VITE v6.x.x  ready in xxx ms

➜  Local:   http://localhost:5173/
```

### Listo — Acceder al sistema

1. Abri el navegador en **http://localhost:5173**
2. Ingresa con cualquiera de estos usuarios:

| Usuario | Contraseña |
|---------|-----------|
| `admin` | `Admin123` |
| `daniel` | `Admin123` |
| `pedro` | `Admin123` |

3. En el primer login te va a pedir cambiar la contraseña — esto es normal y por seguridad.

### URLs

| Servicio | URL |
|----------|-----|
| **Frontend** | http://localhost:5173 |
| **Backend API** | http://localhost:8000 |
| **Swagger (docs API)** | http://localhost:8000/docs |

### Build de produccion

```bash
cd frontend
npm run build
# Los archivos estaticos quedan en frontend/dist/
```

### Troubleshooting comun

| Problema | Solucion |
|----------|----------|
| `uvicorn: command not found` | No activaste el entorno virtual. Ejecuta `venv\Scripts\activate` primero. |
| `ModuleNotFoundError` | No instalaste las dependencias. Ejecuta `pip install -r requirements.txt` con el venv activo. |
| PowerShell bloquea la activacion | Ejecuta `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `connection refused` al PostgreSQL | Verifica que PostgreSQL esta corriendo y que la contraseña en `.env` es correcta. |
| No se crean los admins al iniciar | Verifica que `ADMIN_DEFAULT_PASSWORD=Admin123` esta en tu archivo `backend/.env`. |
| El frontend no conecta al backend | Asegurate de que el backend esta corriendo en el puerto 8000 antes de usar el frontend. |

## Estructura del Proyecto

```
planilla-docentes-upds/
├── backend/
│   ├── app/
│   │   ├── models/              # 11 modelos SQLAlchemy
│   │   │   ├── teacher.py               # Docente (CI, nombre, email, banco, NIT)
│   │   │   ├── designation.py           # Designacion (materia, grupo, horario, periodo)
│   │   │   ├── attendance.py            # Registro de asistencia
│   │   │   ├── biometric.py             # Datos biometricos (upload + records)
│   │   │   ├── planilla.py              # Planilla generada (con overrides)
│   │   │   ├── billing_publication.py   # Publicacion de facturacion (snapshot inmutable)
│   │   │   ├── user.py                  # Usuarios (admin/docente, must_change_password)
│   │   │   ├── notification.py          # Notificaciones para docentes
│   │   │   ├── detail_request.py        # Solicitudes docente→admin
│   │   │   ├── activity_log.py          # Registro de actividad (audit trail)
│   │   │   └── report.py               # Reportes generados
│   │   │
│   │   ├── routers/             # 14 routers FastAPI
│   │   │   ├── auth.py                  # Login, cambio de contrasena
│   │   │   ├── teachers.py              # CRUD docentes + upload lista + bulk delete
│   │   │   ├── designations.py          # Upload designaciones (3 formatos)
│   │   │   ├── biometric.py             # Upload biometrico + date-range detection
│   │   │   ├── attendance.py            # Procesar asistencia + auditoria
│   │   │   ├── planilla.py              # Generar planilla + dashboard + approve/reject + search
│   │   │   ├── billing_publication.py   # Publicar/despublicar facturacion
│   │   │   ├── contracts.py             # Generar contratos PDF
│   │   │   ├── reports.py               # Generar reportes PDF (7 tipos)
│   │   │   ├── docente_portal.py        # Portal docente completo
│   │   │   ├── detail_requests.py       # Solicitudes admin↔docente
│   │   │   ├── users.py                 # Gestion de usuarios
│   │   │   ├── activity_log.py          # Registro de actividad
│   │   │   └── admin.py                 # Backups de BD
│   │   │
│   │   ├── services/            # Logica de negocio
│   │   │   ├── planilla_generator.py     # Calculo de pagos (Model C + retencion)
│   │   │   ├── attendance_engine.py      # Procesamiento de asistencia
│   │   │   ├── designation_loader.py     # Carga de designaciones (3 formatos + HORARIO parser)
│   │   │   ├── biometric_parser.py       # Parseo de archivos biometricos + CI aliasing
│   │   │   ├── auth_service.py           # Autenticacion + JWT
│   │   │   ├── report_generator.py       # PDFs: financiero, asistencia, comparativo, plantel, incidencias, conciliacion
│   │   │   ├── contract_pdf.py           # PDFs de contratos (17 clausulas legales UPDS)
│   │   │   ├── retention_letter_pdf.py   # Carta de retencion RC-IVA
│   │   │   ├── schedule_pdf.py           # Horario semanal PDF
│   │   │   ├── audit_report_pdf.py       # Auditoria de asistencia PDF (individual + masivo)
│   │   │   └── activity_logger.py        # Helper de logging de actividad
│   │   │
│   │   ├── schemas/             # Pydantic schemas (validacion)
│   │   ├── utils/               # Helpers (auth middleware, normalizacion)
│   │   ├── config.py            # Configuracion (env vars + settings)
│   │   ├── database.py          # Conexion a PostgreSQL
│   │   └── main.py              # App FastAPI + lifespan + migraciones
│   │
│   ├── tests/                   # Test suite (153+ tests)
│   ├── data/
│   │   ├── assets/              # Logos UPDS (isologo + logotipo)
│   │   ├── uploads/             # Archivos subidos
│   │   ├── reports/             # Reportes PDF generados
│   │   ├── contracts/           # Contratos PDF generados
│   │   ├── schedules/           # Horarios PDF
│   │   ├── retention_letters/   # Cartas de retencion
│   │   └── backups/             # Backups de BD (.sql)
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── pages/               # 22 paginas
│   │   │   ├── LoginPage.tsx            # Login split-layout (desktop + mobile)
│   │   │   ├── ForceChangePasswordPage  # Cambio obligatorio de contrasena
│   │   │   ├── DashboardPage.tsx        # Dashboard con Recharts
│   │   │   ├── UploadPage.tsx           # Subir: lista docentes, designacion, biometrico
│   │   │   ├── AttendancePage.tsx        # Procesar asistencia (con auto-deteccion de rango)
│   │   │   ├── AttendanceAuditPage.tsx  # Auditoria de asistencia por docente
│   │   │   ├── PlanillaPage.tsx         # Generar + aprobar + publicar + detalle + override
│   │   │   ├── TeachersPage.tsx         # CRUD docentes + bulk delete
│   │   │   ├── TeacherDetailPage.tsx    # Detalle/edicion de docente
│   │   │   ├── UsersPage.tsx            # Gestion de usuarios
│   │   │   ├── ContractsPage.tsx        # Generacion de contratos PDF
│   │   │   ├── ReportsPage.tsx          # 7 tipos de reportes con preview
│   │   │   ├── AdminRequestsPage.tsx    # Solicitudes de docentes (admin)
│   │   │   ├── ObservationsPage.tsx     # Observaciones de asistencia
│   │   │   ├── ActivityLogPage.tsx      # Registro de actividad
│   │   │   ├── BackupPage.tsx           # Respaldos de BD
│   │   │   ├── BillingPage.tsx          # Facturacion actual (docente)
│   │   │   ├── BillingHistoryPage.tsx   # Historial de facturacion (docente)
│   │   │   ├── MyProfilePage.tsx        # Perfil editable (docente)
│   │   │   ├── SchedulePage.tsx         # Horario semanal con 3 vistas (docente)
│   │   │   ├── RetentionLetterPage.tsx  # Carta de retencion RC-IVA (docente)
│   │   │   ├── MyRequestsPage.tsx       # Mis solicitudes (docente)
│   │   │   └── NotificationsPage.tsx    # Notificaciones (docente)
│   │   │
│   │   ├── components/          # UI components
│   │   │   ├── layout/                  # Layout, Sidebar (colapsable), Header (search + bell)
│   │   │   ├── shared/                  # StatCard, DataTable, FileUploader
│   │   │   └── ui/                      # Shadcn: Button, Dialog, Input, Select, Badge, etc.
│   │   │
│   │   ├── api/                 # API layer
│   │   │   ├── client.ts                # Axios con interceptor JWT
│   │   │   ├── types.ts                 # TypeScript interfaces
│   │   │   └── hooks/                   # 12 hooks TanStack Query
│   │   │
│   │   ├── context/             # React contexts
│   │   │   ├── AuthContext.tsx           # Auth + must_change_password redirect
│   │   │   └── SidebarContext.tsx        # Sidebar collapse state
│   │   │
│   │   └── lib/                 # Utilidades (format, utils)
│   │
│   ├── public/                  # Logos UPDS
│   └── package.json
│
├── Designaciones_UPDS_*.json    # Designacion docente oficial
├── lista_docentes_*.xlsx        # Lista del plantel docente
├── REPORTE DOCENTES *.xls       # Reporte biometrico
└── README.md
```

## Modelo de Negocio

### Modelo de Pago (Model C)

```
Pago Base     = Horas Mensuales Asignadas x Bs 70/hora
Descuento     = Horas Ausentes (verificadas por biometrico) x Bs 70/hora
Bruto         = Pago Base - Descuento
Retencion     = Bruto x 13% (solo docentes con retencion RC-IVA)
Neto          = Bruto - Retencion
```

**Reglas de negocio:**
- Docentes **sin biometrico** = pago completo (0 ausencias asumidas)
- Biometrico scoped al **periodo** (month+year), no historico
- Admin puede aplicar **overrides** manuales al monto de cualquier docente
- Overrides almacenados inmutables en `PlanillaOutput.payment_overrides_json`
- Publicacion crea **snapshot inmutable** — los montos publicados no cambian si los datos base cambian
- El sistema **detecta automaticamente** el rango del biometrico y sugiere las fechas al admin
- **46 docentes** tienen retencion RC-IVA 13%, **87** facturan con NIT propio

### Formatos de designacion soportados

| Formato | Deteccion | Campos clave |
|---------|-----------|-------------|
| **UPDS Oficial** (recomendado) | `"NOMBRE COMPLETO"`, `"CI"` en UPPERCASE | CI real, email, telefono, NIT, banco, HORARIO string |
| Formato intermedio | `"docente"`, `"materias"` en lowercase | horario_detalle parseado |
| Formato legacy | Dict con `"designaciones"` | Formato viejo normalizado |

El formato UPDS oficial es el mas completo — trae CI real (no TEMP), datos personales del docente, y el sistema parsea automaticamente el string de HORARIO a slots con dias, horas inicio/fin, duracion y horas academicas. Incluye correccion de typos (JUVES→JUEVES) y normalizacion de acentos.

### CI Aliasing (Biometrico)

El biometrico puede tener CIs diferentes a la designacion (ej: `10752810` en bio vs `E-10152810` en designacion). El sistema construye un **mapa de alias** al subir el biometrico:
1. Intenta match exacto por CI
2. Si no matchea, busca por nombre fuzzy (`names_match()`)
3. Almacena `biometric_records.teacher_ci` con el CI real del teacher

### Flujo de trabajo del admin

```
1. Subir Lista de Docentes (Excel/JSON)
   → Crea docentes con CI real + datos personales + NIT/retencion
   → Auto-crea usuarios docentes

2. Subir Designacion Docente (JSON — 3 formatos soportados)
   → Asigna materias, grupos, horarios por periodo academico
   → Parsea HORARIO string automaticamente
   → Auto-crea usuarios si hay docentes nuevos

3. Subir Biometrico (XLS)
   → Datos de entrada/salida del control de acceso
   → CI aliasing automatico por nombre

4. Procesar Asistencia (con rango de fechas auto-detectado)
   → Cruza biometrico con designaciones → ATTENDED/LATE/ABSENT
   → Sugiere rango basado en cobertura del biometrico
   → Warning si el rango excede la cobertura

5. Auditar Asistencia
   → Vista detallada por docente: horario + biometrico + resultado
   → Trazabilidad: de donde viene cada ATTENDED/LATE/ABSENT
   → Exportar PDF individual o masivo

6. Generar Planilla
   → Calcula pagos (Model C + retencion 13%)
   → Admin puede ajustar montos (overrides)

7. Aprobar Planilla
   → Estado: generated → approved (o rejected)
   → No se puede publicar sin aprobacion

8. Publicar Facturacion
   → Snapshot inmutable con overrides aplicados
   → Notificacion a TODOS los docentes
   → Docentes ven sus montos en el portal
```

### Roles de usuario

| Rol | Acceso |
|-----|--------|
| **Admin** | Todo: uploads, planilla, reportes, contratos, usuarios, auditoria, actividad, backups |
| **Docente** | Su facturacion, horario, perfil, solicitudes, carta retencion, notificaciones |

## Modulos del Sistema

### Panel de Administracion

| Modulo | Descripcion |
|--------|-------------|
| **Dashboard** | Metricas con Recharts: asistencia (donut), top facturacion (barras), grupos, semestres. 6 stat cards. Busqueda global. |
| **Subir Archivos** | 3 uploaders: lista docentes (Excel/JSON), designacion (JSON — 3 formatos), biometrico (XLS) |
| **Asistencia** | Procesar asistencia con rango de fechas auto-detectado del biometrico. Banners de cobertura. |
| **Auditoria Asistencia** | Vista detallada por docente: horario programado vs entrada real vs estado. Exportar PDF individual o masivo. |
| **Planilla** | Generar + override montos + aprobar/rechazar + publicar + detalle por docente/designacion + historial |
| **Docentes** | CRUD completo + eliminacion masiva (checkboxes) + detalle con edicion de todos los campos incluyendo CI |
| **Usuarios** | Crear/editar/desactivar usuarios + reset de contrasena (fuerza cambio en proximo login) |
| **Contratos** | Generar contratos PDF con plantilla legal UPDS (17 clausulas). Individual o masivo. Configurable: departamento, duracion, tarifa. |
| **Reportes** | 7 tipos con preview: Financiero, Asistencia, Comparativo, Plantel Docente, Incidencias, Conciliacion |
| **Solicitudes** | Responder solicitudes de docentes con info de facturacion + horarios del docente |
| **Observaciones** | Tardanzas, ausencias, sin salida — filtradas por tipo y docente |
| **Registro Actividad** | Audit trail: 16 tipos de eventos con usuario, IP, timestamp, detalles JSON |
| **Respaldos** | Backup/restore de BD via pg_dump. Crear, listar, descargar, eliminar. |

### Portal del Docente

| Modulo | Descripcion |
|--------|-------------|
| **Mi Facturacion** | Monto a cobrar del mes (solo meses publicados). Bruto, retencion, neto. |
| **Historial** | Historial de facturacion por mes con desglose por materia/grupo |
| **Mi Horario** | 3 vistas: por dia, por materia, grilla semanal. Filtro por turno. Export PDF/PNG. |
| **Mi Perfil** | Editar: email, telefono, banco, cuenta. Solo lectura: CI, nombre, genero. Cambio de contrasena con barra de fortaleza. |
| **Solicitudes** | Enviar solicitudes al admin. Ver detalle de respuestas. |
| **Carta Retencion** | Generar carta RC-IVA 13% en PDF con preview. Formulario: titulo, matricula, periodo. |
| **Notificaciones** | Campana con badge de no leidas (poll 30s). Marcar como leida/todas leidas. |

## Seguridad

| Feature | Detalle |
|---------|---------|
| **JWT** | Tokens con expiracion configurable |
| **Contrasenas** | Minimo 8 chars, 1 mayuscula, 1 minuscula, 1 numero. Validado en backend (Pydantic). |
| **must_change_password** | Forzado en primer login para usuarios auto-creados. Enforced en backend (get_current_user, require_admin, require_docente). Solo /auth/login, /auth/me, /auth/change-password permitidos. |
| **Cuentas deshabilitadas** | HTTP 403 con mensaje claro (no generico 401) |
| **Path traversal** | Proteccion con regex estricto en backup download/delete |
| **Activity logging** | 16 tipos de eventos registrados con IP, usuario, timestamp |
| **Password auto-generado** | 12 chars con upper+lower+digit garantizados |
| **CI aliasing** | names_match hardened: requiere 2+ tokens de nombre real (4+ chars) para evitar false positives |
| **Approval workflow** | Planilla debe ser aprobada antes de publicar. State machine: generated→approved→published |

## Reportes PDF

| Tipo | Contenido | Filtros |
|------|-----------|---------|
| **Financiero** | Desglose por docente: bruto, retencion 13%, neto | Mes, ano, docente, semestre, grupo, materia |
| **Asistencia** | Detalle slot por slot con estado coloreado | Mes, ano, docente, semestre, grupo |
| **Comparativo** | Tabla mes a mes con totales acumulados | Ano, docente |
| **Plantel Docente** | Lista completa: CI, telefono, email, banco, NIT/retencion | Ninguno |
| **Incidencias** | Top ausencias, tardanzas, docentes sin biometrico | Mes, ano |
| **Conciliacion** | Discrepancias designacion vs biometrico con severidad | Mes, ano |
| **Auditoria Asistencia** | Trazabilidad completa por docente: horario + bio + resultado | Por docente o masivo |

Otros documentos PDF:
- **Contrato** — 17 clausulas legales UPDS, tabla de materias, firma dual
- **Carta de Retencion** — Solicitud RC-IVA 13% formal con logo UPDS
- **Horario Semanal** — Grilla coloreada por materia con leyenda

Todos los PDFs incluyen: logo UPDS (isologo), header branded, footer de auditoria (generado por, fecha/hora, SIPAD).

## Deteccion Automatica de Rango Biometrico

Al procesar asistencia o generar planilla, el sistema:
1. Detecta automaticamente el rango de fechas del biometrico cargado
2. Pre-llena los campos de fecha con el rango detectado
3. Muestra banner informativo azul con la cobertura
4. Muestra warning naranja si el admin extiende las fechas mas alla de la cobertura
5. Previene la generacion de ausencias falsas por dias sin datos biometricos

## Periodo Academico

Las designaciones estan scoped por periodo academico (ej: `I/2026`, `II/2026`). Configurable via:
- Variable de entorno `ACTIVE_ACADEMIC_PERIOD`
- Selector en la pagina de upload de designaciones
- Endpoint `GET /api/config/active-period` para el frontend

Al cambiar de semestre, solo necesitas cambiar `ACTIVE_ACADEMIC_PERIOD` y cargar las nuevas designaciones.

## Tests

```bash
cd backend

# Ejecutar tests (excluyendo E2E que requiere datos cargados)
python -m pytest tests/ --ignore=tests/test_e2e_real_data.py

# Con output detallado
python -m pytest tests/ --ignore=tests/test_e2e_real_data.py -v

# Solo tests de planilla (calculo de pagos)
python -m pytest tests/test_planilla_generator.py -v

# Solo tests de designation loader
python -m pytest tests/test_designation_loader.py -v

# Test E2E con datos reales (requiere archivos en raiz del repo)
python -m pytest tests/test_e2e_real_data.py -s
```

**153+ tests** cubriendo: carga de designaciones, calculo de pagos (Model C + retencion + overrides), procesamiento de asistencia, APIs, normalizacion de nombres.

## Datos de Ejemplo

El repositorio incluye datos de ejemplo:

| Archivo | Descripcion |
|---------|-------------|
| `Designaciones_UPDS_*.json` | Designacion docente oficial (formato UPDS, 400 entradas, 133 docentes) |
| `lista_docentes_*.xlsx` | Lista del plantel docente con datos personales y bancarios |
| `REPORTE DOCENTES *.xls` | Reporte biometrico del sistema de control de acceso |

### Orden de carga recomendado

```
1. Lista de docentes (Excel)      → Crea docentes con CI real + usuarios
2. Designacion docente (JSON)     → Asigna materias y horarios
3. Biometrico (XLS)               → Datos de asistencia con CI aliasing
4. Procesar asistencia            → Cruza bio con designaciones (usar fechas sugeridas)
5. Generar planilla               → Calcula pagos
6. Revisar + ajustar              → Override montos si necesario
7. Aprobar planilla               → Estado: approved
8. Publicar facturacion           → Docentes ven sus montos
```

## Judgment Day (Control de Calidad)

El proyecto ha pasado por **10 rondas de revision adversarial** (Judgment Day) con dos jueces ciegos independientes. Cada ronda verifica:

- Correccion de pagos (Model C + retencion + overrides)
- Scoping de biometrico por periodo
- Normalizacion de dias con acentos
- Snapshots inmutables con overrides
- Cascada completa de CI (6 tablas)
- Seguridad (JWT, contrasenas, path traversal, state machine)
- Frontend build limpio + TypeScript sin errores

**Estado actual: APPROVED** — 0 CRITICALs, 0 WARNINGs.

## Licencia

Proyecto privado — UPDS Sede Cobija.

## Contacto

SIPAD — Sistema Integrado de Pago Docente
Desarrollado para la Universidad Privada Domingo Savio — Sede Cobija, Pando, Bolivia
Gestion 2026
