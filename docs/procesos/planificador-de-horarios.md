# Armar y publicar el horario semanal de un programa

**Para qué sirve.** El **Planificador de horarios** te permite armar, en un borrador, el horario semanal de un programa y un período (de lunes a sábado), asignar un docente a cada bloque, revisar el resultado y publicarlo. Mientras es borrador no cambia nada de lo que se paga. Al publicarlo, sus bloques pasan a regir la planilla y la asistencia regular desde la **fecha efectiva** que elijas, y la revisión publicada queda guardada como historial inmutable.

## Antes de empezar

- **Rol:** administrador. Cualquier otro rol no puede crear ni modificar borradores ni publicar.
- **Dónde está:** menú **Docentes y académico → Planificador de horarios**.
- **Catálogos preparados** en **Docentes y académico → Gestión académica** (pestañas **Programas**, **Ofertas**, **Grupos**, **Aulas** y **Disponibilidad docente**). El planificador solo ofrece:
  - ofertas activas del programa y período del borrador, con horas de teoría o de práctica mayores a cero;
  - grupos activos del mismo programa y período;
  - aulas activas;
  - docentes que tengan la disponibilidad cargada para cubrir todo el bloque.
- **Duración de la hora académica:** en **Administración → Configuración**, campo **Duración de la hora académica (minutos)** (por defecto 45). Se usa para precargar las horas que se pagan de cada bloque nuevo.
- **Importante:** publicar afecta la planilla. El propio planificador lo avisa con el cartel **Publicar afecta la planilla**.

## Paso a paso

### 1. Crear un borrador

1. Abrí **Planificador de horarios** y tocá **Nuevo borrador**.
2. Elegí el **Programa**, escribí el **Período académico** (por ejemplo `II/2026`) y un **Nombre** descriptivo.
3. Tocá **Crear borrador**. Queda seleccionado como **Borrador activo**.

Para cambiar el nombre más adelante, usá **Editar** junto al estado del borrador y **Guardar cambios**. El programa y el período solo se pueden cambiar mientras el borrador no tiene bloques.

Si ya tenés un borrador, elegilo en la lista **Borrador activo**. Con **Importación inicial** se crea un borrador a partir de archivos (ver más abajo).

### 2. Agregar bloques al horario

Un bloque es una clase semanal: una materia, un grupo, un aula, un día y un rango de horas. Hay dos formas de crearlo:

- **Arrastrando:** en el panel **Actividades disponibles**, arrastrá la tarjeta de la materia (con el ícono de agarre) hasta el día y la hora que quieras de la grilla del **Horario semanal**.
- **Con el botón:** tocá **Agregar al horario** en la tarjeta de la materia; el bloque se propone el lunes a las 07:00.

En ambos casos se abre **Agregar bloque**:

1. Revisá **Oferta académica**, **Grupo** y **Aula** (el sistema propone el primer grupo del mismo semestre y la primera aula activa).
2. Elegí la **Actividad** (**Teoría** o **Práctica**), el **Día**, el **Inicio** y el **Fin**. Podés usar los botones de **Duración** (45, 90 o 135 min) para completar el fin.
3. En **Horas académicas que se pagan** podés dejar el campo vacío: se calcula como la duración dividida por la duración de la hora académica, redondeando hacia arriba desde la mitad, con un mínimo de 1. Si escribís un valor (de 1 a 12), ese es el que se paga por clase.
4. Tocá **Guardar bloque**.

Cada bloque muestra materia, grupo, horario, horas, aula y el docente o la etiqueta **Sin docente**. Los colores indican el semestre; el borde punteado marca las prácticas. En el menú de acciones de cada bloque (los tres puntos) tenés **Asignar docente** o **Reemplazar docente**, **Historial de asignaciones**, **Editar bloque** y **Eliminar bloque**.

Arriba de la grilla ves cuatro indicadores: **Bloques**, **Sin docente**, **Horas pagadas** (horas académicas por semana) y **Docentes**.

