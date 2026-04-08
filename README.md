# SIPAD — Sistema Integrado de Pago Docente

Sistema web para la gestión de pagos docentes de la **Universidad Privada Domingo Savio (UPDS) — Sede Cobija**.

Procesa designaciones docentes, datos biométricos de asistencia y genera planillas de pago con cálculo automatizado, retención RC-IVA 13%, ajustes del admin, publicación de facturación, contratos PDF y reportes.

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| **Backend** | Python 3.11 · FastAPI · SQLAlchemy · PostgreSQL |
| **Frontend** | React 19 · TypeScript · Vite · Tailwind CSS 4 · Shadcn UI |
| **PDFs** | ReportLab 4.4 |
| **Gráficos** | Recharts |
| **Exportación** | html-to-image (PNG) · openpyxl (Excel parsing) |

## Requisitos Previos

- **Python 3.11+**
- **Node.js 18+** y npm
- **PostgreSQL 14+** (con `pg_dump` accesible en PATH para backups)
- Git

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/fabricio19102003/planilla-docentes-upds.git
cd planilla-docentes-upds
```

### 2. Backend

```bash
cd backend

# Crear entorno virtual
python -m venv venv

# Activar (Windows)
venv\Scripts\activate
# Activar (Linux/Mac)
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con los datos de tu BD
```

### 3. Base de datos

```bash
# Crear la base de datos en PostgreSQL
createdb planilla_docentes_upds

# Las tablas se crean automáticamente al iniciar el backend
```

### 4. Frontend

```bash
cd frontend
npm install
```

## Configuración

### Variables de entorno (`backend/.env`)

```env
# Base de datos PostgreSQL
DATABASE_URL=postgresql+psycopg2://postgres:tu_password@localhost:5432/planilla_docentes_upds

# CORS — orígenes permitidos del frontend
CORS_ORIGINS=["http://localhost:5173"]

# JWT — cambiar en producción
JWT_SECRET=tu-clave-secreta-segura-cambiar-en-produccion

# Directorio de uploads
UPLOAD_DIR=./data/uploads

# Contraseña del admin por defecto (debe cumplir: 8+ chars, 1 mayúscula, 1 minúscula, 1 número)
ADMIN_DEFAULT_PASSWORD=Admin2026!

# Período académico activo
ACTIVE_ACADEMIC_PERIOD=I/2026

# Tarifa por hora académica (Bs)
HOURLY_RATE=70
```

### Primer inicio

Al iniciar el backend por primera vez:
1. Se crean todas las tablas automáticamente
2. Se ejecutan las migraciones de columnas nuevas
3. Se crea el usuario admin por defecto (si `ADMIN_DEFAULT_PASSWORD` está configurado)
4. Se vinculan usuarios docentes a sus docentes correspondientes

## Ejecución

### Desarrollo

```bash
# Terminal 1 — Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Documentación API**: http://localhost:8000/docs (Swagger UI)

### Build de producción

```bash
cd frontend
npm run build
# Los archivos estáticos quedan en frontend/dist/
```

## Estructura del Proyecto

