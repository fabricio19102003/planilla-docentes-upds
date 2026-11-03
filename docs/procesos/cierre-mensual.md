# Hacer el cierre mensual: del biométrico a la planilla publicada

El **cierre mensual** es el proceso que se repite cada mes para pagar a los docentes: subís el reporte del reloj biométrico, procesás la asistencia, generás la planilla de pagos (teóricas y prácticas), la aprobás y la publicás para que cada docente vea cuánto tiene que facturar. Esta guía recorre ese camino en el orden en que lo muestra el tablero del sistema (**Biométrico → Asistencia → Planilla → Aprobación → Publicación**), explica qué decide cada opción (fechas de corte, modo de cálculo, días excluidos), cómo avisar a los docentes y cómo responder sus solicitudes.

## Antes de empezar

- **Rol**: solo el administrador puede hacer el cierre. Los docentes ven el resultado en su portal (ver «Qué ve el docente»).
- **Dónde está**: menú **Cierre mensual**, con estos ítems: **Subir biométrico**, **Asistencia teóricas**, **Asistencia prácticas**, **Observaciones**, **Auditoría de asistencia**, **Planilla** y **Reportes**. Las **Solicitudes** de los docentes están en **Docentes y académico → Solicitudes**.
- **Requisitos antes de arrancar**:
  - Las designaciones del período están cargadas y al día (ver [designaciones.md](designaciones.md)). La planilla se arma sobre ellas.
  - Tenés el archivo `.xls` que exporta el reloj biométrico para el mes.
  - Las tarifas por hora están bien en **Administración → Configuración** (**Tarifa por Hora — Teoría (Bs)** y **Tarifa por Hora — Prácticas (Bs)**). Los valores por defecto son 70 Bs para teoría y 50 Bs para prácticas.
- **El tablero te guía**: en el **Dashboard** hay una tarjeta **Cierre mensual** con el período de facturación y los cinco pasos. Cada paso aparece como hecho, actual o pendiente, y al hacer clic te lleva a la pantalla correspondiente (**Biométrico** a **Subir biométrico**, **Asistencia** a **Asistencia teóricas**, y **Planilla**, **Aprobación** y **Publicación** a **Planilla**). Un paso cuenta como hecho si ya hay un paso posterior hecho. El tablero sigue la planilla de **teóricas**; las prácticas se controlan desde la pestaña **Prácticas** de **Planilla**.

| Paso del tablero | Cuándo está «hecho» | Mensaje que ves si falta |
|---|---|---|
| **Biométrico** | Hay un archivo procesado de ese mes | «Sin archivo de {mes año}» |
| **Asistencia** | Hay horarios procesados | «Sin procesar» |
| **Planilla** | Hay una planilla generada y no rechazada | «Sin generar» o «Rechazada · regenerar» |
| **Aprobación** | La planilla está aprobada | «Pendiente de aprobación» o «Esperando planilla» |
| **Publicación** | La facturación está publicada | «Sin publicar» |

## Paso a paso

### 1. Subir el biométrico

1. Abrí **Cierre mensual → Subir biométrico** (el título de la pantalla es **Carga de datos**).
2. En la tarjeta **Reporte Biométrico**, arrastrá o elegí el archivo en **Seleccioná el reporte biométrico** (el archivo Excel exportado del reloj).
3. Elegí el **Mes** y el **Año** al que corresponde el reporte. La lista de meses va de **Marzo** a **Diciembre**.
4. Hacé clic en **Subir Reporte Biométrico**.
5. Si todo sale bien ves «¡Archivo subido exitosamente!» con la cantidad de registros y de docentes, y, si hubo avisos, «N advertencia(s)». El archivo queda en la tabla **Historial de Subidas** (**Archivo**, **Período**, **Fecha de Subida**, **Registros**, **Docentes**, **Estado**) con estado **Procesado**.

Qué hace el sistema por vos al subir:

- **Alias de CI**: si el CI del biométrico no coincide con ningún docente, busca al docente por nombre. Cuando lo encuentra, guarda los registros con el CI real del docente y te avisa: «Se resolvieron N CI(s) biométrico(s) por nombre (CIs no coincidían entre sistemas).»
- **Vínculos por nombre**: si vincula docentes por nombre te avisa «Se vincularon N docente(s) por nombre.»
- **Rango detectado**: del archivo cargado el sistema toma la primera y la última fecha con registros. Ese rango se sugiere después en **Asistencia teóricas** y **Planilla** como fechas de corte.

