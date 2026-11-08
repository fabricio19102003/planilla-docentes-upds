# SIPAD — Sistema Integrado de Pago Docente

<p align="center">
  <strong>Sistema web para la gestión integral de pagos docentes</strong><br>
  Universidad Privada Domingo Savio (UPDS) — Sede Cobija, Pando, Bolivia
</p>

---

## Descripcion General

SIPAD procesa designaciones docentes, datos biometricos de asistencia y genera planillas de pago con calculo automatizado. Incluye retencion RC-IVA 13%, ajustes manuales del admin, publicacion de facturacion para docentes, contratos PDF con historial inmutable de versiones, planificador de horarios con publicaciones, reportes multiples, auditoria de asistencia, mensajeria admin-docente y registro completo de actividad.

Ademas cubre la gestion estudiantil de Medicina: malla curricular, historial academico importado del sistema anterior, portal del estudiante con rematricula, cursos de verano e invierno, apertura de grupos y documentos migratorios.

## Documentacion

| Para | Leer |
|------|------|
| Operar el sistema paso a paso (personal administrativo) | [Guias de procesos](docs/procesos/README.md) |
| Crear, editar o finalizar designaciones | [Designaciones](docs/procesos/designaciones.md) |
| Cambiar el docente de una materia | [Cambio de docente](docs/procesos/cambio-de-docente.md) |
| Armar y publicar horarios | [Planificador de horarios](docs/procesos/planificador-de-horarios.md) |
| Emitir contratos y sus versiones | [Contratos](docs/procesos/contratos.md) |
| Cerrar el mes: biometrico, asistencia, planilla, publicacion | [Cierre mensual](docs/procesos/cierre-mensual.md) |
| Malla, estudiantes, rematricula, intensivos | [Gestion estudiantil](docs/procesos/gestion-estudiantil.md) |
| Docentes, usuarios y credenciales | [Docentes y usuarios](docs/procesos/docentes-y-usuarios.md) |
| Desplegar en el VPS, backups y rollback | [DEPLOYMENT.md](DEPLOYMENT.md) |
| Desarrollar en el frontend (tema, componentes, checks) | [frontend/README.md](frontend/README.md) |

## Stack Tecnologico

| Capa | Tecnologia |
|------|-----------|
| **Backend** | Python 3.11 · FastAPI · SQLAlchemy |
| **Base de datos** | PostgreSQL · migraciones con Alembic (`backend/alembic/`) |
| **Frontend** | React 19 · TypeScript · Vite 8 · Tailwind CSS 4 · coss UI sobre Base UI · TanStack Query |
| **Interfaz** | Tema propio "Institucional vivo" con modo oscuro (Claro/Oscuro/Sistema) · Lucide icons · dnd-kit (planificador) |
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

# ─── Configuracion de Negocio ─────────────────────────────
# ACTIVE_ACADEMIC_PERIOD, COMPANY_NAME, COMPANY_NIT, HOURLY_RATE
# se configuran desde la UI (pagina Configuracion del admin).
# Los valores por defecto se crean automaticamente en la BD al primer inicio.
```

> **Nota:** Las configuraciones de negocio (periodo academico, tarifa por hora, nombre/NIT de empresa) ya **no van en el `.env`**. Se gestionan desde la pagina **Configuracion** en el menu del admin.

### Primer inicio (seed automatico)

Al iniciar el backend por primera vez con una base de datos vacia:

1. En desarrollo (`AUTO_SCHEMA_BOOTSTRAP=true`, el valor por defecto de `backend/.env.example`) se crean todas las tablas automaticamente
2. Se ejecutan las migraciones de columnas nuevas de compatibilidad

> **Produccion es distinto:** con `APP_ENV=production` y `AUTO_SCHEMA_BOOTSTRAP=false` el backend no crea tablas: exige que la base este en el head de Alembic (`alembic upgrade head` se corre aparte) y se niega a arrancar si no. Ver [DEPLOYMENT.md](DEPLOYMENT.md).

3. Se crean **3 usuarios admin** por defecto (si `ADMIN_DEFAULT_PASSWORD` esta configurado):

| Usuario | Contraseña | Rol |
|---------|-----------|-----|
| `admin` | `Admin123` | Admin |
| `daniel` | `Admin123` | Admin |
| `pedro` | `Admin123` | Admin |

4. Se crean las **configuraciones de negocio** por defecto:

| Configuracion | Valor por defecto | Editable desde |
|---------------|-------------------|----------------|
| Periodo Academico | `I/2026` | Configuracion (UI) |
| Nombre Empresa | `UNIPANDO S.R.L.` | Configuracion (UI) |
| NIT Empresa | `456850023` | Configuracion (UI) |
| Tarifa por Hora | `70.0 Bs` | Configuracion (UI) |

5. Se vinculan usuarios docentes a sus docentes correspondientes

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
│   │   ├── models/        # ~28 modelos SQLAlchemy (docentes, designaciones, asistencia, planilla,
│   │   │                  #   publicaciones, contratos, horarios, estudiantes, rematricula, chat...)
│   │   ├── routers/       # ~30 routers FastAPI (admin, portal docente, portal estudiante)
│   │   ├── services/      # Logica de negocio: planilla, asistencia, contratos y PDFs, horarios,
│   │   │                  #   importaciones, rematricula, intensivos, WhatsApp/email, chat
│   │   ├── schemas/       # Validacion Pydantic
│   │   ├── config.py      # Variables de entorno
│   │   └── main.py        # App FastAPI: arranque, seeds y verificacion del esquema
│   ├── alembic/           # Migraciones de esquema (fuente de verdad en produccion)
│   ├── data/              # Malla curricular incluida, assets y archivos generados (PDFs, uploads, backups)
│   └── tests/             # Suite pytest (~120 archivos)
│
├── frontend/
│   ├── src/
│   │   ├── pages/         # ~47 pantallas: admin, portal docente y portal del estudiante (pages/student/)
│   │   ├── components/
│   │   │   ├── ui/        # Primitivas coss UI sobre Base UI (Button, Dialog, Sheet, Menu, Table...)
│   │   │   ├── shared/    # PageHeader, StatCard, StatusBadge, EmptyState, PersonAvatar, tones.ts...
│   │   │   ├── layout/    # Shell: Sidebar, Header, ThemeToggle, Logo
│   │   │   └── <modulo>/  # Componentes por modulo (designations, contracts, curriculum, chat...)
│   │   ├── api/           # Cliente Axios + hooks TanStack Query (staff y studentClient)
│   │   ├── lib/           # Logica pura testeable (estado de pantallas, formatos, navegacion)
│   │   ├── context/       # AuthContext, ThemeContext
│   │   └── index.css      # Tokens del tema (claro/oscuro) y utilidades de marca
│   ├── scripts/           # Checks node:test (`npm run test:*`)
│   └── e2e/               # Playwright con API simulada
│
├── docs/procesos/         # Guias de procesos para el personal administrativo
├── deploy/                # Scripts y runbooks de despliegue
├── openspec/              # Especificaciones y cambios (SDD)
├── DEPLOYMENT.md          # Despliegue seguro en el VPS
└── README.md
```

