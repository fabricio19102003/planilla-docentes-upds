# Administrar docentes, usuarios y credenciales

## Para qué sirve

Con esta guía vas a mantener el padrón de docentes (alta, edición, foto, baja y corrección de CI), completar perfiles de forma masiva con el importador seguro, registrar el consentimiento de WhatsApp de cada docente, crear las cuentas de acceso a SIPAD (administradores y docentes), resetear contraseñas y activar o desactivar usuarios. También explica qué es un alias de CI y cuándo aparece, para que no te sorprenda.

## Antes de empezar

- **Rol:** administrador. Un docente solo puede ver y editar su propio perfil desde su portal.
- **Dónde está en el menú:**
  - **Docentes y académico → Docentes** (listado y detalle de cada docente).
  - **Cierre mensual → Subir biométrico** (pantalla «Carga de datos», tarjeta **Lista de Docentes**: importador de perfiles).
  - **Administración → Usuarios** (cuentas de acceso).
  - **Administración → Configuración** (permisos de **Mi Perfil** docente y envío por WhatsApp).
- **Docente ≠ usuario.** Un *docente* es la ficha del padrón (CI, datos académicos y bancarios); un *usuario* es la cuenta con la que alguien entra a SIPAD. Primero se crea el docente y después, si hace falta, su usuario con rol **Docente** vinculado a esa ficha.
- **Tipos de docente** (campo **Tipo**): **Externo**, **Permanente** y **Titular**.

## Paso a paso

### 1. Dar de alta un docente

1. Abrí **Docentes y académico → Docentes** y tocá **Nuevo Docente**.
2. Completá al menos **CI \*** y **Nombre Completo \***. El resto es opcional y está agrupado en **Datos Personales** (Email, Teléfono, Género, Tipo), **Datos Académicos** (Nivel Académico, Profesión, Especialidad, Código SAP) y **Datos Bancarios** (Banco, Número de Cuenta, Retención Factura).
3. Tocá **Crear Docente**.

El listado se puede buscar por **nombre o C.I.** y muestra Nombre Completo, C.I., Correo, Profesión, Tipo y el enlace **Ver más →** al detalle.

### 2. Editar un docente y su foto

1. En el listado tocá **Ver más →** (título **Detalle de Docente**).
2. Tocá **Editar**, cambiá los campos y tocá **Guardar Cambios** (o **Cancelar**). Podés corregir cualquier dato, incluido el CI (ver el paso 3).
3. **Foto institucional** (visible cuando no estás editando): **Subir foto** / **Cambiar foto** (JPG, PNG o WEBP de hasta 2 MB), **Descargar foto** y **Eliminar foto** (pide confirmación; el docente vuelve a mostrar sus iniciales). El cambio se ve en el portal y en el encabezado del docente.
4. Desde el mismo detalle también podés **Descargar horario** (PDF), ver el **Resumen de Asistencia** y las **Designaciones** del docente; **Gestionar designaciones** te lleva a la pantalla de designaciones ya filtrada por ese docente.

### 3. Corregir el CI de un docente

1. En el detalle tocá **Editar** y cambiá el campo **C.I. \***.
2. Aparece el aviso «Al guardar, el docente ingresará al portal con el C.I. X. Su contraseña no cambia.»
3. Tocá **Guardar Cambios**. SIPAD actualiza el CI en designaciones, asistencia, biométrico, solicitudes, contratos y demás registros del docente, y guarda el CI anterior como **alias** (ver «Alias de CI» abajo). Te lleva automáticamente a la nueva URL del docente.

### 4. Eliminar docentes

- **Uno:** en el detalle tocá **Eliminar** y confirmá («Eliminar Docente»).
- **Varios:** en el listado marcá las casillas (o **Seleccionar todos los docentes de la página**) y tocá **Eliminar seleccionados**, luego **Confirmar eliminación**.

Ambas opciones eliminan también sus designaciones, registros de asistencia y cuentas de usuario. **No se puede deshacer.** Si solo querés que alguien deje de entrar, desactivá su usuario (paso 8).

### 5. Importar perfiles de docentes (importador seguro)

Sirve para **completar campos vacíos** de docentes que ya existen. No crea docentes, no pisa valores existentes, no activa períodos ni toca contraseñas o accesos.

1. Abrí **Cierre mensual → Subir biométrico** y buscá la tarjeta **Lista de Docentes**.
2. En «Seleccioná el sobre auditado de perfiles» elegí el archivo JSON `audit_envelope` (máximo 10 MB).
3. Escribí el **Período Académico** (por ejemplo `II/2026`) y tocá **Generar vista previa**.
4. Revisá la vista previa: total de perfiles, **Identidades** (coincidentes, ausentes, conflictos), advertencias y errores, y la tabla por campo con **Crear**, **Completar**, **Igual**, **Conflicto** y **Sin dato**.
5. Si la vista previa se puede aplicar, tocá **Confirmar e importar**. Aparece «¡Perfiles completados!» con las filas confirmadas y los docentes con campos completados.