> **Atención**: el selector acepta `.xls` y `.xlsx`, pero el sistema solo procesa archivos `.xls`. Con otro formato aparece «Error al subir el archivo» con el detalle «El archivo biométrico debe ser .xls».

En esta misma pantalla está la tarjeta **Lista de Docentes** (vista previa y **Confirmar e importar** de perfiles). No forma parte del cierre; está explicada en [docentes-y-usuarios.md](docentes-y-usuarios.md). Las designaciones no se cargan acá: se cargan desde **Designaciones**.

### 2. Procesar la asistencia

1. Abrí **Cierre mensual → Asistencia teóricas** (título **Procesamiento de asistencia**).
2. Elegí el **Mes** y el **Año**.
3. En **Upload biométrico** elegí el archivo subido en el paso 1 (la lista muestra «archivo — mes año»).
4. Revisá el bloque **Período de corte**:
   - Si ya hay biométrico para ese mes verás el aviso azul **Rango biométrico detectado** y **Fecha inicio** / **Fecha fin** vienen completadas con ese rango.
   - Si no hay biométrico verás **Sin datos biométricos** y las fechas se completan con el corte estándar: del 21 del mes anterior al 20 del mes actual (el texto «Estándar: del 21 del mes anterior al 20 del mes actual» está debajo de los campos).
   - Podés cambiar las fechas a mano. Si el rango se pasa de lo que cubre el biométrico aparece **Rango extendido más allá del biométrico**: «Los días sin cobertura generarán ausencias para todos los docentes con biométrico». No lo hagas salvo que sea intencional.
5. Hacé clic en **Procesar Asistencia**. Se abre la confirmación **Procesar asistencia** con el archivo, el período y el rango de corte. Avisa que «Se recalculan los registros de asistencia del rango y reemplazan los ya procesados. La planilla del período usará estos datos.» Confirmá con **Procesar asistencia**.
6. Cuando termina aparece «✓ Asistencia procesada exitosamente», cuatro indicadores (**Asistencias**, **Tardanzas**, **Ausencias**, **Sin Salida**) y la tabla **Registros de Asistencia — {mes año}**.

Cómo decide el sistema el estado de cada clase (cruzando el horario de la designación con el biométrico):

| Estado | Cuándo | ¿Se paga? |
|---|---|---|
| **Asistió** | Entró hasta 5 minutos después del inicio de la clase (o antes) | Sí |
| **Tardanza** | Entró más de 5 minutos tarde | Sí |
| **Sin Salida** | Hay entrada pero no marcó salida | Sí |
| **Ausente** | Ningún registro del biométrico cubre la clase | No: se descuenta |

Si algo falla, el mensaje es «Error al procesar. Verificá que el upload corresponda al mes seleccionado.»

### 3. Revisar la asistencia: observaciones y auditoría

Antes de generar la planilla conviene revisar lo que va a descontar plata.

**Observaciones** (**Cierre mensual → Observaciones**, título **Observaciones de asistencia**): lista de lo que no fue «asistió» del mes elegido. Tiene pestañas **Todas**, **Tardanzas**, **Ausencias** y **Sin Salida**, cada una con su contador, y columnas **Docente**, **Materia**, **Grupo**, **Fecha**, **Horario**, **Estado**, **Minutos de Tardanza** y **Observación**. Es una pantalla de consulta: no se edita desde acá.

**Auditoría de asistencia** (**Cierre mensual → Auditoría de asistencia**): para un docente muestra de dónde salió cada resultado.

1. Buscá al docente por nombre o CI en **Docente** y elegí **Mes** y **Año**.
2. Mirás el resumen (**Asistidos**, **Tardanzas**, **Ausencias**, **Sin salida**, tasa de asistencia), el **Horario Asignado**, el **Detalle de Asistencia — Auditoría** (con **Entrada Real**, **Salida Real**, **Estado**, **Retraso**, **Hrs**, **Biométrico** «✓ Vinculado» / «✗ Sin registro» y una **Explicación** por fila) y los **Registros Biométricos Originales**.
3. **Descargar PDF** baja la auditoría de ese docente.
4. Para varios docentes a la vez usá **Reporte de Auditoría Masivo**: elegí **Todos los docentes** o **Seleccionar docentes** (marcás los que querés) y hacé clic en **Generar Reporte de Auditoría**.