## Modelo de Negocio

### Modelo de Pago (Model C)

```
Horas Reales  = Calculadas desde el horario del docente x dias reales del periodo de corte
Exclusiones   = Dias excluidos (global, por semestre, o por materia) x Horas/dia
Horas Reales  = Calculadas desde el horario - Horas Excluidas
Pago Base     = Horas Reales x Tarifa/hora (configurable, default 70 Bs)
Descuento     = Horas Ausentes (verificadas por biometrico) x Tarifa/hora
Bruto         = Pago Base - Descuento
Retencion     = Bruto x 13% (solo docentes con retencion RC-IVA)
Neto          = Bruto - Retencion
```

> **Nota**: El calculo de horas usa los **dias reales del calendario** en el periodo de corte,
> no la formula fija `semanal × 4`. Ejemplo: si un docente da clase los lunes (4h) y el
> periodo 21/Mar → 20/Abr tiene 5 lunes, cobra 20h (no 16h como seria con la formula vieja).

**Reglas de negocio:**
- Solo las clases **ausentes** descuentan: tardanzas (mas de 5 minutos) y clases sin salida se pagan completas
- Docentes **sin biometrico** = pago completo (0 ausencias asumidas)
- Biometrico scoped al **periodo** de corte, no al mes calendario
- Admin puede excluir dias especificos del calculo (feriados, eventos, clases magistrales)
- Tres niveles de granularidad: global (todos), por semestre, por materia+grupo
- Exclusiones se configuran antes de generar y son editables despues (regenerar)
- Dias excluidos aparecen en rojo y con 0h en el Excel
- Exclusiones almacenadas en `excluded_days_json` (JSONB) — mismo patron que overrides
- Admin puede aplicar **overrides** manuales al monto de cualquier docente
- Overrides almacenados inmutables en `PlanillaOutput.payment_overrides_json`
- Publicacion crea **snapshot inmutable** — los montos publicados no cambian si los datos base cambian
- El sistema **detecta automaticamente** el rango del biometrico y sugiere las fechas al admin

### Periodo de corte (cross-month)

El admin define un **periodo de corte** para cada planilla (ej: 21 de marzo al 20 de abril). El sistema:

- Calcula las horas de cada docente contando los **dias reales** del periodo que coinciden con su horario programado
- Muestra **dos bloques** en el Excel: uno por cada mes del corte, con los dias fuera del rango en gris
- Las queries de asistencia y biometrico cubren **ambos meses** del rango
- La pantalla exige las dos fechas de corte (hasta 63 dias) antes de habilitar **Generar Planilla**

### Modo de calculo (discount_mode)

La planilla soporta dos modos de calculo. No hay modo por defecto: el admin tiene que elegir uno para habilitar **Generar Planilla**, y la pantalla resume que se va a generar antes de confirmar.

| Modo | Comportamiento |
|------|---------------|
| **Con descuentos** | Se descuentan las clases ausentes segun biometrico |
| **Sin descuentos** | Todos los docentes cobran el 100% de sus horas asignadas. No se requiere biometrico. |