```
planilla-docentes-upds/
├── backend/
│   ├── app/
│   │   ├── models/          # Modelos SQLAlchemy (11 modelos)
│   │   │   ├── teacher.py           # Docente
│   │   │   ├── designation.py       # Designación (materia, grupo, horario)
│   │   │   ├── attendance.py        # Registro de asistencia
│   │   │   ├── biometric.py         # Datos biométricos
│   │   │   ├── planilla.py          # Planilla generada
│   │   │   ├── billing_publication.py # Publicación de facturación
│   │   │   ├── user.py              # Usuarios (admin/docente)
│   │   │   ├── notification.py      # Notificaciones
│   │   │   ├── detail_request.py    # Solicitudes de docentes
│   │   │   ├── activity_log.py      # Registro de actividad
│   │   │   └── report.py            # Reportes generados
│   │   ├── routers/          # Endpoints FastAPI (13 routers)
│   │   │   ├── auth.py              # Login, cambio de contraseña
│   │   │   ├── teachers.py          # CRUD docentes + upload lista
│   │   │   ├── designations.py      # Upload designaciones
│   │   │   ├── biometric.py         # Upload biométrico
│   │   │   ├── attendance.py        # Procesar asistencia
│   │   │   ├── planilla.py          # Generar planilla + dashboard
│   │   │   ├── billing_publication.py # Publicar/despublicar facturación
│   │   │   ├── contracts.py         # Generar contratos PDF
│   │   │   ├── reports.py           # Generar reportes PDF
│   │   │   ├── docente_portal.py    # Portal docente (billing, perfil, horario)
│   │   │   ├── detail_requests.py   # Solicitudes admin↔docente
│   │   │   ├── activity_log.py      # Registro de actividad
│   │   │   └── admin.py             # Backups de BD
│   │   ├── services/          # Lógica de negocio
│   │   │   ├── planilla_generator.py     # Cálculo de pagos (Model C)
│   │   │   ├── attendance_engine.py      # Procesamiento de asistencia
│   │   │   ├── designation_loader.py     # Carga de designaciones
│   │   │   ├── biometric_parser.py       # Parseo de archivos biométricos
│   │   │   ├── auth_service.py           # Autenticación + JWT
│   │   │   ├── report_generator.py       # PDFs de reportes
│   │   │   ├── contract_pdf.py           # PDFs de contratos
│   │   │   ├── retention_letter_pdf.py   # Carta de retención RC-IVA
│   │   │   ├── schedule_pdf.py           # Horario semanal PDF
│   │   │   └── activity_logger.py        # Helper de logging
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── utils/             # Helpers (auth, normalization)
│   │   ├── config.py          # Configuración (env vars)
│   │   ├── database.py        # Conexión a PostgreSQL
│   │   └── main.py            # App FastAPI + lifespan
│   ├── tests/                 # Test suite (172 tests)
│   ├── data/
│   │   ├── assets/            # Logos UPDS
│   │   ├── uploads/           # Archivos subidos
│   │   ├── reports/           # Reportes PDF generados
│   │   ├── contracts/         # Contratos PDF generados
│   │   ├── schedules/         # Horarios PDF
│   │   ├── retention_letters/ # Cartas de retención
│   │   └── backups/           # Backups de BD (.sql)
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── pages/             # 20 páginas
│   │   ├── components/        # UI components (layout, shared, ui)
│   │   ├── api/               # Client Axios + hooks TanStack Query
│   │   ├── context/           # Auth + Sidebar contexts
│   │   └── lib/               # Utilidades
│   ├── public/                # Logos UPDS
│   └── package.json
│
├── designacion_new.json       # Datos de designación docente
├── lista_docentes_1_2026.xlsx # Lista del plantel docente
└── README.md
```

## Modelo de Negocio

### Modelo de Pago (Model C)

```
Pago Base = Horas Mensuales × Bs 70/hora
Descuento = Horas Ausentes × Bs 70/hora (solo ausencias verificadas por biométrico)
Bruto = Pago Base - Descuento
Retención = Bruto × 13% (solo docentes con retención RC-IVA)
Neto = Bruto - Retención
```

**Reglas:**
- Docentes **sin biométrico** = pago completo (0 ausencias asumidas)
- Biométrico scoped al **período** (month+year), no histórico
- Admin puede aplicar **overrides** manuales al monto de cualquier docente
- Overrides se almacenan inmutables en la planilla generada

### Flujo de trabajo del admin

```
1. Subir Lista de Docentes (Excel/JSON) → Crea docentes con CI real + usuarios
2. Subir Designación Docente (JSON) → Asigna materias, grupos, horarios
3. Subir Biométrico (XLS) → Datos de entrada/salida del control de acceso
4. Procesar Asistencia → Cruza biométrico con designaciones → ATTENDED/LATE/ABSENT
5. Generar Planilla → Calcula pagos (Model C + retención) → Excel
6. Revisar + Ajustar → Override de montos si hay errores del biométrico
7. Aprobar Planilla → Estado: generated → approved
8. Publicar Facturación → Snapshot inmutable → Docentes ven sus montos
```

### Roles de usuario

| Rol | Acceso |
|-----|--------|
| **Admin** | Todo: uploads, planilla, reportes, contratos, usuarios, actividad, backups |
| **Docente** | Su facturación, horario, perfil, solicitudes, carta retención, notificaciones |

## Módulos del Sistema

### Admin

