# Cambiar de docente una materia (designaciones y horario publicado)

Cuando un docente deja una materia y otro la toma, hay que decidir **desde qué día** cobra cada uno y asegurarse de que la planilla lo refleje. En SIPAD esto se hace de dos maneras según de dónde salga el pago de esa materia: **Gestión académica → Cambiar docente** mueve las **designaciones**, y el **Planificador de horarios** (**Reemplazar docente**) cambia al docente de un bloque de un **horario publicado**. Esta guía explica cuándo usar cada uno, cómo se hace, qué fecha poner y qué efecto tiene sobre la planilla y los contratos.

## Antes de empezar

- **Rol**: administrador.
- **Dónde está**:
  - **Docentes y académico → Gestión académica**, pestaña **Cambiar docente**.
  - **Docentes y académico → Planificador de horarios**, menú ⋮ de cada bloque (**Reemplazar docente**, **Historial de asignaciones**).
- **Requisitos**:
  - El docente entrante tiene que existir en **Docentes**.
  - Tené la **fecha del cambio** definida: es el primer día en que cobra el docente entrante. El saliente cobra hasta el día anterior.
  - Antes de aplicar, revisá que no haya planilla **aprobada** ni facturación **publicada** que cubra esa fecha (ver «Reglas y bloqueos»).

### ¿Cuál de las dos herramientas uso?

| Si la materia se paga… | Usá | Qué cambia |
|---|---|---|
| Desde una **designación** (lo habitual: cargada con **Designaciones** → importar o **Nueva designación**) | **Gestión académica → Cambiar docente** | Termina la designación del saliente el día anterior y crea una designación idéntica para el entrante desde la fecha del cambio. |
| Desde un **horario publicado** en el Planificador (los bloques publicados reemplazan a las designaciones de la misma materia, grupo y semestre) | **Planificador de horarios → Reemplazar docente**, y después volver a publicar | Cierra la asignación del saliente el día anterior y abre la del entrante en el bloque del borrador; el cambio rige cuando se publica el borrador. |
| Desde las dos cosas (hay designación **y** horario publicado de esa materia) | Las dos | Cambiar docente avisa: «X (G) se paga desde el horario publicado: cambiá también el docente en el módulo de horarios para que la planilla lo refleje.» |

Si no sabés cuál aplica, corré primero la **Vista previa** de **Cambiar docente**: si la materia se paga desde el horario publicado, lo dice en **Avisos**.

## Paso a paso

### A. Cambiar el docente de las designaciones (Gestión académica → Cambiar docente)

1. Abrí **Docentes y académico → Gestión académica** y entrá a la pestaña **Cambiar docente**.
2. Completá el formulario:
   - **Período académico**: viene precargado con `II/2026`. Corregilo si el cambio es de otro período.
   - **Fecha del cambio**: viene con la fecha de hoy. Debajo, el sistema escribe «El docente saliente cobra hasta el AAAA-MM-DD» (el día anterior).
   - **Docente saliente** y **Docente entrante**: buscá por nombre y elegí.
   - **Qué cambia**: dejá «Todas sus designaciones activas en esa fecha (N)» para pasar todas las materias del saliente, o elegí una sola materia de la lista (se muestra materia, semestre, grupo, tipo y horario). Solo aparecen las designaciones que siguen vigentes en la fecha del cambio.
3. Hacé clic en **Vista previa**. Cualquier cambio que hagas después en el formulario borra la vista previa y hay que generarla de nuevo.
4. Revisá el resultado:
   - **El cambio no se puede aplicar**: lista los bloqueos en rojo. Corregí lo que indican (ver «Reglas y bloqueos») y volvé a generar la vista previa.
   - **Avisos**: informativos (por ejemplo, que la materia se paga desde el horario publicado).
   - **Planillas para regenerar**: planillas ya generadas que quedan desactualizadas; las regenerás después de aplicar.
   - **Designaciones que cambian**: por cada materia, «saliente hasta … , entrante desde …».
   - **Pago base de M/AAAA (antes de descuentos por asistencia)**: tabla con, para cada docente, **Horas antes**, **Horas después**, **Antes**, **Después** y **Diferencia** (en Bs), más el **Total**. Es una estimación del mes de la fecha del cambio; no incluye descuentos por asistencia.