En modo "sin descuentos":
- No se consulta biometrico ni registros de asistencia
- Los dias del Excel se llenan con las horas programadas del docente (no verificadas)
- El modo se persiste en la planilla y se propaga a la publicacion de facturacion, reportes PDF, y dashboard

### Planilla de Salarios (Excel)

Desde la pagina de Planilla, el admin puede descargar una **Planilla de Salarios** en formato Excel que replica la plantilla oficial UNIPANDO. Incluye:
- Encabezado con nombre y NIT de la empresa (configurables desde la UI)
- Una fila por designacion docente con: nombre, telefono, email, CI, materia, semestre, horas, monto, retencion RC-IVA, liquido pagable, NIT, cuenta bancaria, banco
- Formulas Excel (`=J*13%` para retencion, `=J-K` para liquido pagable)
- Fila de totales con `SUBTOTAL`
- Configuracion de impresion (landscape, escala)

### Formatos de designacion soportados

| Formato | Deteccion | Campos clave |
|---------|-----------|-------------|
| **Sobre auditado** (recomendado para cargas conciliadas) | Objeto con `academic_period`, `contract` y `rows` | CI real, identidad validada, designación y horario canónico |
| **UPDS Oficial** (recomendado) | `"NOMBRE COMPLETO"`, `"CI"` en UPPERCASE | CI real, email, telefono, NIT, banco, HORARIO string |
| Formato intermedio | `"docente"`, `"materias"` en lowercase | horario_detalle parseado |
| Formato legacy | Dict con `"designaciones"` | Formato viejo normalizado |

El formato UPDS oficial trae CI real (no TEMP), datos personales del docente, y el sistema parsea automaticamente el string de HORARIO a slots con dias, horas inicio/fin, duracion y horas academicas. Los formatos intermedio y legacy sin CI solo se aceptan cuando cada nombre coincide exactamente con un unico docente real ya existente; nunca crean identidades TEMP.

El string de HORARIO acepta uno o varios bloques `DIA: inicio - fin`, separados por saltos de linea, `/` o espacios, de lunes a domingo; se ignora un `h`/`hrs`/`horas` (también después de `am`/`pm`) o un punto al final del bloque y una `/` al inicio de la celda. Se aceptan horas de 24 h con un `am/pm` redundante (`13: 40 pm`), horas de 12 h (`06: 30 am`, `12: 00 pm` es mediodia), hora y minutos separados por espacio o punto (`08 10`, `18.15`), guion doble y `A` como separador. Se rechaza el bloque, con un mensaje que lo nombra, cuando no se puede leer, cuando una hora no existe (`24:00`, `08:70`), cuando el `am/pm` contradice la hora (`20: 50 am`), cuando termina antes de empezar o cuando dura mas de 6 horas (por ejemplo `08: 55 am- 11: 20 pm`). La vista previa lista cada bloque rechazado como `Fila N: horario inválido: ...` y la importacion completa queda bloqueada hasta corregirlo. Lo mismo vale para la subida en Excel: el horario de la columna H usa el mismo lector, y una fila sin horario se omite con una advertencia.

Las fechas de contrato se importan desde `FECHA INICIO` y `FECHA FIN` (formato oficial) o desde `designation.contract_start_date` y `designation.contract_end_date` (sobre auditado), ambas en formato `AAAA-MM-DD`. Si una fila no trae una fecha, se conserva la que ya estaba guardada; para cerrar una designacion basta reenviarla con su nueva fecha de fin. La vista previa rechaza la fila si la fecha de fin resultante (nueva o guardada) queda antes de la fecha de inicio.

La carga de designaciones siempre se realiza en dos pasos: primero **Generar vista previa**, que valida el archivo completo y muestra altas, actualizaciones, filas sin cambios y conflictos; luego **Confirmar e importar** usando el digest de esos mismos bytes y periodo. La aplicacion es atomica, no elimina filas ausentes y repetir exactamente un archivo produce operaciones sin cambios.

### Pantalla Designaciones (gestion una por una)

El menu **Docentes y academico → Designaciones** (`/designations`) muestra todas las designaciones del periodo con buscador por docente o materia y filtros de semestre, tipo y estado. Desde ahi un administrador puede:

- **Nueva designacion**: docente, materia, semestre, grupo, tipo (se detecta "Practica" por el nombre), horario por bloques (las horas academicas se calculan con bloques de 45 minutos), horas mensuales (sugerido: semanales × 4) y del semestre (sugerido: mensuales × 5), y fechas de contrato.
- **Editar**: corrige cualquier dato mientras ningun mes cubierto este pagado. Si la planilla del mes esta **aprobada** o la facturacion **publicada**, la API responde 409 y la pantalla sugiere finalizar y crear una nueva desde el dia del cambio. Las fechas quedan fijas una vez emitido un contrato para esa designacion.
- **Finalizar**: fija el ultimo dia que dicta la materia (solo puede adelantar el fin). Se rechaza si hay asistencia registrada despues de esa fecha o un mes posterior ya pagado.
- **Eliminar**: solo para designaciones cargadas por error, sin asistencia, contrato, monto manual en planilla ni mes pagado.
- **Importar archivo**: el unico lugar para cargar el Excel de designaciones (*Subir biometrico* ya no lo tiene y enlaza aca), con la vista previa fila por fila (nuevas, con cambios y sin cambios, indicando que campo cambia).