Si cambiás el archivo o el período después de la vista previa, hay que generar una nueva.

### 6. Registrar el consentimiento de WhatsApp

La tarjeta **Preferencia de WhatsApp** está en el detalle de cada docente. Muestra si el número está *verificado*, si está *habilitado para envíos* y si hay *baja registrada*; el número se ve enmascarado. El campo «Teléfono de contacto» del docente **no** es consentimiento.

**Registrar o renovar el consentimiento:**

1. Completá **Número de WhatsApp en formato internacional** (por ejemplo `+59170000000`).
2. Completá la **Referencia de evidencia de consentimiento** (dónde consta que el docente aceptó; hasta 500 caracteres).
3. Elegí la **Fuente del consentimiento**: **Registro escrito**, **Registro verbal** u **Otro documento**.
4. Indicá la **Fecha y hora del consentimiento** y tocá **Guardar consentimiento**.

**Registrar una baja:** escribí la **Referencia de evidencia de baja**, tocá **Registrar baja** y confirmá. El docente no recibirá avisos de facturación por WhatsApp hasta que registres un nuevo consentimiento.

Para volver a habilitar a un docente dado de baja, registrá un consentimiento nuevo con **otra referencia de evidencia** y una fecha posterior al consentimiento anterior.

Además, el envío por WhatsApp debe estar permitido en **Administración → Configuración** (sección «Entrega de facturación por WhatsApp», interruptor «Permitir nuevos envíos por WhatsApp oficial»).

### 7. Crear un usuario

1. Abrí **Administración → Usuarios** y tocá **Nuevo Usuario**.
2. En **Identificación** completá **CI \*** y **Rol \*** (**Administrador** o **Docente**).
3. En **Datos Personales** completá **Nombre Completo \*** y, si querés, **Email**.
4. En **Acceso** definí la **Contraseña \*** (la lista de requisitos se tilda a medida que escribís). Si el rol es **Docente**, elegí el **Docente vinculado**.
5. Tocá **Crear Usuario**. Entregale al usuario su CI y la contraseña.

La contraseña debe tener al menos 8 caracteres, una mayúscula, una minúscula y un número. Un usuario nuevo **no** queda obligado a cambiarla en el primer ingreso; si querés forzarlo, usá el reseteo (paso 8).

### 8. Resetear contraseña, activar y desactivar

En la tabla **Lista de Usuarios** (columnas Nombre, CI, Rol, Vinculado a, Estado, Último Login, Acciones; podés filtrar por **Rol** y **Estado** y buscar por nombre o CI):

- **Resetear contraseña** (ícono de flecha circular): se abre «Resetear Contraseña», escribí la **Nueva Contraseña \*** y tocá **Guardar**. Al próximo ingreso el usuario verá **«Debés cambiar tu contraseña»** y tendrá que escribir la contraseña temporal actual, una nueva y su confirmación, y tocar **Establecer nueva contraseña**.
- **Desactivar** (ícono de usuario tachado): pide confirmación («Desactivar usuario»); el usuario no podrá ingresar hasta que lo actives. **Activar** lo reactiva sin confirmación.

### 9. Qué pueden hacer los docentes en su portal

En **Administración → Configuración**, sección «Permisos de Mi Perfil docente», dos interruptores definen qué puede autogestionar un docente: **Editar datos personales y bancarios** y **Subir o eliminar foto propia**. Si están apagados, el docente ve su ficha en modo lectura; los administradores siempre pueden gestionar la foto desde el detalle. Guardá con **Guardar Cambios**.

## Reglas y bloqueos