Si un docente reclama una ausencia, la fila con «✗ Sin registro» y su **Explicación** es lo primero que hay que mirar. Si el problema es el biométrico (por ejemplo un CI que no se vinculó), corregí el dato y volvé a procesar la asistencia (paso 2).

### 4. Asistencia de prácticas (docentes asistenciales)

Las prácticas internas **no usan el biométrico**: la asistencia se registra a mano.

1. Abrí **Cierre mensual → Asistencia prácticas** (título **Asistencia Practicas Internas**).
2. Elegí **Mes** y **Anio**, y si querés acotar, **Desde** / **Hasta**, **Docente** y **Fecha Especifica**.
3. Hacé clic en **Generar Asistencia**. El sistema crea un registro por cada clase de práctica del período y te dice «Se crearon N entradas de asistencia para {mes año}.» Es seguro repetirlo: no duplica los registros que ya existen.
4. Revisá y corregí cada clase:
   - Cambiá el **Estado** con el selector de la fila: **ASISTIÓ**, **AUSENTE**, **TARDANZA** o **JUSTIFICADO**.
   - Cargá **Hora Llegada** / **Hora Salida** (en la vista por docente: **Hora Real Inicio** / **Hora Real Fin**). Al cargar la hora de llegada el sistema pone **ASISTIÓ** si llegó hasta 15 minutos tarde y **TARDANZA** si llegó más tarde.
   - Agregá una **Obs** (observación) si hace falta.
   - Con **Fecha Especifica** ves un solo día y aparecen **Todos Asistieron** y **Todos Ausentes** para marcar todo el día de una vez (pide confirmación). Con **Dia anterior** / **Dia siguiente** te movés entre días.
5. **Exportar PDF** y **Exportar Excel** bajan el control de asistencia.

> **Importante**: al generar, todas las clases quedan en **AUSENTE**. Si no las corregís antes de generar la planilla de prácticas, se descuentan todas.

Eliminar un registro (ícono de papelera, confirmación **Eliminar**) lo borra de forma permanente y deja de contar en la planilla de prácticas.

### 5. Generar la planilla de teóricas

1. Abrí **Cierre mensual → Planilla** (título **Planilla de Pagos**). Arriba elegí **Mes** y **Año**. La pestaña **Teóricas** es la que se abre por defecto.
2. En **Período de corte** revisá **Fecha inicio** y **Fecha fin**. Se completan solas, en este orden: las fechas de la planilla ya guardada para ese mes, si no el rango del biométrico, y si tampoco hay, del 21 del mes anterior al 20 del mes. Podés cambiarlas.
3. En **Modo de cálculo** elegí una de las dos opciones. **No hay ninguna elegida por defecto** y no podés generar sin elegir:
   - **Con descuentos por asistencia**: se descuentan las horas de las clases marcadas **Ausente** según el biométrico. Las tardanzas y las clases sin salida no descuentan.
   - **Sin descuentos (pago completo)**: todos los docentes cobran el 100 % de sus horas asignadas, sin mirar el biométrico. El sistema avisa «Atención: En este modo no se aplicarán descuentos por ausencias. Todos los docentes recibirán el monto total correspondiente a sus horas asignadas.» El modo queda guardado en la planilla y se usa también al publicar.
4. Si hay feriados o clases suspendidas, abrí **Días excluidos del cálculo** (botón **Abrir**) y cargá cada exclusión:
   - **Fecha** (obligatoria) y **Alcance**: **Global** (todos los docentes), **Por semestre** (marcás los **Semestres**) o **Por materia** (marcás **Materias y grupos**).
   - **Motivo** (opcional, por ejemplo «Feriado institucional») y **Agregar**.
   - Un día excluido no se cuenta como hora a pagar ni como ausencia, y queda marcado en el Excel. Para quitarlo usá el ícono **Quitar exclusión**.