API: `GET/POST /api/admin/designations`, `PUT/DELETE /api/admin/designations/{id}` y `POST /api/admin/designations/{id}/finalize` (solo admin; cada escritura queda en el registro de actividad, categoria *Designaciones*). El detalle del docente enlaza a la pantalla filtrada por ese docente (`/designations?teacher=<CI>`).

### CI Aliasing (Biometrico)

El biometrico puede tener CIs diferentes a la designacion (ej: `10752810` en bio vs `E-10152810` en designacion). El sistema construye un **mapa de alias** al subir el biometrico:
1. Intenta match exacto por CI
2. Si no matchea, busca por nombre fuzzy (`names_match()`)
3. Almacena `biometric_records.teacher_ci` con el CI real del teacher

### Flujo de trabajo del admin

El detalle de cada paso esta en las [guias de procesos](docs/procesos/README.md). Resumen:

**Antes de clases** ([Docentes y usuarios](docs/procesos/docentes-y-usuarios.md), [Designaciones](docs/procesos/designaciones.md), [Planificador](docs/procesos/planificador-de-horarios.md), [Contratos](docs/procesos/contratos.md))

1. **Docentes**: alta en *Docentes y academico → Docentes*; el importador seguro de perfiles (*Subir biometrico → Lista de Docentes*) solo completa campos vacios y nunca crea docentes.
2. **Designaciones**: una por una o *Importar archivo* en *Designaciones* (vista previa obligatoria, aplicacion atomica). *Gestion academica → Cargar designacion* no importa designaciones: arma un borrador del planificador a partir de las existentes.
3. **Horario**: borrador en el *Planificador de horarios* → *Revisar publicacion completa* → publicar. Lo publicado reemplaza a las designaciones en planilla y asistencia desde su fecha efectiva.
4. **Contratos**: *Emitir contratos* (individual o por lote). Si la carga cambia despues, la nueva emision genera una version nueva del contrato completo.

**Cada mes** ([Cierre mensual](docs/procesos/cierre-mensual.md)) — el Dashboard muestra el avance:

1. Subir biometrico → 2. Asistencia (teoricas y practicas) y auditoria → 3. Generar planilla con periodo de corte y modo de calculo → 4. Aprobar → 5. Publicar facturacion y notificar a los docentes.

**Durante el semestre**: [cambio de docente](docs/procesos/cambio-de-docente.md), finalizar designaciones, responder solicitudes y mensajes.

### Roles de usuario

| Rol | Acceso |
|-----|--------|
| **Admin** | Todo: uploads, planilla, reportes, contratos, usuarios, auditoria, actividad, backups |
| **Docente** | Su facturacion, horario, perfil, solicitudes, carta retencion, notificaciones |
| **Estudiante** | Portal propio (`/estudiante`, sesion separada): historial, rematricula, horario, cursos intensivos |

## Modulos del Sistema

El menu del administrador se organiza en cuatro grupos. Cada guia de [docs/procesos](docs/procesos/README.md) explica el paso a paso.

### Panel de Administracion

**Dashboard** — metricas del mes con conteo animado, stepper del **Cierre mensual** (biometrico → asistencia → planilla → aprobacion → publicacion), graficos de asistencia, top facturacion, grupos y semestres, y busqueda global.

| Grupo del menu | Modulo | Que hace |
|----------------|--------|----------|
| **Cierre mensual** | Subir biometrico | Carga el XLS del control de acceso con deteccion de rango y alias de CI; tambien aloja el importador de perfiles docentes |
| | Asistencia teoricas / practicas | Cruza biometrico con horarios: asistio, tardanza, ausencia, sin salida |
| | Observaciones | Tardanzas, ausencias y salidas faltantes por docente |
| | Auditoria de asistencia | Trazabilidad por docente (horario vs. marcacion) con PDF individual o masivo |
| | Planilla | Planilla teorica y de practicas: generar, ajustar montos, aprobar, publicar facturacion, notificar |
| | Reportes | Financiero, asistencia, comparativo, plantel, incidencias, conciliacion |
| **Docentes y academico** | Docentes | Padron con avatar y tipo (titular, permanente, externo), detalle, foto, importacion de perfiles |
| | Designaciones | Materias asignadas: crear, editar, finalizar, eliminar, importar Excel; KPIs y filtros rapidos |
| | Contratos | Historial inmutable agrupado por docente (originales y versiones posteriores) y emision en panel lateral |
| | Gestion academica | Catalogos (programas, materias, grupos, aulas), horarios por semestre, conflictos, cambio de docente |
| | Planificador de horarios | Borradores semanales con arrastrar y soltar, asignacion de docentes, publicaciones con vista previa |
| | Reservas de aulas | Grilla diaria (aulas y laboratorios × hora) con todas las reservas confirmadas de los docentes, filtro Aulas/Laboratorios y lista accesible |
| | Solicitudes | Responde las solicitudes de los docentes |
| | Mensajes | Chat con los docentes (adjuntos, respuestas, reacciones) |
| **Gestion estudiantil** | Estudiantes | Ficha, historial, cuenta del portal y documentos migratorios |
| | Rematricula | Ventanas por periodo y bandeja de solicitudes (realizar u observar) |
| | Cursos intensivos | Cursos de verano e invierno con montos propios e inscripcion desde el portal |
| | Apertura de grupos | Compara solicitudes con grupos creados por semestre y turno |
| | Documentos migratorios | Lista configurable de documentos y estado de regularizacion |
| | Malla curricular | Tablero por semestre con totales; edicion y generacion de ofertas |
| | Importar historial | Importa los CSV del sistema academico anterior (vista previa + aplicar) |
| **Administracion** | Usuarios | Cuentas, roles, credenciales y reseteo de contraseña |
| | Registro de actividad | Audit trail con usuario, IP, fecha y detalle |
| | Respaldos | Backups de la base |
| | Configuracion | Periodo activo, tarifas, comitente de contratos, WhatsApp |

