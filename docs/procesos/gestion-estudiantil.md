# Gestionar estudiantes, rematrícula y cursos intensivos

## Para qué sirve

El sistema académico anterior sigue siendo el registro oficial; SIPAD lo complementa. Con esta guía vas a cargar la malla curricular y el historial de los estudiantes, entregarles una cuenta del portal, abrir la ventana de rematrícula, procesar las solicitudes que llegan (marcarlas como realizadas u observarlas), abrir cursos de verano e invierno, calcular cuántos grupos conviene abrir y controlar los documentos migratorios de los estudiantes extranjeros. SIPAD **no cobra nada**: los montos que ves son informativos y el pago se verifica en caja.

## Antes de empezar

- **Rol:** solo administradores. Todas las pantallas de este grupo y sus APIs son exclusivas de admin.
- **Dónde está en el menú:** grupo **Gestión estudiantil** de la barra lateral, con estos ítems:
  **Estudiantes**, **Rematrícula**, **Cursos intensivos**, **Apertura de grupos**, **Documentos migratorios**, **Malla curricular** e **Importar historial**.
- **Orden recomendado la primera vez:** **Malla curricular** → **Importar historial** → **Estudiantes** (claves del portal) → **Documentos migratorios** (lista) → **Rematrícula** (ventana) → **Apertura de grupos**.
- **Grupos y cupos del período:** los grupos del período a rematricular (código, turno, semestre y capacidad) se cargan en **Docentes y académico → Gestión académica**, no acá. Sin grupos, el estudiante no puede elegir dónde cursar.
- **Qué ven los estudiantes:** entran por `/estudiante/login` con su número de documento. Su portal tiene: **Inicio**, **Historial académico**, **Rematrícula**, **Mi horario**, **Cursos de verano e invierno** y **Cambiar contraseña**. Es una sesión independiente de la de admin/docente.

## Paso a paso

### 1. Cargar la malla curricular

1. Abrí **Gestión estudiantil → Malla curricular**.
2. Si todavía no hay malla, aparece «Todavía no hay una malla cargada». Tocá **Cargar malla Medicina 510-01**. (También se carga sola la primera vez que importás un historial.)
3. Revisá el tablero: tarjetas de **Materias**, **Horas**, **Créditos** y **Electivas**, y una columna por semestre con cada materia (HT, HP y créditos).

Para **editar la malla**:

1. Tocá **Editar malla**. Aparece el aviso «Los cambios aplican a la malla vigente para todos los estudiantes (semestre a cursar, recursados y materias fuera de malla). Quitar una materia no borra el historial de nadie.»
2. En cada semestre podés **agregar** una materia, **editar** una existente, **reordenarla** (subir/bajar) o **quitarla**. En el formulario completás **Nombre**, **Semestre**, **Sigla**, **Horas teóricas (HT)**, **Horas prácticas (HP)** y **Créditos (CR)**, y marcás «Es una electiva (puede ir sin sigla)» si corresponde. Tocá **Guardar**.
3. Para sumar un semestre al final tocá **Agregar semestre**; para sacar el último (solo si está vacío) tocá **Quitar semestre N (vacío)**.
4. Al quitar una materia se pide confirmación («Quitar materia de la malla»): «Deja de ofrecerse y de contarse para la rematrícula. El historial de los estudiantes no se borra.»
5. Tocá **Terminar edición** cuando termines. Cada cambio queda en el registro de actividad.

Para **generar las ofertas de un período** a partir de la malla:

1. Con **Editar malla** activo, tocá **Generar ofertas**.
2. Escribí el **Período** (`I/2027`, `II/2027`, `INV/2027` o `VER/2027`) y tocá **Generar ofertas**.
3. Se crean las ofertas con la materia, el semestre y las horas de la malla. Las que ya existían no se tocan; las electivas sin sigla aparecen como «No generadas». Después se ajustan en **Gestión académica**.

### 2. Importar el historial académico