5. Mirá la **Vista previa** en la tarjeta **Detalle por Docente**: totales (**Docentes**, **Designaciones**, **Total a Pagar**) y el detalle **Por Docente** o **Por Designación** (**Hrs base**, **Ausencias**, **Hrs a pagar**, **Monto (Bs)**). Los docentes sin biométrico llevan la etiqueta **Sin Bio** y cobran completo. Los que tienen retención muestran **Bruto**, **Retención 13%** y **Neto**.
6. Si tenés que corregir el monto de un docente, usá el lápiz **Ajustar monto** de su fila, escribí el importe final y confirmá con **Confirmar ajuste**. Se acumulan en el aviso «N ajuste(s) de monto pendiente(s)» y se aplican recién al generar. **Quitar ajuste** lo descarta.
7. Hacé clic en **Generar Planilla**. Se abre la confirmación **Generar planilla de Teóricas** con período, corte, modo y totales estimados. Confirmá con **Generar**.
8. Al terminar ves «¡Planilla generada exitosamente!» con docentes, horas y total en Bs, y los botones **Descargar Excel** y **Planilla Salarios** (el Excel con formato de la planilla oficial de salarios). Los mismos archivos están por fila en el **Historial de Planillas**; hacer clic en una fila del historial recarga en pantalla sus fechas y su modo.

Mientras falte algo, el botón **Generar Planilla** queda deshabilitado y la pantalla dice por qué: «Completá las fechas de corte», «La fecha de inicio no puede ser posterior a la fecha de fin» o «Elegí el modo de cálculo».

Cómo se calcula el pago (para poder explicárselo a un docente):

- **Horas base** = las horas de su horario que caen en los días reales del período de corte (no «horas por semana × 4»), menos las horas de los días excluidos.
- **Descuento** = las horas de las clases **Ausente** (solo en el modo con descuentos).
- **Bruto** = horas a pagar × tarifa por hora.
- **Retención RC-IVA** = 13 % del bruto, solo para los docentes marcados con retención. **Neto** = bruto − retención.

### 6. Generar la planilla de prácticas

1. En **Planilla**, cambiá a la pestaña **Prácticas** (el mes y el año se mantienen).
2. El formulario es el mismo: **Período de corte**, **Modo de cálculo** y **Días excluidos del cálculo**. Usa la tarifa de prácticas y toma la asistencia de **Asistencia prácticas**, no del biométrico. Solo se descuentan las clases en **AUSENTE**; **TARDANZA** y **JUSTIFICADO** se pagan.
3. Hacé clic en **Generar Planilla** y confirmá **Generar planilla de Prácticas**. Resultado: «¡Planilla de prácticas generada exitosamente!».
4. El detalle muestra **Docentes**, **Total Bruto**, **Retenciones** y **Total Neto**, y las advertencias que haya.

Si falta algún registro de asistencia de prácticas, la generación se detiene y la pantalla muestra: «La cobertura de prácticas está incompleta o contiene datos incoherentes (faltantes=…, duplicados=…, sobrantes=…, inválidos=…). Generá o corregí la asistencia de prácticas antes de generar la planilla». Volvé al paso 4.

### 7. Aprobar o rechazar

La aprobación se hace por separado en cada pestaña (**Teóricas** y **Prácticas**).

1. Bajá a la tarjeta **Estado de la Planilla**. Una planilla recién generada dice «Pendiente de aprobación».
2. Revisá el detalle y el Excel.
3. Hacé clic en **Aprobar** y confirmá: «La planilla quedará aprobada y lista para publicar.» El estado pasa a «Aprobada — lista para publicar».
4. Si encontrás un error, **Rechazar** (confirmación en rojo): «La planilla quedará rechazada y vas a tener que regenerarla.» Corregí lo que haga falta y generá de nuevo.

Una planilla rechazada no se puede publicar. Una aprobada también puede rechazarse (el sistema lo permite desde el servidor), pero la pantalla solo ofrece **Aprobar** y **Rechazar** mientras está pendiente.

### 8. Publicar para los docentes

1. En la tarjeta **Publicación de Facturación** (de la pestaña que corresponda) hacé clic en **Publicar para Docentes**. El botón solo se habilita con la planilla **aprobada**.
2. Confirmá **Publicar planilla de Teóricas** (o **de Prácticas**): «Los docentes verán sus montos a facturar de {mes año}.»
3. Queda «Publicado el {fecha}» y el aviso verde «Los docentes pueden ver sus montos a facturar para {mes año}.» con la cantidad de docentes y el total.

Qué pasa al publicar:

- Se guarda una **copia congelada** de los montos. Los docentes ven esa copia aunque después cambien los datos de base.
- Cada docente incluido recibe una notificación en su portal: «Facturación {mes año} publicada» — «El monto a facturar para {mes año} ya está disponible. Revisá tu portal para ver el detalle.»
- El sistema también intenta avisar por correo o WhatsApp a quienes corresponda según su consentimiento. Es un intento «de mejor esfuerzo»: si falla, la publicación igual queda hecha y podés reenviar desde la tabla (ver «Avisar a los docentes»).