### Portal del Docente

| Modulo | Descripcion |
|--------|-------------|
| **Mi Facturacion** | Monto a cobrar del mes publicado: bruto, retencion y neto, con detalle por materia |
| **Historico** | Facturacion de meses anteriores |
| **Mi Horario** | Horario publicado vigente: por dia, por materia o grilla semanal; exporta PDF/PNG |
| **Reservar aula** | Disponibilidad diaria de un aula o laboratorio (clases publicadas como *Ocupada*, otras reservas como *Reservada*) y reserva puntual por hora de inicio y cantidad de periodos academicos (`ACADEMIC_HOUR_MINUTES`), confirmada al instante; lista y cancelacion de las propias reservas futuras |
| **Carta Retencion** | Carta RC-IVA 13% en PDF (solo para docentes con retencion) |
| **Mis Solicitudes** | Consultas al admin y sus respuestas |
| **Mensajes** | Chat con administracion |
| **Notificaciones** | Avisos de publicacion y respuestas, con contador de no leidas |
| **Mi Perfil** | Datos de contacto y bancarios, foto y cambio de contraseña |

### Portal del Estudiante (`/estudiante`)

| Modulo | Descripcion |
|--------|-------------|
| **Inicio** | Bienvenida con semestre, beca y plan; estado de la rematricula y documentos migratorios |
| **Historial academico** | Resumen (promedio, aprobadas, avance) y linea de tiempo por periodo con notas coloreadas |
| **Rematricula** | Solicitud con grupo del semestre y materias de recursado o pendientes |
| **Mi horario** | Horario publicado de sus grupos y cursos intensivos |
| **Cursos de verano e invierno** | Inscripcion y cancelacion con precio estimado |

## Interfaz y tema

- **Componentes:** coss UI sobre Base UI (`frontend/src/components/ui/`). Las paginas usan los componentes compartidos de `components/shared/` (`PageHeader`, `StatCard`, `StatusBadge`, `EmptyState` con ilustraciones, `PersonAvatar`, `TeacherTypeBadge`).
- **Colores solo por tokens:** todos los colores viven en `frontend/src/index.css` (tokens claro/oscuro y utilidades `bg-brand`, `bg-brand-soft`, `bg-brand-line`). Las paginas no usan hex, degradados ni clases de paleta (`bg-blue-500`); los checks `test:ui-*` lo verifican. Los tonos semanticos estan en `components/shared/tones.ts` y los colores por semestre y turno en `lib/academicTones.ts`.
- **Modo oscuro:** selector Claro/Oscuro/Sistema en el header y en el portal del estudiante; sigue al sistema operativo por defecto y se recuerda por navegador (`sipad-theme`), con un script previo al render para evitar el destello claro.
- **Accesibilidad:** contraste WCAG AA verificado en ambos temas; las animaciones (hover, transicion de pagina, conteo de numeros) se desactivan con `prefers-reduced-motion`.

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

Las designaciones estan scoped por periodo academico (ej: `I/2026`, `II/2026`).
- El **periodo activo** se guarda en la base (`ACTIVE_ACADEMIC_PERIOD`, por defecto `I/2026`) y se cambia en *Administracion → Configuracion*; ya no se lee del `.env`.
- El frontend lo consulta con `GET /api/config/active-period`.
- Al importar en *Designaciones → Importar archivo* se elige el periodo destino del archivo.

Importar designaciones no cambia el periodo activo. La activacion sigue siendo una accion separada en Configuracion.

## Horarios por semestre y grupo (Gestion academica)