1. Abrí **Gestión estudiantil → Importar historial** (también hay un botón **Importar historial** arriba en **Estudiantes**).
2. En «1. Elegir archivo» seleccioná el CSV `gestion-AAAA.csv` exportado del sistema académico (48 columnas) y tocá **Ver vista previa**. Nada se guarda todavía.
3. En «2. Revisar y confirmar» mirá los conteos, los **Períodos del archivo**, las **Advertencias (se importan igual)** y las filas con error («N fila(s) con error no se importan», con su número de fila para corregir en el sistema académico).
4. Si todo está bien, tocá **Importar N fila(s)**. Aparece «Historial importado desde …».
5. Abajo, **Importaciones realizadas** muestra cada archivo, sus períodos, cuántas materias fueron nuevas o actualizadas y quién lo hizo.

Podés importar el mismo archivo, o uno más nuevo, las veces que haga falta: los estudiantes se reconocen por su documento y cada materia por su número de registro, así que no se duplican y los cambios (por ejemplo de *en curso* a *aprobada*) se actualizan.

### 3. Consultar un estudiante

1. Abrí **Gestión estudiantil → Estudiantes**.
2. Buscá por **nombre o documento**, o filtrá por **Estado de inscripción** y **Nacionalidad** (**Bolivianos** / **Extranjeros**). Los extranjeros llevan la insignia *Extranjero*.
3. Tocá el nombre para abrir el detalle (título **Detalle de estudiante**). Ahí ves **Datos personales**, la tarjeta **Portal del estudiante**, **Documentos migratorios** (solo extranjeros) y el **Historial académico** agrupado por período, con grupo, docente, estado y nota. Las materias que no están en la malla llevan la insignia *Fuera de malla*; los cursos de verano/invierno, *Curso intensivo*.

### 4. Crear la cuenta del portal y entregar la clave temporal

**Un estudiante:**

1. En el detalle del estudiante, tarjeta **Portal del estudiante** (estado *Sin cuenta*), tocá **Generar clave temporal**.
2. Se abre «Clave temporal generada». Copiala con **Copiar clave** y entregásela **en persona**: se muestra una sola vez.
3. El estudiante entra con su número de documento y esa clave, y debe cambiarla en su primer ingreso (mientras tanto el estado es *Con clave temporal*).

**Varios a la vez (hasta 100):**

1. En **Estudiantes**, marcá las casillas de los estudiantes (o **Seleccionar la página**).
2. Tocá **Generar claves temporales (N)**.
3. En el diálogo «N claves temporales generadas» tocá **Descargar CSV** (`claves-temporales-portal.csv`) antes de cerrar con **Listo**.

**Reemplazar una clave o bloquear el acceso:**

- **Generar nueva clave temporal** pide confirmación: la clave actual deja de funcionar y se cierran sus sesiones abiertas.
- **Deshabilitar cuenta** / **Habilitar cuenta** cierra o permite el ingreso; deshabilitar también cierra las sesiones abiertas.

### 5. Abrir la ventana de rematrícula

1. Abrí **Gestión estudiantil → Rematrícula**. Arriba está **Ventanas de rematrícula**.
2. Tocá **Nueva ventana** y completá **Período a rematricular** (por ejemplo `I/2027`; formatos válidos: `I/AAAA`, `II/AAAA`, `INV/AAAA`, `VER/AAAA`), **Desde** y **Hasta**. Tocá **Guardar**. Las fechas se interpretan en hora de Bolivia.
3. La ventana aparece con su estado: *Programada*, *Abierta* o *Cerrada*, y los conteos de solicitudes pendientes, observadas y realizadas.
4. Para corregir fechas usá **Cambiar fechas** (el período no se puede cambiar).

Fuera de la ventana el estudiante solo ve su historial y el estado de su solicitud. Dentro de ella, en **Rematrícula** de su portal ve el semestre que le corresponde, elige su grupo y, si tiene, las materias a recursar o pendientes con su grupo, y envía la solicitud (**Enviar solicitud**; luego **Guardar cambios** mientras la ventana siga abierta).