### 3. Fecha de referencia y carga docente semanal

- El campo **Fecha de referencia** (panel izquierdo) define qué docente se muestra en cada bloque y para qué día se calcula la carga.
- El panel **Carga docente semanal** lista a cada docente con horas totales, de teoría y de práctica. La barra completa equivale a 40 horas por semana; si un docente la supera aparece **Supera la referencia semanal**. Es solo una referencia visual, no un bloqueo.
- Si no hay asignaciones vigentes en esa fecha, el panel muestra **Sin carga**.

### 4. Asignar o reemplazar un docente

1. En el menú del bloque elegí **Asignar docente** (si no tiene docente en la fecha de referencia) o **Reemplazar docente** (si ya tiene).
2. Completá **Vigente desde** (obligatorio) y, si corresponde, **Vigente hasta (opcional)**. Por defecto se propone la fecha de referencia.
3. Buscá y elegí al docente en **Docente compatible**. Solo aparecen quienes tienen disponibilidad completa y no tienen cruces con otros bloques del borrador en ese intervalo.
4. Tocá **Asignar docente** o **Confirmar reemplazo**.

Cuando la fecha cae sobre una asignación existente, el diálogo se convierte en reemplazo y avisa: «Reemplazará a <docente>. La asignación anterior finalizará el <día anterior>.» La asignación anterior termina el día previo a la nueva fecha y la nueva queda abierta o hasta la fecha que indiques.

Para ver quién cubrió el bloque y cuándo, usá **Historial de asignaciones**.

> El cambio de docente sobre horarios ya publicados y vigentes se hace desde **Gestión académica → Cambiar docente** (ver [cambio-de-docente.md](cambio-de-docente.md)). Aquí solo se modifica el borrador.

### 5. Revisar la publicación completa

La publicación siempre es del borrador entero; no se publican bloques sueltos.

1. Con el borrador en estado **Borrador**, tocá **Revisar publicación**.
2. Elegí la **Fecha efectiva** (desde cuándo rige el horario).
3. Tocá **Generar vista previa vinculante**. Verás:
   - **Resumen sellado:** secuencia, cantidad de bloques e intervalos docentes y un código de verificación (digest).
   - Conteos de **Añadidos**, **Retirados**, **Cambiados** y **Reemplazos** respecto de la publicación vigente.
   - **Cambios de carga semanal** por docente.
   - **Publicación bloqueada**, con la lista de problemas, si los hay.
   - **Límite operativo**, con las advertencias sobre cómo afecta la planilla.
4. Opcional: tocá **Simular planilla** para ver cuánto cobraría cada docente en el mes de la fecha efectiva si publicaras este borrador. No publica nada.

### 6. Publicar

1. Si la vista previa no tiene bloqueos, aparece el botón **Publicar borrador completo**. Tocalo.
2. El borrador pasa a **Publicado e inmutable** y se crea una revisión en el historial.

Desde la **fecha efectiva**, los bloques publicados (teoría y práctica) reemplazan en la planilla y en la asistencia regular a las designaciones de la misma materia, grupo y semestre. Cada bloque paga sus horas académicas por clase dictada: la teoría a la tarifa de teoría y la práctica a la tarifa de prácticas. Si cambiás la fecha efectiva o el borrador después de generar la vista previa, tenés que generar una nueva.

### 7. Consultar el historial y clonar una publicación

1. Tocá **Historial de publicaciones**. Las revisiones se listan por período, fecha efectiva y número de revisión (**Rev.**).
2. Elegí una para ver su **Detalle inmutable**: bloques, aulas y la secuencia de docentes de cada uno.
3. Para corregir o preparar un cambio, escribí el **Nombre del nuevo borrador** y tocá **Clonar como borrador editable**. La publicación original no se toca; el nuevo borrador queda seleccionado y listo para editar.

### 8. Archivar un borrador

Un borrador que ya no vas a usar se descarta con **Archivar**, junto al estado del borrador. Un borrador archivado no se puede modificar. Un borrador publicado no se puede archivar.