- `GET /api/admin/academic-management/schedule-view?academic_period=II/2026[&source=current|draft][&draft_id=N][&date=AAAA-MM-DD][&semester=N][&group=M-1]` devuelve los bloques semanales y la lista de semestres con sus grupos.
  - `current` (por defecto) es el horario que usa la planilla: designaciones de teoria vigentes en la fecha mas la ultima publicacion de practicas.
  - `draft` muestra un borrador con el docente asignado en la fecha.
  - Los semestres en ordinal (`PRIMERO`, `Septimo`) se devuelven como numero y los grupos normalizados (`M-01` = `M-1`).
- `GET .../schedule-view/export` con los mismos filtros descarga un Excel: una hoja por semestre y grupo con la grilla semanal de 06:30 a 23:30 en franjas de 30 minutos, mas una hoja `Lista` con todos los bloques.
- La vista previa de publicacion bloquea los borradores con teoria que cambiarian lo que pagan las designaciones: `theory_hours_mismatch` cuando la designacion reemplazada pagaria otras horas semanales y `theory_duplicates_designation` cuando una designacion vigente del mismo grupo y semestre se superpone con un bloque de teoria sin ser reemplazada (se pagaria dos veces).

## Gestion estudiantil (malla, estudiantes e historial)

El sistema academico anterior sigue siendo el registro oficial. SIPAD importa sus exportaciones CSV (`gestion-AAAA.csv`, una fila por materia cursada, 48 columnas) y puede reimportarlas las veces que haga falta.

- **Malla curricular** (`/curriculum`): Medicina 510-01, 10 semestres y 80 materias (4 electivas sin codigo). La definicion esta en `backend/data/curricula/medicina-510-01.json`; se carga con `POST /api/admin/academic-records/curricula/default/load` o sola en la primera importacion. Reutiliza el programa `MED 510-01` y las materias existentes por codigo (`MRF 0100`) sin renombrarlas.
- **Periodos**: `Primer Semestre`, `Segundo Semestre`, `Invierno` y `Verano` de cada `OfertaGestion` se guardan como `I/AAAA`, `II/AAAA`, `INV/AAAA` y `VER/AAAA`; el `OfertaNombre` original (`2023/1/1`, `2025/ Semestre I`, `INVIERNO 2024`) queda como evidencia.
- **Importacion** (`/academic-history-import`): `POST /imports/preview` no escribe nada; `POST /imports/apply` exige el `expected_sha256` de la vista previa y responde `409` si el archivo cambio. Los estudiantes se reconocen por `EstudianteNroDocumento` y cada materia por `RegistroMateriaID`, asi que reimportar actualiza (por ejemplo `Pendiente` a `Aprobado`) y nunca duplica. Las filas con error se omiten y se informan con su numero de fila (tambien una fila incompleta o un valor mas largo que su campo, por ejemplo `EstudianteCelular supera 40 caracteres`); un CSV mal formado, como una comilla sin cerrar, se rechaza entero con `422`. Las materias fuera de la malla se importan con una advertencia. La importacion nunca crea docentes: vincula el registro a un docente de SIPAD solo si su documento coincide (tambien por alias de CI). Cada aplicacion guarda un recibo con nombre, SHA-256, conteos y usuario.
- **Notas**: un `0` en una materia `Pendiente` o `Retirado` es el valor de relleno del sistema anterior y se guarda sin nota. El promedio del periodo que muestra el detalle del estudiante solo cuenta materias aprobadas y reprobadas.
- **Archivos grandes**: el proxy acepta hasta 25 MB y `gestion-2026.csv` pesa ~27 MB, por eso el navegador comprime el CSV con gzip antes de subirlo; la API acepta CSV plano o gzip (maximo 20 MB subidos, 120 MB descomprimidos); un gzip cortado o con contenido extra se rechaza con `400`.
- **Privacidad**: todos los endpoints `/api/admin/academic-records/*` y las pantallas de Gestion estudiantil son solo para administradores.
- **Editar la malla** (*Malla curricular → Editar malla*): agregar, editar o quitar materias (nombre, sigla, HT, HP, creditos, electiva), moverlas de semestre, reordenarlas, y agregar un semestre o quitar el ultimo si esta vacio. Los cambios aplican a la malla vigente para todos los estudiantes y cada uno queda en el registro de actividad con el antes y el despues; quitar una materia no borra el historial de nadie. La malla incluida en SIPAD se carga una sola vez: despues la importacion del historial ya no la sobrescribe.
- **Ofertas desde la malla**: en el modo de edicion, *Generar ofertas* crea las ofertas de un periodo (`I/2027`, `II/2027`, `INV/2027`, `VER/2027`) con la materia, el semestre y las horas de la malla. Las que ya existen no se tocan (se conservan sus cambios manuales) y las electivas sin sigla se informan como no generadas.

## Portal del estudiante y rematricula

El estudiante pide su rematricula desde SIPAD y Registro la carga en el sistema academico anterior, que sigue siendo el oficial.

