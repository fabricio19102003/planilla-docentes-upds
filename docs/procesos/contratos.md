# Emitir contratos docentes y consultar su historial

**Para qué sirve.** La pantalla **Contratos** emite los contratos docentes en PDF, de a uno o por lote, a partir de la carga vigente de cada docente en el período académico activo. Cada emisión queda guardada en un **Historial Inmutable**: el primer contrato de un docente en el período es el **Original**, y si algo del contrato cambia después se emite una **versión nueva** del contrato completo, sin tocar los documentos anteriores. UPDS Cobija no usa adendas. Si volvés a emitir y nada cambió, el sistema te devuelve el mismo contrato en lugar de crear otro.

## Antes de empezar

- **Rol:** administrador.
- **Dónde está:** menú **Docentes y académico → Contratos** (título de la página: **Contratos Docentes**). Los datos del comitente y las tarifas se configuran en **Administración → Configuración**.
- **Prerrequisitos:**
  - El docente debe tener un CI real. Los docentes con CI provisorio (`TEMP-…`) no aparecen ni reciben contrato; vinculalos primero a un CI real (ver [docentes-y-usuarios.md](docentes-y-usuarios.md)).
  - El docente debe tener carga efectiva en el período activo: designaciones cargadas o bloques de horario publicados con su asignación (ver [designaciones.md](designaciones.md) y [planificador-de-horarios.md](planificador-de-horarios.md)).
  - Las tarifas de teoría y de prácticas deben ser mayores a cero (**Tarifa por Hora — Teoría (Bs)** y **Tarifa por Hora — Prácticas (Bs)**).
  - El período académico activo debe tener el formato `I/AAAA` o `II/AAAA`. El período `I` va del 1 de enero al 30 de junio y el `II` del 1 de julio al 31 de diciembre.

**¿De dónde sale la carga que se escribe en el contrato?** De las designaciones y del horario publicado que estén vigentes en el período, sin modificar designaciones históricas. Si una designación terminó antes de la última actualización de designaciones del período (por ejemplo, un grupo que cambió de nombre o pasó a otro docente), se considera reemplazada y no se incluye. Las tarifas por hora se toman de la configuración al momento de emitir y se muestran en el panel de emisión.

## Paso a paso

### 1. Configurar los datos del comitente

Estos datos aparecen en la cláusula PRIMERA de cada contrato.

1. Abrí **Administración → Configuración** y andá a la tarjeta **Datos del Comitente en Contratos**.
2. Completá todos los campos (ninguno puede quedar vacío): **Representante legal**, **CI del representante**, **N.º de testimonio de poder**, **Fecha del poder**, **N.º de Notaría de Fe Pública**, **Notario** y **Ciudad de firma**.
3. Tocá **Guardar datos del comitente**. Verás: «Datos del comitente guardados. Los contratos que emitas desde ahora los usarán.»

Los contratos ya emitidos no se modifican. La próxima vez que emitas el contrato de un docente se genera un contrato nuevo completo con los datos actualizados.

### 2. Emitir el contrato de un docente con fechas propias

1. En **Contratos** tocá **Emitir contratos**. Se abre el panel lateral **Emitir contratos**.
2. En **Configuración de Emisión** elegí el **Departamento** (por defecto Pando). Es el departamento del CI del docente que se escribe en el contrato.
3. En **Contrato Individual con Fechas** elegí al **Docente**.
4. Completá, si hace falta, **Fecha de inicio**, **Fecha de fin** y **Fecha de firma**. Cada campo muestra debajo lo que ocurre si lo dejás vacío:
   - inicio y fin vacíos: se usan las fechas de las designaciones del docente;
   - firma vacía: se usa la fecha de inicio del contrato.
5. Tocá **Emitir contrato**. Cuando termina aparece «<docente>: contrato original listo.» (o «versión N listo.») con el botón **PDF** para descargarlo.

Para volver a las fechas de las designaciones, tocá **Usar fechas de designaciones**: vacía los campos y emite de nuevo. Las fechas que elegiste siguen vigentes para ese docente hasta que las restablezcas. Si las fechas o la fecha de firma cambian respecto del último contrato, se agrega un contrato nuevo completo al historial y el anterior queda sin cambios.

### 3. Emitir contratos por lote

1. En el panel **Emitir contratos**, elegí el **Departamento**.
2. En **Selección de Docentes** elegí una opción:
   - **Todos los docentes**: se emite para todos los docentes con CI real.
   - **Seleccionar docentes**: buscá por nombre o CI en **Buscar docentes** y tildá a quienes correspondan. Aparece el contador de docentes seleccionados.
3. Tocá **Emitir o Recuperar Contratos**.
4. Al terminar verás «N contratos emitidos o recuperados» con la lista de docentes y un botón **PDF** por cada uno. Para bajarlos juntos tocá **Descargar Todos (.zip)**.
5. Si algún docente no pudo procesarse, aparece el aviso **Algunos docentes se omitieron:** con el motivo de cada uno. Los demás contratos se emiten igual.

Las fechas de contrato no se eligen en el lote. Si cerrás el panel, el resultado de la última emisión queda en la página con el botón de cierre **Cerrar resultados de emisión**, así podés descargar los archivos más tarde.

### 4. Versiones: cuándo se crea un contrato nuevo y cuándo se recupera

Cada vez que emitís (individual o por lote), el sistema compara la carga vigente de hoy con la del último contrato del docente:

| Qué cambió desde el último contrato | Qué hace el sistema |
|---|---|
| Nada | Recupera el contrato existente. No se crea ningún documento nuevo |
| No tiene contrato en el período | Emite el **Original** |
| Cambió algo del contrato: la carga (una materia o grupo se agregó, se quitó, o cambiaron sus horas o su tarifa), el nombre o el CI del docente, las fechas de contrato, la fecha de firma, los datos del comitente o la plantilla | Emite una **versión nueva**: el contrato completo, con todas las materias vigentes |
| El docente ya tenía contrato y se quedó sin carga efectiva | No emite nada: «El docente <nombre> no tiene carga efectiva en <período>.» Su último contrato queda como está |

La versión sube de a uno por docente y período: el Original es la versión 1, la siguiente la **Versión 2**, y así. El archivo se descarga como `Contrato_<CI>_<período>_v<N>.pdf`.

### 5. Consultar el historial inmutable

La parte inferior de la página muestra primero seis indicadores:

- **Documentos emitidos**: originales y versiones posteriores.
- **Originales**: primer contrato de cada docente y período.
- **Versiones posteriores**: contratos completos emitidos después del original.
- **Docentes con contrato**.
- **Horas vigentes**: carga vigente de cada docente según su última versión.
- **Monto estimado**: horas por tarifa de la carga vigente de cada docente.

Debajo, en **Historial Inmutable**, hay una tarjeta por docente con una línea de tiempo de sus versiones. Cada versión muestra el tipo (**Original** o **Versión N**), el período, la fecha efectiva, la fecha de emisión y el botón **Descargar PDF**.

Para filtrar:

1. Escribí en **Buscar en el historial** (por docente o CI).
2. Elegí un período en **Período académico** (o **Todos los períodos**).
3. Elegí el **Tipo de documento**: **Todos**, **Originales** o **Versiones posteriores** (cada opción muestra su cantidad).
4. Para volver a ver todo, tocá **Limpiar filtros**.

Bajo cada versión, la tabla de líneas muestra **Actividad** (**Teoría** o **Práctica**), **Materia** (con su grupo), **Horas** y **Tarifa**. Cada versión es un contrato completo con toda la carga vigente al emitirla.

## Reglas y bloqueos

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| El docente no tiene carga efectiva en el período (tenga o no un contrato previo) | «El docente <nombre> no tiene carga efectiva en <período>.» No se emite nada y el último contrato queda como está. En el lote queda en **Algunos docentes se omitieron:** | Cargá la designación o publicá el horario con su asignación |
| Ninguno de los docentes pudo procesarse (lote) | Error «No se pudo emitir ningún contrato.» seguido de los motivos; si no hay docentes que coincidan, «No se encontraron docentes para emitir contratos» | Resolvé los motivos listados y volvé a emitir |
| Un lote termina sin contratos | «No se emitieron contratos.» con la ayuda «Revisá que los docentes tengan carga efectiva y tarifas completas.» | Revisá cargas y tarifas |
| Alguna tarifa es cero o negativa | «Las tarifas de teoría y práctica deben ser mayores que cero.» | Corregí las tarifas en **Administración → Configuración** |
| Docente con CI provisorio (`TEMP-…`) | No aparece en las listas; si se intenta, «No se puede emitir un contrato para un docente TEMP; vinculalo primero a un CI real.» | Vinculalo a un CI real |
| El período activo no tiene formato válido | «El período académico … no permite determinar fechas. Usá el formato I/AAAA o II/AAAA.» | Corregí el período activo en la configuración |
| Fechas de contrato fuera del período | «Las fechas del contrato deben estar dentro del período <período> (<inicio> al <fin>).» | Elegí fechas dentro del período |
| Fecha de inicio posterior a la de fin | «La fecha de inicio del contrato no puede ser posterior a la fecha de fin.» | Corregí las fechas |
| Dos personas emiten a la vez para el mismo docente | «Otra emisión modificó simultáneamente el historial; reintentá para emitir la nueva versión del contrato.» | Volvé a emitir |
| Quiero corregir o borrar un contrato emitido | No se puede: el historial es inmutable | Corregí la causa (carga, fechas, comitente) y emití de nuevo para generar una versión nueva |
| Datos del comitente incompletos | «El campo "<nombre del campo>" no puede estar vacío.» y no se guarda | Completá todos los campos |
| Guardar el comitente sin cambios | «No hay cambios para guardar.» | Modificá algún dato |

## Preguntas frecuentes

**¿Por qué el botón dice «Emitir o Recuperar Contratos»?**
Porque si la carga de un docente no cambió desde su último contrato, el sistema te devuelve ese mismo documento y no crea uno nuevo. Por eso podés volver a descargar un lote sin ensuciar el historial.

**¿Por qué se generó una versión nueva si yo no cambié nada del docente?**
Se emite una versión nueva si cambió algo de lo que entra en el contrato: la carga (por ejemplo, una nueva publicación del horario o un cambio de designación), el nombre o el CI del docente, las fechas, los datos del comitente o la plantilla. Compará sus materias y horas con las de la versión anterior.

**¿Se puede borrar o reemplazar un contrato ya emitido?**
No. Los documentos son inmutables. Un cambio siempre se hace emitiendo una versión nueva del contrato completo.

**¿Qué período se usa?**
El período académico activo de la configuración. El historial guarda los contratos de todos los períodos y los podés filtrar con **Período académico**.

**¿Los contratos cambian si publico un horario nuevo?**
Sí, la carga vigente puede cambiar. El contrato ya emitido queda igual; al emitir de nuevo se agrega una versión nueva del contrato completo con la carga actual.

## Relacionado

- [Designaciones](designaciones.md)
- [Cambio de docente](cambio-de-docente.md)
- [Planificador de horarios](planificador-de-horarios.md)
- [Cierre mensual](cierre-mensual.md)
- [Gestión estudiantil](gestion-estudiantil.md)
- [Docentes y usuarios](docentes-y-usuarios.md)
- [README del proyecto](../../README.md)