### 9. Importación inicial

El botón **Importación inicial** crea de una sola vez un borrador a partir de dos archivos Excel. Está pensado para la carga de arranque del período **II/2026**: el alcance es fijo (período II/2026, vigente desde el 21 de agosto de 2026).

1. Tocá **Importación inicial** y elegí el **Programa académico**.
2. Cargá el **Libro oficial de teoría y práctica** y el **Libro salarial de práctica** (ambos `.xlsx`, hasta 20 MiB cada uno).
3. Tocá **Generar vista previa**. Revisá **Registros preparados**, **Advertencias** y **Problemas que impiden aplicar**; cada problema trae su «Siguiente acción».
4. Si hay nombres de docentes o materias de práctica que no coinciden entre archivos, tocá **Resolver coincidencias** y elegí explícitamente cada opción.
5. Cuando no haya problemas, marcá la casilla de **Confirmación final** y tocá **Confirmar y crear borrador**.
6. Tocá **Continuar en el borrador**. El borrador queda creado, pero **no se publica automáticamente**.

La sección **Opciones avanzadas** (archivo técnico de equivalencias) es solo para migraciones preparadas con anterioridad.

## Reglas y bloqueos

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| El borrador está **Publicado e inmutable** o **Archivado** | Los botones de editar, agregar, asignar y eliminar quedan deshabilitados; **Revisar publicación** no aparece | Clonalo desde **Historial de publicaciones** para editar una copia |
| Ya existe un borrador activo con el mismo nombre en el programa y período | «Ya existe un borrador activo con el mismo nombre para el programa y período.» | Usá otro nombre |
| Cambiar programa o período de un borrador con bloques | «No se puede cambiar el programa o período de un borrador que ya tiene bloques.» | Creá un borrador nuevo con el programa y período correctos |
| Bloque fuera de horario | «El bloque debe estar entre las 06:00 y las 23:30.» | Ajustá inicio y fin |
| Duración inválida | Debe usar intervalos de 5 minutos y durar entre 15 minutos y 6 horas | Ajustá la duración |
| El aula es chica para el grupo | «La capacidad del aula es menor que el tamaño esperado del grupo.» | Elegí otra aula |
| Se supera la carga de la oferta | «El bloque excede las horas configuradas para la actividad.» | Reducí la duración o corregí las horas de la oferta en **Gestión académica → Ofertas** |
| La oferta no tiene horas para esa actividad | «La oferta no tiene horas configuradas para este tipo de actividad.» | Elegí la otra actividad o corregí la oferta |
| Oferta y grupo de distinto semestre | «La oferta y el grupo deben pertenecer al mismo semestre.» | Elegí un grupo del semestre de la materia |
| Choque de grupo o aula | «El grupo o el aula ya tiene un bloque superpuesto. Los bloques adyacentes sí están permitidos.» | Cambiá el horario o el aula |
| Editar un bloque que ya tiene docente | «Quite explícitamente las asignaciones antes de modificar un bloque con historial docente.» | (a confirmar) la pantalla no tiene un botón para quitar asignaciones; consultá con soporte antes de rehacer el bloque |
| Eliminar un bloque que ya tiene docente | «Quite explícitamente el historial de asignaciones antes de eliminar el bloque.» | Igual que arriba |
| El docente no tiene disponibilidad que cubra el bloque | «El docente no tiene una disponibilidad activa que cubra completamente este bloque.» | Cargá la disponibilidad en **Gestión académica → Disponibilidad docente** o elegí otro docente |
| El docente ya tiene otro bloque superpuesto | «El docente ya está asignado a otro bloque superpuesto de este borrador durante ese intervalo.» | Elegí otro docente o cambiá el horario |
| El bloque ya tiene docente en ese intervalo | «El bloque ya tiene una asignación docente en ese intervalo efectivo.» | Usá **Reemplazar docente** con una fecha posterior |
| Reemplazo el mismo día en que empezó la asignación | «La fecha de reemplazo debe ser posterior al inicio de la asignación vigente; …» | Elegí una fecha posterior |
| Reemplazar por el mismo docente | «El docente seleccionado ya es el docente vigente del bloque.» | Elegí otro docente |
| No hay docentes en la lista | «No existe un docente con disponibilidad completa y sin cruces para este bloque e intervalo.» | Revisá las fechas, la disponibilidad y los otros bloques del docente |
| Borrador sin bloques | Publicación bloqueada: «El borrador debe contener al menos un bloque.» | Agregá bloques |
| Algún bloque sin docente en la fecha efectiva | Publicación bloqueada: «Cada bloque debe tener exactamente un docente vigente en la fecha efectiva.» | Asigná docente a todos los bloques (el indicador **Sin docente** debe estar en 0) |
| Cobertura docente con huecos, superposiciones o sin cierre abierto | Publicación bloqueada: «La cobertura docente contiene intervalos discontinuos.» / «…superpuestos.» / «La asignación docente final debe quedar abierta.» | Corregí las fechas de las asignaciones para que se encadenen sin huecos y la última quede abierta |
| Fecha efectiva anterior a hoy con datos ya cargados | Publicación bloqueada: «Existen N registros de <asistencias, planillas o facturación> en el rango afectado.» | Elegí una fecha efectiva posterior a esos datos |
| La teoría cambiaría lo que pagan las designaciones | Publicación bloqueada: «N grupo(s) de teoría cambiarían sus horas pagadas respecto de la designación vigente. Corrija los bloques antes de publicar.» | Igualá las horas de los bloques con las de la designación |
| Un bloque de teoría duplica una designación vigente | Publicación bloqueada: «N bloque(s) de teoría coinciden con una designación vigente que se seguiría pagando. Unifique materia, grupo y semestre antes de publicar.» | Corregí materia, grupo o semestre para que coincidan |
| El borrador cambió después de la vista previa | «El borrador o la secuencia cambió desde la vista previa. Genere una nueva vista previa.» | Volvé a tocar **Generar vista previa vinculante** |
| Otra persona publicó al mismo tiempo | «Otra publicación ganó la carrera o el borrador ya fue publicado. Genere una nueva vista previa.» | Recargá y revisá el historial de publicaciones |
| Clonar con un nombre repetido | Mismo mensaje de nombre duplicado | Usá un nombre distinto |