- **Cuenta** (`/estudiante/login`): el estudiante entra con su numero de documento. Registro genera una clave temporal desde el detalle del estudiante o para hasta 100 estudiantes seleccionados en la lista (se muestra una sola vez y se puede descargar como CSV); el estudiante la cambia en su primer ingreso. Generar una clave nueva o deshabilitar la cuenta cierra las sesiones abiertas. La sesion del portal (`student_token`) es independiente de la de admin/docente: un token de estudiante nunca abre rutas de staff y viceversa.
- **Ventanas** (*Gestion estudiantil → Rematricula*): el admin abre la rematricula de un periodo destino (por ejemplo `I/2027`) con fecha de inicio y fin, en hora de Bolivia. Fuera de la ventana el portal solo muestra el historial y el estado de la solicitud.
- **Que le toca cursar**: el semestre siguiente a su semestre principal del ultimo periodo regular (I o II), es decir el semestre del que curso mas materias distintas (empate al mayor), con tope en el ultimo semestre de la malla. Recursado: materias con un `Reprobado` y sin `Aprobado`. Pendientes sin cargo: materias de semestres anteriores que solo tienen `Retirado`. Las materias en curso (`Pendiente`) no aparecen. `SPC 0100` y `SVB 0800` del sistema anterior equivalen a `SCP 0100` y `CVB 0800` de la malla.
- **Grupos y cupos**: los grupos del periodo destino se cargan en *Gestion academica* (codigo, turno, semestre y capacidad). El estudiante elige un grupo de su semestre y uno por cada materia de recursado o pendiente que quiera cursar. Las solicitudes pendientes y realizadas ocupan cupo; un grupo lleno no se puede elegir y un grupo sin capacidad no tiene limite.
- **Montos (informativos)**: Beca Fundador (promedio > 64) 850 Bs por cuota, Beca Desafio (promedio > 61) 1300 Bs, Sin beca 1600 Bs, 5 cuotas. Las dos becas exigen no haber reprobado nunca una materia; el promedio es el del ultimo periodo regular con notas finales, sin `Retirado`. Recursado: 1200 Bs por materia elegida, cobrando como maximo 3. SIPAD no cobra nada; Registro verifica el pago del recursado en caja.
- **Bandeja de Registro**: filtra por estado, semestre, nacionalidad y nombre o documento. Cada solicitud se marca como *Realizada* despues de cargarla en el sistema anterior, o como *Observada* con un motivo (`Documentos de migracion`, `Pago pendiente`, `Otro`) y un mensaje que el estudiante ve en su portal; mientras la ventana esta abierta el estudiante puede corregirla y vuelve a *Pendiente*. Todas las acciones quedan en el registro de actividad.

## Cursos intensivos, horario, apertura de grupos y documentos migratorios

- **Cursos de verano e invierno** (*Gestion estudiantil → Cursos intensivos*): primero se configuran los montos propios de los intensivos (tarifa por hora teorica y practica, factor de margen 1,10, minimo 1200 Bs y maximo 1600 Bs); son independientes de las tarifas de la planilla y sin tarifas no se puede abrir un curso. El admin abre un curso `VER/AAAA` o `INV/AAAA` con materia, docente, cupo, fechas de inscripcion y horas (si se dejan vacias se toman de la malla). Se puede inscribir desde el portal (`/estudiante/intensivos`) quien tiene esa materia reprobada y nunca aprobada, o solo retirada; puede cancelar mientras el curso este abierto. Precio por estudiante = pago docente × factor / inscritos, redondeado y limitado entre el minimo y el maximo; pago docente = horas teoricas × tarifa teorica + horas practicas × tarifa practica. El portal muestra el precio estimado con los inscritos actuales; al cerrar la inscripcion el precio queda fijo. El ultimo cupo nunca se asigna a dos estudiantes.
- **Mi horario** (`/estudiante/horario`): cuando Registro marca la rematricula como *Realizada*, el estudiante ve el horario publicado de su grupo (solo las materias del semestre que cursa) y de cada grupo de recursado o pendiente, mas sus cursos intensivos, con aula y docente. Usa la publicacion vigente hoy (la misma regla que el portal docente) o, antes de que empiecen las clases, la proxima con su fecha de inicio.
- **Apertura de grupos** (*Gestion estudiantil → Apertura de grupos*): por ventana de rematricula, semestre y turno compara las solicitudes pendientes y realizadas con el tamano de grupo configurable (40 por defecto): grupos sugeridos = solicitudes / tamano redondeado hacia arriba, frente a los grupos ya creados en Gestion academica y su capacidad (falta, sobra o correcto). Los recursantes se informan aparte y no suman grupos.
- **Documentos migratorios** (*Gestion estudiantil → Documentos migratorios*): el admin define la lista de documentos (con o sin vencimiento, orden, desactivar). En la ficha de cada estudiante extranjero se registra cuales presento y su vencimiento; queda *Regularizado* cuando tiene todos los documentos activos y ninguno vencido (un documento que vence hoy sigue vigente). Registro no puede marcar como realizada la rematricula de un extranjero no regularizado: la API responde `409` con la lista, por ejemplo `Documentos migratorios pendientes: Visa de estudiante, Carnet de extranjero (vencido el 15/10/2026)`. El estudiante ve en su portal que le falta presentar.

## Reservas de aulas y laboratorios