**Despublicar**: el botón **Despublicar** (confirmación en rojo) hace que los docentes dejen de ver sus montos de ese mes. Usalo si descubrís un error después de publicar. Para corregir: despublicá, regenerá la planilla con los cambios, aprobala y publicala de nuevo. Una planilla idéntica a la ya publicada no se puede publicar otra vez (ver «Reglas y bloqueos»).

### 9. Avisar a los docentes (correo y WhatsApp)

Estas opciones aparecen en la tabla **Por Docente**, solo cuando el mes está publicado.

1. Marcá a los docentes con la casilla de cada fila, o **Seleccionar todos**. Aparece «N docente(s) seleccionado(s)».
2. Para **correo**: **Enviar correo**. El resultado se muestra como «Correos procesados exitosamente» con **enviado(s)**, **fallido(s)** y **omitido(s)**. Si falla todo: «No se pudieron enviar los correos» — «Verificá la configuración de email e intentá nuevamente.» Los docentes con consentimiento de WhatsApp activo se omiten del correo: a ellos se les avisa por WhatsApp.
3. Para **WhatsApp oficial** (solo en la pestaña **Teóricas**):
   1. Mirá el aviso **WhatsApp oficial**: si dice «listo para una vista previa» podés seguir; si dice «no está listo para enviar», la confirmación queda bloqueada hasta que se resuelva.
   2. Hacé clic en **Generar vista previa WhatsApp**. Ves cuántos van por **WhatsApp**, cuántos por **Correo alternativo** y cuántos quedan **Bloqueados**, con el teléfono enmascarado.
   3. Si todo está bien, **Confirmar envío**. Si no querés, **Cancelar**.
   4. Después ves «Estado durable de WhatsApp · lote #N» con el estado de cada intento. Se actualiza solo.
4. **Limpiar selección** desmarca a todos.

Mensajes que podés ver al confirmar WhatsApp:

- «La vista previa cambió. Generá una nueva antes de confirmar.»
- «La capacidad actual no alcanza para este grupo. No se creó ningún envío.»
- «WhatsApp no está listo para enviar. No se creó ningún envío.»
- «No se pudo generar una vista previa segura. No se creó ningún envío.»

Quién recibe WhatsApp depende del consentimiento del docente (ver [docentes-y-usuarios.md](docentes-y-usuarios.md)): sin consentimiento va por correo; si dio de baja, queda bloqueado.

### 10. Responder solicitudes de docentes

Durante el cierre los docentes suelen pedir el detalle de su pago o de su asistencia.

1. Abrí **Docentes y académico → Solicitudes** (título **Solicitudes de Docentes**). El subtítulo cuenta las pendientes.
2. Filtrá con **Todas**, **Pendientes**, **Aprobadas** o **Rechazadas**. La tabla muestra **Docente**, **Período**, **Tipo de Solicitud**, **Mensaje**, **Estado** y **Fecha**. Los tipos son **Detalle Biométrico**, **Resumen de Horas** y **Detalle de Horario**.
3. En una solicitud **Pendiente** hacé clic en **Aprobar** o **Rechazar**. Se abre un cuadro con el mensaje del docente y, como apoyo, el contexto actual de su facturación.
4. Escribí **Observaciones para el docente (opcional)** y confirmá. Rechazar pide una confirmación extra («Confirmar rechazo»): «El docente verá la solicitud como rechazada.»
5. Las ya respondidas se ven con **Ver detalle**. Una solicitud respondida no se puede responder de nuevo.

### Qué ve el docente

Para poder orientar a quien consulta (portal del docente):

- **Mi Facturación**: «Pago — {mes año}» con el bruto, la retención, el ajuste administrativo si lo hubo y el **Neto** («Total a cobrar»), separado en **Teóricas** y **Prácticas Internas**. Mientras no publiques el mes ve «Facturación aún no publicada» — «El administrador aún no ha publicado los montos a facturar para este mes. Serás notificado cuando estén disponibles.»
- Si el pago tiene un ajuste del administrador (**Ajustar monto**), el docente ve «Pago ajustado por administración» y la marca **Ajustado** en el detalle.
- **Notificaciones**: la campana con el aviso de publicación.
- **Mis Solicitudes**: botón de nueva solicitud con **Mes**, **Año**, **Tipo de Solicitud** y **Mensaje (opcional)**; ve el estado **En espera**, **Aprobada** o **Rechazada** y las **Observaciones del administrador**.
- **Carta Retención**: solo aparece para docentes con retención RC-IVA. Genera el PDF con **Generar y Descargar PDF** (título profesional, matrícula, mes y año de cobro, período académico). A los docentes que emiten factura el sistema les dice «Vos emitís factura: no necesitás carta de retención.»