## Preguntas frecuentes

**¿Puedo publicar solo algunos bloques?**
No. La publicación es siempre del borrador completo.

**¿Se puede deshacer una publicación?**
No: las revisiones publicadas son inmutables. Para corregir, clonalas como borrador, ajustá y publicá una nueva revisión con la fecha efectiva que corresponda.

**¿Por qué mi docente no aparece en la lista?**
Solo se listan docentes con disponibilidad que cubra todo el bloque y sin cruces en ese intervalo. Revisá la disponibilidad en **Gestión académica → Disponibilidad docente** y las fechas **Vigente desde** y **Vigente hasta**.

**¿La carga semanal de 40 horas es un límite?**
No, es una referencia visual del panel. El sistema no bloquea por superarla.

**¿Dónde veo el resultado vigente o los choques?**
En **Gestión académica**, pestañas **Horarios** (con **Descargar Excel**; la fuente puede ser **Vigente** o **Borrador**) y **Conflictos y huecos** (**Choques**, **Avisos**, **Sin docente** y docentes con más horas que el umbral).

**¿Qué pasa con los contratos?**
Los contratos toman la carga de los horarios publicados y de las designaciones. Mirá [contratos.md](contratos.md).

## Relacionado

- [Designaciones](designaciones.md)
- [Cambio de docente](cambio-de-docente.md)
- [Contratos](contratos.md)
- [Cierre mensual](cierre-mensual.md)
- [Gestión estudiantil](gestion-estudiantil.md)
- [Docentes y usuarios](docentes-y-usuarios.md)
- [README del proyecto](../../README.md)