5. Si todo está bien, hacé clic en **Aplicar cambio**. El botón solo se habilita con una vista previa vigente y sin bloqueos.
6. En el cuadro **¿Aplicar el cambio de docente?** confirmá con **Aplicar cambio**.
7. Aparece **Cambio aplicado**: cuántas designaciones terminan el día anterior y cuántas se crearon para el entrante, y, si corresponde, «Regenerá: …».
8. Si hay planillas para regenerar, andá a **Cierre mensual → Planilla** y regenerá esas planillas (teoría o práctica, según el aviso).
9. Verificá el resultado en **Designaciones**: la del saliente figura con fecha de fin el día anterior y la del entrante aparece nueva, desde la fecha del cambio.

Qué crea el sistema: la designación del entrante copia materia, semestre, grupo, tipo, horario y horas de la original; empieza en la fecha del cambio y termina cuando terminaba la original. La designación del saliente queda con fecha de fin = fecha del cambio − 1 día. El cambio queda en el **Registro de actividad**.

### B. Reemplazar al docente de un bloque en el Planificador de horarios

El Planificador trabaja con **borradores**: un horario publicado no se edita. Para cambiar al docente de un bloque ya publicado, se clona la publicación a un borrador, se reemplaza el docente y se vuelve a publicar con la fecha del cambio.

1. Abrí **Docentes y académico → Planificador de horarios**.
2. Si el horario que querés cambiar ya está publicado: hacé clic en **Historial de publicaciones**, elegí la revisión, escribí el **Nombre del nuevo borrador** y hacé clic en **Clonar como borrador editable**. Si ya tenés un borrador, elegilo en **Borrador activo**.
3. Poné en **Fecha de referencia** el día del cambio (define qué docente se muestra en cada bloque).
4. En el bloque, abrí el menú ⋮ (**Acciones del bloque …**) y elegí **Reemplazar docente** (si el bloque ya tiene docente en esa fecha) o **Asignar docente** (si dice **Sin docente**). Las dos opciones solo están habilitadas en un borrador editable.
5. En el cuadro completá:
   - **Vigente desde**: el primer día del docente entrante.
   - **Vigente hasta (opcional)**: dejalo vacío salvo que sea un reemplazo temporal.
   - **Docente compatible**: solo se listan docentes con disponibilidad completa para ese bloque y sin cruces en el intervalo.
6. Si hay un docente vigente, el cuadro avisa «Reemplazará a NOMBRE. La asignación anterior finalizará el AAAA-MM-DD.». Confirmá con **Confirmar reemplazo** (o **Asignar docente** si no había uno).
7. Para auditar los cambios de un bloque, abrí ⋮ → **Historial de asignaciones**: lista cada docente con su rango de fechas («Sin fecha final» si sigue abierto).
8. Cuando termines, hacé clic en **Revisar publicación**:
   1. Poné la **Fecha efectiva** (normalmente, la misma fecha del cambio).
   2. Hacé clic en **Generar vista previa vinculante** y revisá el resumen (**Añadidos**, **Retirados**, **Cambiados**, **Reemplazos**) y los **Cambios de carga semanal**.
   3. Opcional pero recomendado: **Simular planilla**. Calcula cuánto cobraría cada docente en el mes de la fecha efectiva si publicás este borrador (**Pago base** antes de descuentos por asistencia). No publica nada.
   4. Si no hay bloqueos, hacé clic en **Publicar borrador completo**.
9. Regenerá las planillas del mes en **Cierre mensual → Planilla** si ya estaban generadas.

Ver el detalle del Planificador en [planificador-de-horarios.md](planificador-de-horarios.md).

## Reglas y bloqueos