| Situación | Qué pasa | Qué hacer |
|-----------|----------|-----------|
| Creás un docente sin CI o sin nombre | «CI y nombre completo son obligatorios.» | Completá ambos campos |
| Creás un docente con un CI que ya existe | «Ya existe un docente con CI 12345678» | Buscalo en el listado; si es un duplicado, editá el existente |
| Cambiás el CI a uno que ya pertenece a otro docente | «Ya existe un docente con CI X» | Verificá el CI |
| Cambiás el CI a uno usado por otro usuario | «El CI X ya está en uso por el usuario …» | Resolvé primero el usuario en conflicto |
| El docente tiene más de un usuario del portal vinculado | «No se puede cambiar el CI: el docente tiene N usuarios del portal vinculados; dejá uno solo» | Desactivá o dejá un único usuario del portal para ese docente |
| Un usuario del docente figura como quien registró asistencias de prácticas | «No se puede cambiar el CI: el usuario X figura como quien registró asistencias de prácticas» | No se puede cambiar el CI en ese caso; consultalo con soporte técnico |
| El biométrico ya tiene marcas con el CI nuevo en la misma fecha y hora | «No se puede cambiar el CI: el biométrico ya tiene N marca(s) con el CI X en la misma fecha y hora que las del CI Y» | Revisá qué CI es el correcto en el biométrico antes de corregir |
| Subís una foto que no es JPG, PNG o WEBP, o pesa más de 2 MB | «El contenido del archivo no coincide con un formato de imagen permitido.» u otro error de la foto | Usá una imagen válida de hasta 2 MB |
| **Descargar foto** / **Eliminar foto** sin foto cargada | Los botones están deshabilitados | Primero **Subir foto** |
| Importás perfiles con un archivo que no es JSON | «El importador seguro de perfiles admite únicamente archivos .json audit_envelope.» | Usá el JSON `audit_envelope` |
| El archivo está vacío o pesa más de 10 MB | «El archivo está vacío.» / «El archivo supera el límite de 10 MB.» | Corregí o dividí el archivo |
| La vista previa muestra CI ausentes, duplicados, conflictos o campos a «Crear» | **Confirmar e importar** queda deshabilitado; este flujo no crea docentes | Dalos de alta primero en **Docentes** o corregí el archivo y repetí la vista previa |
| Cambiás el archivo o el período después de la vista previa | «El archivo o el período cambiaron después de la vista previa. Generá una nueva vista previa.» | Generá otra vista previa |
| Número de WhatsApp sin formato internacional | La preferencia no se guarda | Escribilo con `+` y código de país, sin espacios (`+59170000000`) |
| Volvés a dar consentimiento a un docente con baja usando la misma evidencia | No se acepta: hace falta una referencia de evidencia nueva y una fecha posterior | Registrá la nueva evidencia y fecha |
| **Registrar baja** sin referencia de evidencia | El botón está deshabilitado | Completá la **Referencia de evidencia de baja** |
| Creás un usuario sin CI, nombre o contraseña | «CI, nombre y contraseña son obligatorios.» | Completá los campos con \* |
| La contraseña no cumple los requisitos | «La contraseña no cumple: …» con lo que falta | Usá 8+ caracteres con mayúscula, minúscula y número |
| Rol **Docente** sin docente vinculado | «Seleccioná el docente vinculado.» | Elegí el docente (debe existir en el padrón) |
| Creás un usuario con un CI que ya tiene cuenta | «Ya existe un usuario con CI '…'» | Usá **Resetear contraseña** sobre la cuenta existente |
| Intentás desactivar tu propio usuario | «No podés desactivar tu propio usuario» | Pedile a otro administrador que lo haga |

## Preguntas frecuentes

**¿Qué es un alias de CI y dónde lo veo?** Es el registro de un CI anterior de un docente. No hay una pantalla para administrarlos: SIPAD los usa solo por detrás. Se crean (1) al corregir el CI de un docente, para que las facturaciones ya publicadas (que no se pueden modificar) sigan encontrándose en el portal del docente, y (2) al subir el biométrico cuando un CI no coincide con ninguna ficha: el sistema busca al docente por nombre y avisa «Se resolvieron N CI(s) biométrico(s) por nombre (CIs no coincidían entre sistemas).» Si el nombre no coincide, esas marcas no se vinculan.

**¿Cómo hago que un docente deje de entrar sin borrarlo?** Desactivá su usuario en **Administración → Usuarios**. Conserva todo su historial; podés activarlo de nuevo cuando quieras.

**¿Por qué un docente no puede editar su perfil?** Revisá los interruptores de **Administración → Configuración → Permisos de Mi Perfil docente**. Si están apagados, el portal le muestra la ficha en solo lectura.

**¿Perdí la contraseña de un usuario, la puedo ver?** No. Usá **Resetear contraseña**: definís una nueva y el usuario deberá cambiarla en su próximo ingreso.

**¿Puedo importar perfiles para crear docentes nuevos?** No. El importador solo completa campos vacíos de docentes existentes; los docentes nuevos se crean con **Nuevo Docente**.

**¿Un docente dado de baja de WhatsApp puede volver a recibir avisos?** Sí, registrando un nuevo consentimiento con evidencia nueva (paso 6).

## Relacionado

- [Designaciones](designaciones.md) — las materias de cada docente.
- [Cambio de docente](cambio-de-docente.md)
- [Planificador de horarios](planificador-de-horarios.md)
- [Contratos](contratos.md) — los contratos emitidos siguen al docente aunque cambie su CI.
- [Cierre mensual](cierre-mensual.md) — subida del biométrico y publicación de facturación (WhatsApp).
- [Gestión estudiantil](gestion-estudiantil.md) — cuentas del portal de estudiantes (son independientes de los usuarios de esta guía).
- [README del proyecto](../../README.md)