- Se reservan las aulas y laboratorios **activos** del catalogo (Gestion academica → Aulas; los laboratorios se dan de alta ahi con tipo *Laboratorio* y capacidad).
- El docente elige fecha, hora de inicio (multiplos de 5 minutos) y de 1 a 8 periodos academicos; la hora de fin es inicio + periodos × `ACADEMIC_HOUR_MINUTES`. La reserva debe quedar entre las 06:30 y las 23:05 y no puede empezar en el pasado (hora de Bolivia).
- Una reserva puntual se confirma al crearla si su rango `[inicio, fin)` no se superpone con una clase **publicada** del aula ese dia de la semana ni con otra reserva confirmada; reservas contiguas estan permitidas. La fila del aula se bloquea (`SELECT ... FOR UPDATE`) antes de comprobar, asi dos pedidos simultaneos no reservan el mismo rango.
- El docente puede cancelar sus reservas que todavia no empezaron (quedan con estado `cancelled`). La disponibilidad nunca muestra quien reservo.
- Portal: `GET /api/portal/classroom-reservations/classrooms`, `GET .../availability?classroom_id=&date=`, `POST /api/portal/classroom-reservations`, `GET .../mine`, `POST .../{id}/cancel`.
- Admin: `GET /api/admin/classroom-reservations?date_from=&date_to=` (rango de hasta 31 dias) devuelve las aulas reservables (mas las desactivadas que tengan reservas en el rango) y las reservas confirmadas.

## Tests

```bash
cd backend

# Ejecutar tests (excluyendo E2E que requiere datos cargados)
python -m pytest tests/ --ignore=tests/test_e2e_real_data.py

# Con output detallado
python -m pytest tests/ --ignore=tests/test_e2e_real_data.py -v

# Solo tests de planilla (calculo de pagos)
python -m pytest tests/test_planilla_generator.py -v

# Solo tests de exclusion de dias
python -m pytest tests/test_exclusion_dias_planilla.py -v

# Solo tests de designation loader
python -m pytest tests/test_designation_loader.py -v

# Synthetic designation-loader integration coverage
python -m pytest tests/test_designation_loader.py -s
```

La suite backend (~120 archivos de test) cubre: carga de designaciones, calculo de pagos (Model C + retencion + overrides), asistencia, contratos, horarios y publicaciones, rematricula, intensivos, importaciones y APIs. Los tests de concurrencia en PostgreSQL son opcionales (`REENROLLMENT_TEST_POSTGRES_URL`).

### Frontend

```bash
cd frontend
npx tsc -b            # Tipos
npm run lint          # ESLint
npm run build         # Build de produccion
npm run test:<nombre> # Checks node:test de logica pura y reglas de UI (scripts/check-*.mjs), ej. test:ui-shared
npm run test:e2e      # Playwright (desktop + mobile) con la API simulada; la primera vez: npm run test:e2e:install
```

Para correr todos los checks: `for s in $(node -e "console.log(Object.keys(require('./package.json').scripts).filter(k=>k.startsWith('test:')&&!k.startsWith('test:e2e')).join(' '))"); do npm run -s $s || echo "FALLO $s"; done`

## Test Data and External Real-Data E2E

The repository contains only the artificial fixture
`backend/tests/fixtures/designations.synthetic.json`. It uses clearly synthetic
teachers, subjects, groups, and schedules and is safe for normal automated tests.

Official designation, teacher, banking, and biometric files are operational
data and are not distributed with the source repository. The destructive
real-data E2E is explicitly opt-in and accepts external fixture paths:

```bash
SIPAD_REAL_DATA_E2E=1 \
SIPAD_E2E_BIOMETRIC_FILE=/secure/path/biometric.xls \
SIPAD_E2E_DESIGNATIONS_FILE=/secure/path/designations.json \
python -m pytest tests/test_e2e_real_data.py -v -s
```

Keep those paths and files outside the repository. Without the opt-in flag and
both existing inputs, the real-data E2E skips safely.

### Orden de carga recomendado

```
1. Docentes (alta o importador de perfiles)   → Padron con CI real; usuarios docentes
2. Designaciones (Designaciones → Importar)   → Materias, grupos y horarios del periodo
3. Horario publicado (opcional)               → Planificador: borrador → revisar → publicar
4. Biometrico (XLS)                           → Marcaciones con alias de CI
5. Asistencia                                 → Cruza biometrico con horarios (usar fechas sugeridas)
6. Planilla                                   → Calcula pagos; ajustar montos si hace falta
7. Aprobar planilla                           → Requisito para publicar
8. Publicar facturacion                       → Los docentes ven sus montos
```

## Judgment Day (Control de Calidad)

El proyecto ha pasado por **12 rondas de revision adversarial** (Judgment Day) con dos jueces ciegos independientes. Cada ronda verifica:

- Correccion de pagos (Model C + retencion + overrides)
- Scoping de biometrico por periodo
- Normalizacion de dias con acentos
- Snapshots inmutables con overrides
- Exclusion de dias: doble deduccion, cutoff fallback, coverage validation, dashboard consistency
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