### 6. Procesar las solicitudes

1. En **Rematrícula** elegí la ventana (tocá su fila) y filtrá la bandeja por **Estado** (empieza en *Pendientes*), **Semestre**, **Nacionalidad** o **Buscar** (nombre o documento).
2. Tocá una solicitud para abrir el detalle. Revisá:
   - **Documentos migratorios** (solo extranjeros), con la insignia *Regularizado* / *No regularizado*.
   - **Grupos elegidos**: el grupo del semestre y uno por cada materia *Recursado* o *Pendiente*.
   - **Beca y montos (informativo)**: categoría, promedio del último período, cuota × cuotas y costo del recursado.
   - **Contacto** del estudiante.
3. Registrá la rematrícula en el sistema académico anterior y volvé a SIPAD. Si todo está correcto, tocá **Marcar como realizada**.
4. Si hay algo para corregir, tocá **Observar**, elegí el **Motivo** (**Documentos de migración**, **Pago pendiente** u **Otro**), escribí el **Mensaje para el estudiante** (mínimo 5 caracteres) y tocá **Enviar observación**. El estudiante ve el motivo y el mensaje en su portal; mientras la ventana siga abierta puede corregir y la solicitud vuelve a *Pendiente*.
5. Para deshacer una solicitud ya realizada u observada, tocá **Reabrir como pendiente**.

**Becas y montos (informativos):**

| Categoría | Condición | Cuota |
|-----------|-----------|-------|
| Beca Fundador | promedio mayor a 64 | 850 Bs × 5 cuotas |
| Beca Desafío | promedio mayor a 61 | 1300 Bs × 5 cuotas |
| Sin beca | el resto | 1600 Bs × 5 cuotas |

Las dos becas exigen **no haber reprobado nunca una materia**; el promedio es el del último período regular con notas finales. El **recursado** cuesta 1200 Bs por materia elegida y se cobran como máximo 3. Antes de marcar como realizada una solicitud con recursado, verificá el pago en caja.

### 7. Abrir cursos de verano e invierno

1. Abrí **Gestión estudiantil → Cursos intensivos**.
2. **Primero configurá los montos** en la tarjeta **Montos de cursos intensivos**: tocá **Configurar montos** (o **Cambiar montos**) y completá **Tarifa por hora de teoría (Bs)**, **Tarifa por hora de práctica (Bs)**, **Factor de margen** (1 o más; por defecto 1,10), **Precio mínimo (Bs)** (1200 por defecto) y **Precio máximo (Bs)** (1600 por defecto). Tocá **Guardar montos** y confirmá. Son tarifas propias, independientes de la planilla.
3. Tocá **Abrir curso** y completá **Período** (`VER/2027` verano o `INV/2027` invierno), **Materia**, **Docente**, **Cupos**, **Inscripción desde** / **Inscripción hasta** y, si querés, las **Horas de teoría** y **Horas de práctica** (vacías = las de la malla).
4. Los estudiantes se inscriben desde **Cursos de verano e invierno** en su portal. Pueden inscribirse quienes tienen la materia reprobada y nunca aprobada, o solo retirada; pueden cancelar mientras el curso esté abierto.
5. Tocá un curso de la lista para ver el detalle: docente, inscritos, horas, **Pago docente**, **Precio por estudiante** y la lista de estudiantes inscritos.
6. Para ajustar un curso abierto usá **Editar curso** (el período y la materia no se pueden cambiar).
7. Al terminar la inscripción tocá **Cerrar inscripción** y confirmá: el precio queda **fijo** y ya no se puede inscribir, cancelar ni editar. No se puede deshacer.