### Reportes útiles al cierre

En **Cierre mensual → Reportes** elegís el tipo, los filtros y hacés **Vista Previa** o **Generar PDF** (luego **Descargar PDF**). El **Historial de Reportes** guarda los últimos 50. Los que más se usan al cerrar el mes:

| Reporte | Para qué |
|---|---|
| **Financiero** | Pagos por docente y designación: bruto, retención y neto del mes |
| **Asistencia** | Registros de asistencia detallados, filtrables por docente, semestre y grupo |
| **Incidencias** | Ausencias, tardanzas y docentes sin biométrico del mes |
| **Conciliación** | Diferencias entre la designación y la asistencia real, con severidad |
| **Comparativo** | Evolución mes a mes del año |
| **Plantel Docente** | Lista completa del plantel (sin filtros) |

## Reglas y bloqueos

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| Subís un archivo que no es `.xls` | «Error al subir el archivo»: «El archivo biométrico debe ser .xls» | Exportá el reporte del reloj en formato `.xls` y subilo de nuevo |
| Querés subir el biométrico de enero o febrero | El selector de **Mes** del biométrico solo ofrece de **Marzo** a **Diciembre** | (a confirmar con el equipo técnico si hace falta otro mes) |
| El CI del biométrico no coincide con el del docente | El sistema lo busca por nombre y, si lo encuentra, lo vincula y lo avisa en las advertencias | Revisá las advertencias; si un docente quedó sin vincular, corregí su CI en **Docentes** y volvé a procesar |
| Procesás la asistencia con otro mes del archivo | «Error al procesar. Verificá que el upload corresponda al mes seleccionado.» | Elegí el archivo que corresponde al mes |
| El rango de corte excede la cobertura del biométrico | Aviso «Rango extendido más allá del biométrico»: los días sin datos generan ausencias | Ajustá **Fecha inicio** / **Fecha fin** al rango detectado |
| Volvés a procesar la asistencia del mismo rango | Reemplaza los registros ya procesados | Hacelo antes de generar la planilla; después regenerá la planilla |
| Falta **Fecha inicio** o **Fecha fin**, o inicio > fin | **Generar Planilla** queda deshabilitado | Completá o corregí las fechas |
| El período de corte supera 63 días | El servidor rechaza la generación | Usá un corte de hasta 63 días (el estándar es 21 → 20) |
| No elegiste el modo de cálculo | **Generar Planilla** deshabilitado: «Elegí el modo de cálculo» | Elegí **Con descuentos por asistencia** o **Sin descuentos (pago completo)** |
| Docente sin registros en el biométrico (modo con descuentos) | Se marca **Sin Bio** y cobra el 100 % de sus horas | Verificá si realmente no marcó; si corresponde, cargá su biométrico y reprocesá |
| Una exclusión por semestre o por materia sin selección | La pantalla avisa «Exclusión #N: seleccioná al menos un semestre o cambiá el alcance» (o «…una materia/grupo…») y no genera | Marcá al menos un semestre o materia/grupo |
| Generás de nuevo un mes que ya tiene planilla | Reemplaza la planilla del mes y vuelve a «Pendiente de aprobación» | Aprobala otra vez |
| Generás sobre una planilla **aprobada** | Confirmación en rojo: «La planilla de {mes año} ya está aprobada. Al generar se va a reemplazar y vuelve a quedar pendiente de aprobación.» | Confirmá solo si querés rehacerla |
| Regenerás la planilla de **Teóricas** con ajustes de monto previos | La pantalla no recarga los ajustes anteriores: se generan sin ellos | Volvé a cargar los **Ajustar monto** antes de generar (en **Prácticas** la pantalla sí los recupera) |
| Cambiaste las exclusiones pero no regeneraste | **Publicar para Docentes** se bloquea: «Regenerá la planilla para aplicar los cambios de exclusiones antes de publicar.» | Generá la planilla otra vez |
| Intentás aprobar una planilla que no está «generada» | El servidor responde que solo se aprueba una planilla en estado «generada» | Si estaba rechazada, regenerala |
| Historial antiguo sin copia de cálculo | «Regeneración requerida: el historial legacy no permite aprobar, publicar, exportar ni abrir el detalle.» | Generá la planilla de ese mes de nuevo |
| Publicás sin planilla o sin aprobar | Botón deshabilitado: «Generá y aprobá la planilla antes de publicar.» / «Aprobá la planilla antes de publicar para docentes.» / «La planilla fue rechazada. Regenerá con los ajustes necesarios.» | Completá el paso que falta |
| Publicás otra vez una planilla que no cambió | El servidor rechaza la publicación por conflicto (el cálculo ya fue publicado). La pantalla no muestra un mensaje claro (a confirmar) | Para corregir montos: regenerá con los cambios, aprobá y publicá |
| La planilla de prácticas no tiene todos los registros de asistencia | «La cobertura de prácticas está incompleta o contiene datos incoherentes…» | Volvé a **Asistencia prácticas**, usá **Generar Asistencia** y corregí los estados |
| **Generar Asistencia** de prácticas sin designaciones de práctica | «No se encontraron designaciones de práctica para el período académico activo» | Revisá las designaciones de tipo Práctica en **Designaciones** |
| Mandás avisos con el mes sin publicar | El servidor responde «La facturación no está publicada para este período» (en pantalla las casillas aparecen recién cuando está publicado) | Publicá primero |
| WhatsApp no listo o sin capacidad | La confirmación queda bloqueada y no se crea ningún envío | Esperá a que el aviso **WhatsApp oficial** diga «listo» o usá **Enviar correo** |
| Respondés una solicitud ya respondida | El servidor responde que solo se responden solicitudes «pending» | Consultala con **Ver detalle** |