| Módulo | Descripción |
|--------|-------------|
| **Dashboard** | Métricas, gráficos (Recharts): asistencia, facturación, docentes, semestres |
| **Subir Archivos** | Upload de: lista docentes, designación, biométrico |
| **Asistencia** | Procesar asistencia con rango de fechas configurable |
| **Planilla** | Generar + override + aprobar/rechazar + publicar + historial |
| **Docentes** | CRUD completo + eliminación masiva + detalle con edición |
| **Usuarios** | Crear/editar/desactivar usuarios + reset de contraseña |
| **Contratos** | Generar contratos PDF (individual o masivo) con plantilla legal UPDS |
| **Reportes** | 7 tipos: Financiero, Asistencia, Comparativo, Plantel, Incidencias, Conciliación |
| **Solicitudes** | Responder solicitudes de docentes con info de facturación |
| **Actividad** | Registro completo de auditoría (16 tipos de eventos) |
| **Respaldos** | Backup/restore de la base de datos (pg_dump) |

### Portal Docente

| Módulo | Descripción |
|--------|-------------|
| **Mi Facturación** | Monto a cobrar del mes (solo meses publicados) |
| **Historial** | Historial de facturación por mes |
| **Mi Horario** | Horario semanal con 3 vistas + filtro por turno + export PDF/PNG |
| **Mi Perfil** | Editar datos personales y bancarios + cambiar contraseña |
| **Solicitudes** | Enviar solicitudes al admin (info, corrección, horario) |
| **Carta Retención** | Generar carta RC-IVA 13% en PDF |
| **Notificaciones** | Campana con badge + listado de notificaciones |

## Seguridad

- **JWT** con expiración configurable
- **Contraseñas**: mínimo 8 caracteres, 1 mayúscula, 1 minúscula, 1 número (validado en backend)
- **must_change_password**: forzado en primer login para usuarios auto-creados
- **Cuentas deshabilitadas**: HTTP 403 con mensaje claro (no genérico 401)
- **Enforcement en backend**: `get_current_user`, `require_admin`, `require_docente` bloquean si must_change_password=True
- **Path traversal**: protección con regex estricto en backup download/delete
- **Activity logging**: 16 tipos de eventos registrados con IP, usuario, timestamp
- **Password auto-generado**: `secrets.token_urlsafe` + validación de complejidad garantizada

## Reportes PDF disponibles

| Tipo | Contenido | Filtros |
|------|-----------|---------|
| **Financiero** | Desglose por docente: bruto, retención 13%, neto | Mes, año, docente, semestre, grupo |
| **Asistencia** | Detalle slot por slot con estado coloreado | Mes, año, docente, semestre, grupo |
| **Comparativo** | Tabla mes a mes con totales acumulados | Año, docente |
| **Plantel Docente** | Lista completa: CI, teléfono, email, banco, NIT/retención | Ninguno |
| **Incidencias** | Top ausencias, tardanzas, docentes sin biométrico | Mes, año |
| **Conciliación** | Discrepancias designación vs biométrico con severidad | Mes, año |
| **Contrato** | Contrato legal completo con 17 cláusulas UPDS | Por docente |
| **Carta Retención** | Solicitud RC-IVA 13% formal | Por docente |
| **Horario Semanal** | Grilla de horario con colores por materia | Por docente |

## Tests

```bash
cd backend

# Ejecutar todos los tests
python -m pytest tests/

# Con output detallado
python -m pytest tests/ -v

# Solo tests unitarios
python -m pytest tests/test_planilla_generator.py tests/test_designation_loader.py -v

# Test E2E con datos reales
python -m pytest tests/test_e2e_real_data.py -s
```

**172 tests** cubriendo: carga de designaciones, cálculo de pagos, procesamiento de asistencia, APIs, E2E.

## Datos de ejemplo

El repositorio incluye datos de ejemplo para pruebas:

- `designacion_new.json` — Designaciones docentes (400 entradas)
- `lista_docentes_1_2026.xlsx` — Lista del plantel docente

### Orden de carga recomendado

1. **Lista de docentes** (`.xlsx`) — Crea docentes con CI real
2. **Designación docente** (`.json`) — Asigna materias y horarios
3. **Biométrico** (`.xls`) — Datos de asistencia

## Licencia

Proyecto privado — UPDS Sede Cobija.

## Contacto

Desarrollado para la gestión de pagos docentes de la UPDS — Sede Cobija, Pando, Bolivia.