**Cómo se calcula el precio:** pago docente = horas teóricas × tarifa teórica + horas prácticas × tarifa práctica. Precio por estudiante = pago docente × factor de margen ÷ inscritos, redondeado y limitado entre el mínimo y el máximo. Mientras la inscripción está abierta el precio es *estimado* (baja si se inscriben más); al cerrarla queda *fijo*.

### 8. Calcular la apertura de grupos

1. Abrí **Gestión estudiantil → Apertura de grupos**.
2. En **Parámetros** elegí la **Ventana de rematrícula**. Si querés, cambiá **Estudiantes por grupo** (entre 1 y 200; 40 por defecto) y tocá **Guardar**.
3. Leé la tabla por **Semestre** y **Turno**: **Solicitudes** (pendientes y realizadas), **Recursantes**, **Grupos sugeridos** (solicitudes ÷ tamaño de grupo, redondeado hacia arriba), **Grupos creados**, **Capacidad** y **Diferencia** (faltan, sobran o correcto). El pie muestra el total de grupos por abrir y de más.
4. Los grupos que falten se crean en **Gestión académica**. Los recursantes se muestran solo para informar: no suman a los grupos sugeridos.

### 9. Controlar documentos migratorios

**Definir la lista de documentos** (una vez, y cuando cambie la exigencia):

1. Abrí **Gestión estudiantil → Documentos migratorios**.
2. En **Nuevo documento** escribí el **Nombre del documento**, marcá **Tiene vencimiento** si corresponde y tocá **Agregar documento**.
3. En la tabla podés **Renombrar**, cambiar **Tiene vencimiento**, subir/bajar el orden, **Desactivar** (deja de exigirse pero conserva lo registrado) o **Reactivar**.

**Registrar lo que presentó un estudiante extranjero:**

1. Abrí el detalle del estudiante (**Estudiantes** → su nombre). La tarjeta **Documentos migratorios** solo aparece para extranjeros.
2. En cada documento tocá **Registrar** (o **Editar**), completá **Vence el** si tiene vencimiento y **Notas (opcional)**, y **Guardar**. **Quitar** elimina el registro.
3. El estudiante queda *Regularizado* cuando presentó todos los documentos activos y ninguno está vencido (un documento que vence hoy sigue vigente). Si no hay documentos activos, todos cuentan como regularizados.

## Reglas y bloqueos