## Preguntas frecuentes

**¿Puedo generar la planilla sin subir el biométrico?**
No es recomendable. Con **Sin descuentos (pago completo)** el biométrico no se consulta. Con **Con descuentos por asistencia** y sin asistencia procesada, cada docente sin registros figura como **Sin Bio** y cobra completo, así que la planilla no refleja las ausencias reales.

**¿Las tardanzas descuentan?**
No. Se ven en **Observaciones** y en la auditoría, pero solo las clases **Ausente** descuentan horas. La clase con tardanza, o sin marca de salida, se paga completa.

**Publiqué y vi un error. ¿Qué hago?**
Hacé clic en **Despublicar** (los docentes dejan de ver el monto), corregí la causa, regenerá la planilla, aprobala y publicá de nuevo. No hace falta avisar otra vez a quienes ya recibieron la notificación anterior, pero conviene decirles que vuelvan a mirar su portal cuando republiques.

**¿Por qué un docente con retención ve un monto menor que el bruto?**
Porque se le descuenta el 13 % de RC-IVA. En su pantalla ve **Bruto**, **Retención** y **Neto**; el **Neto** es lo que corresponde a su factura o cobro. La planilla de salarios también calcula la retención con fórmulas del Excel.

**¿Dónde veo qué planillas ya generé?**
En el **Historial de Planillas** de la pantalla **Planilla** (período, corte, fecha, docentes, horas, total, estado y descargas **Excel** / **Salarios**). Si un mes figura «No disponible» en descargas es porque es un registro antiguo que hay que regenerar.

**¿Puedo hacer la planilla de un mes con corte distinto al estándar?**
Sí. El 21 → 20 es solo la sugerencia por defecto; el sistema calcula con las fechas que dejes en **Fecha inicio** y **Fecha fin** (hasta 63 días). Si hay biométrico, se sugiere su rango.

## Relacionado

- [designaciones.md](designaciones.md): las designaciones son la base del cálculo; cargalas y corregilas antes del cierre.
- [cambio-de-docente.md](cambio-de-docente.md): cuando un docente reemplaza a otro a mitad de período.
- [planificador-de-horarios.md](planificador-de-horarios.md): origen de los horarios publicados que alimentan prácticas y asistencia.
- [contratos.md](contratos.md): contratos que dependen de las mismas designaciones.
- [gestion-estudiantil.md](gestion-estudiantil.md): módulo de estudiantes (independiente del cierre).
- [docentes-y-usuarios.md](docentes-y-usuarios.md): alias de CI, retención RC-IVA y consentimiento de WhatsApp de cada docente.
- [../../README.md](../../README.md): modelo de negocio, periodo de corte y modo de cálculo en detalle.