### Cambiar docente (designaciones)

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| Falta algún campo del formulario | **Vista previa** queda deshabilitado | Completá período, fecha, docente saliente y entrante. |
| El docente saliente no tiene designaciones activas en esa fecha | «El docente saliente no tiene designaciones activas en esa fecha» (o el selector avisa «Este docente no tiene designaciones activas en … para esa fecha.») | Revisá el período y la fecha. |
| El entrante ya es el titular | «…: el docente entrante ya es el titular de esta designación.» | Elegí otro docente entrante. |
| El entrante ya tiene esa materia y grupo en el período | «…: el docente entrante ya tiene una designación de esta materia y grupo.» | Revisá en **Designaciones**; no se puede duplicar. |
| La fecha del cambio es el día de inicio o anterior | «…: la designación empieza el AAAA-MM-DD; el cambio debe ser posterior a esa fecha.» | Elegí una fecha posterior al inicio. |
| La designación ya terminó antes de la fecha del cambio | «…: la designación terminó el AAAA-MM-DD.» | Elegí una fecha dentro de la vigencia. |
| El saliente tiene asistencia registrada desde la fecha del cambio | «…: el docente saliente tiene asistencia registrada desde la fecha del cambio (fechas). Revisá la fecha del cambio.» | Poné una fecha posterior a su última asistencia. |
| La planilla de un mes que cubre el cambio está **aprobada** | «La planilla de teoría M/AAAA ya está aprobada y cubre la fecha del cambio. Rechazala o elegí una fecha posterior.» | Rechazá la planilla en **Planilla** o elegí una fecha posterior. |
| La facturación de un mes que cubre el cambio está **publicada** | «La facturación de teoría M/AAAA ya está publicada y cubre la fecha del cambio.» | Elegí una fecha posterior al mes publicado. |
| Hay planillas generadas (no aprobadas) que cubren el cambio | No bloquea; **Planillas para regenerar** | Regeneralas después de aplicar. |
| Otro cambio tocó las mismas designaciones al mismo tiempo | «Otro cambio modificó estas designaciones al mismo tiempo. Generá una nueva vista previa.» | Volvé a generar la **Vista previa** y aplicá de nuevo. |
| La materia se paga desde un horario publicado | No bloquea; aviso «…se paga desde el horario publicado: cambiá también el docente en el módulo de horarios para que la planilla lo refleje.» | Hacé también el reemplazo en el Planificador (sección B). |

### Reemplazar docente en el Planificador

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| El horario está publicado o archivado | **Asignar/Reemplazar docente** aparece deshabilitado | Clonalo como borrador desde **Historial de publicaciones**. |
| El docente no tiene disponibilidad que cubra el bloque | No aparece en **Docente compatible**; si se fuerza, «El docente no tiene una disponibilidad activa que cubra completamente este bloque.» | Elegí otro docente o cargá su disponibilidad en **Gestión académica → Disponibilidad docente**. |
| El docente ya está en otro bloque que se superpone | «El docente ya está asignado a otro bloque superpuesto de este borrador durante ese intervalo.» | Elegí otro docente o cambiá el intervalo. |
| La fecha coincide con el inicio de la asignación vigente | «La fecha de reemplazo debe ser posterior al inicio de la asignación vigente; corrija o elimine explícitamente la fila iniciada ese día.» | Elegí una fecha posterior al inicio de la asignación vigente. |
| No hay asignación inmediatamente antes de la fecha | «No existe una asignación activa inmediatamente antes de la fecha de reemplazo.» | Usá **Asignar docente** con una fecha en que no haya docente, o revisá el **Historial de asignaciones**. |
| El docente elegido ya es el vigente | «El docente seleccionado ya es el docente vigente del bloque.» | Elegí otro docente. |
| El bloque ya tiene docente en ese intervalo | «El bloque ya tiene una asignación docente en ese intervalo efectivo.» | Usá **Reemplazar docente** o cambiá las fechas. |
| Al publicar, un bloque no tiene exactamente un docente en la fecha efectiva | **Publicación bloqueada**: «Cada bloque debe tener exactamente un docente vigente en la fecha efectiva.» | Asigná docente a los bloques que dicen **Sin docente** (indicador **Sin docente** arriba). |
| Al publicar, hay huecos o superposiciones entre asignaciones | «La cobertura docente contiene intervalos discontinuos.» / «…superpuestos.» | Corregí las fechas en el **Historial de asignaciones**. |
| La última asignación del bloque tiene fecha final | «La asignación docente final debe quedar abierta.» | Dejá vacío **Vigente hasta** en la última asignación. |
| La fecha efectiva es pasada y ya hay asistencia, planillas o facturación en ese rango | **Publicación bloqueada**: «Existen N registros de asistencias regulares en el rango afectado.» (o planillas, publicaciones/revisiones de facturación) | Usá una fecha efectiva posterior, o rechazá/ajustá primero lo ya generado. |
| Los bloques de teoría cambiarían las horas pagadas de la designación | «N grupo(s) de teoría cambiarían sus horas pagadas respecto de la designación vigente. Corrija los bloques antes de publicar.» | Igualá las horas del bloque con las de la designación. |
| Un bloque de teoría coincide con una designación que se seguiría pagando | «N bloque(s) de teoría coinciden con una designación vigente que se seguiría pagando. Unifique materia, grupo y semestre antes de publicar.» | Unificá nombre de materia, grupo y semestre. |