| Situación | Qué pasa | Qué hacer |
|-----------|----------|-----------|
| Intentás **Marcar como realizada** la rematrícula de un extranjero no regularizado | El botón está deshabilitado y, si se fuerza, la API responde «Documentos migratorios pendientes: Visa de estudiante, Carnet de extranjero (vencido el 15/10/2026)» | Registrá o renová los documentos en el detalle del estudiante y volvé a marcar la solicitud |
| Creás una ventana para un período que ya tiene una | «Ya existe una ventana de rematrícula para I/2027» | Usá **Cambiar fechas** sobre la ventana existente |
| La fecha **Hasta** es anterior a **Desde** | «La fecha de fin debe ser igual o posterior a la de inicio» | Corregí las fechas |
| **Observar** con un mensaje corto | El botón **Enviar observación** queda deshabilitado | Escribí al menos 5 caracteres |
| Marcar una solicitud con el estado en el que ya está | «La solicitud ya está en ese estado» | Recargá la bandeja; la solicitud ya fue procesada |
| **Reabrir** una solicitud que ya está pendiente | «La solicitud ya está pendiente» | No hace falta; recargá la bandeja |
| El estudiante envía su solicitud y el grupo se llenó | «El grupo X ya no tiene cupos» (un grupo sin capacidad cargada no tiene límite) | Pedile que elija otro grupo, o ampliá la capacidad en **Gestión académica** |
| El estudiante intenta enviar con la ventana cerrada | «La rematrícula no está abierta» | Revisá las fechas de la ventana |
| El estudiante ya tiene la rematrícula realizada | «Tu rematrícula ya fue realizada»; el portal queda bloqueado | Si hubo un error, usá **Reabrir como pendiente** |
| El estudiante no tiene historial importado | «No encontramos tu historial; acercate a Registro» | Importá su gestión en **Importar historial** |
| Una solicitud observada recupera su lugar y el grupo ya se llenó | Al reabrirla o volver a marcarla se revalidan los cupos y puede dar «El grupo X ya no tiene cupos» | Ampliá el cupo o pedile otro grupo |
| Tocás **Abrir curso** sin montos configurados | El botón está deshabilitado; «Configurá los montos de cursos intensivos para poder abrir un curso» | Tocá **Configurar montos** y cargá las tarifas por hora |
| Abrís un curso de una materia que ya tiene curso en ese período | «Ya existe un curso intensivo de MRF 0100 para VER/2027» | Editá el curso existente |
| Las horas de teoría y práctica son 0 a la vez | «Las horas de teoría y práctica no pueden ser ambas cero» | Indicá las horas o completá la malla |
| Bajás los **Cupos** por debajo de los inscritos | «La capacidad no puede ser menor a los N inscritos» | Subí el cupo o dejalo como está |
| Editás o inscribís en un curso con inscripción cerrada | «El curso intensivo está cerrado» | Ya no se puede; el precio quedó fijo |
| El **Precio mínimo** supera al **Precio máximo** | «El precio mínimo no puede superar al máximo» | Corregí los montos |
| Seleccionás más de 100 estudiantes para generar claves | **Generar claves temporales** queda deshabilitado: «Podés generar hasta 100 claves por vez» | Quitá estudiantes de la selección y repetí por tandas |
| Agregás un documento migratorio con nombre repetido | «Ya existe un documento con ese nombre» | Usá otro nombre o reactivá el existente |
| Registrás un documento con vencimiento sin fecha | «La fecha de vencimiento es obligatoria para este documento» | Completá **Vence el** |
| Registrás documentos de un estudiante que no es extranjero | «El estudiante no es extranjero» | No corresponde; la tarjeta solo aparece para extranjeros |
| Reimportás un CSV que cambió entre la vista previa y la confirmación | La importación se rechaza (409) | Volvé a elegir el archivo y generá otra vista previa |

## Preguntas frecuentes

**¿Perdí la clave temporal de un estudiante?** No se puede volver a ver. Tocá **Generar nueva clave temporal**: la anterior deja de funcionar y se cierran sus sesiones.

**¿Puedo importar el historial varias veces?** Sí. Reimportar actualiza lo que cambió y nunca duplica estudiantes ni materias. Las filas con error se omiten y se listan con su número de fila.

**¿Quitar una materia de la malla borra el historial?** No. Solo deja de ofrecerse y de contarse para la rematrícula; el historial de cada estudiante queda intacto.

**¿SIPAD cobra la rematrícula o los cursos intensivos?** No. Los montos son informativos; Registro verifica el pago en caja antes de marcar como realizada una solicitud con recursado.

**¿Qué materias le toca recursar a un estudiante?** Las que tienen un *Reprobado* y ningún *Aprobado*. Las pendientes sin cargo son las de semestres anteriores que solo tienen *Retirado*. Las materias en curso no aparecen.

**¿El horario que ve el estudiante cuándo aparece?** En **Mi horario** del portal, cuando su rematrícula pasa a *Realizada*. Usa el horario publicado vigente o, antes de que empiecen las clases, el próximo publicado.

## Relacionado

- [Docentes y usuarios](docentes-y-usuarios.md) — los docentes que asignás a los cursos intensivos.
- [Planificador de horarios](planificador-de-horarios.md) — de donde sale el horario publicado que ve el estudiante.
- [Designaciones](designaciones.md)
- [Cambio de docente](cambio-de-docente.md)
- [Contratos](contratos.md)
- [Cierre mensual](cierre-mensual.md)
- [README del proyecto](../../README.md) — secciones «Gestión estudiantil» y «Portal del estudiante y rematrícula».