### Efecto sobre la planilla y los contratos

- **Planilla**: los días anteriores a la fecha del cambio se pagan al saliente y desde la fecha del cambio, al entrante. Cada designación (o bloque publicado) paga con su propio rango de fechas. Si la planilla del mes ya estaba generada, regenerala.
- **Qué se regenera o se bloquea**: las planillas **generadas** (todavía no aprobadas) de los meses afectados solo piden regenerarse; las **aprobadas** y la facturación **publicada** bloquean el cambio.
- **Contratos**: el cambio de docente **no modifica contratos ya emitidos**. En el Planificador, el propio sistema aclara que «los contratos y la facturación siguen usando las designaciones». La designación nueva del entrante aparece sin **Contrato emitido**: emitíle su contrato desde **Contratos** (ver [contratos.md](contratos.md)).

## Preguntas frecuentes

**¿Qué fecha tengo que poner?**
La del primer día en que enseña el docente entrante. Ese día el saliente ya no cobra. Si el saliente dictó clases ese día o después, el sistema bloquea el cambio: poné una fecha posterior a su última asistencia.

**¿Puedo ver cuánto cambia el pago antes de aplicar?**
Sí. La **Vista previa** muestra el pago base del mes del cambio (antes de descuentos por asistencia) con **Antes**, **Después** y **Diferencia** por docente. En el Planificador, **Simular planilla** hace lo mismo para una publicación.

**Me equivoqué y apliqué el cambio con la fecha incorrecta. ¿Se puede deshacer?**
No hay un botón para deshacerlo. Las designaciones resultantes se corrigen en **Designaciones** con **Editar** (fechas) siempre que ningún mes cubierto esté pagado y la designación no tenga contrato emitido; si el mes ya está aprobado o publicado, esas ediciones también se bloquean (ver [designaciones.md](designaciones.md)).

**¿Cambiar docente toca el contrato del docente saliente?**
No. El contrato emitido no cambia; si hace falta ajustarlo, se hace con una adenda desde **Contratos**.

**Cambié al docente en el Planificador pero la planilla no se movió.**
El reemplazo recién rige cuando **publicás** el borrador con la **Fecha efectiva** correcta. Después, regenerá la planilla del mes.

**¿Puedo cambiar solo una materia del docente?**
Sí: en **Qué cambia** elegí esa materia en lugar de «Todas sus designaciones activas en esa fecha».

## Relacionado

- [Designaciones](designaciones.md)
- [Planificador de horarios](planificador-de-horarios.md)
- [Contratos](contratos.md)
- [Cierre mensual](cierre-mensual.md)
- [Docentes y usuarios](docentes-y-usuarios.md)
- [README del proyecto](../../README.md)
