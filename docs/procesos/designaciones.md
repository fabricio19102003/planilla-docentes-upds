# Cargar y mantener las designaciones de los docentes

Una **designación** es la materia que se le asigna a un docente en un período académico: con su semestre, grupo, horario semanal, horas que se pagan y fechas de contrato. De las designaciones salen la asistencia esperada, la planilla de pago y los contratos, por eso la pantalla **Designaciones** cuida cada cambio: no deja tocar lo que ya se pagó y solo permite borrar lo que se cargó por error. Esta guía explica cómo crear una designación, editarla, cambiar sus fechas, finalizarla, eliminarla e importar el Excel del semestre.

## Antes de empezar

- **Rol**: solo el administrador puede usar esta pantalla.
- **Dónde está**: menú **Docentes y académico → Designaciones**. También se llega desde el detalle de un docente (botón que abre la pantalla ya filtrada por ese docente).
- **Requisitos**:
  - El docente tiene que existir en **Docentes** (la designación se arma sobre un docente ya cargado).
  - Tené claro el período académico (por ejemplo `II/2026`). Arriba de la lista, el selector **Período** muestra los períodos que tienen designaciones.
- **Qué muestra la pantalla**: cinco indicadores (**Designaciones**, **Vigentes**, **Finalizadas**, **Horas al mes**, **Con contrato**), un buscador (**Buscar docente o materia**), filtros de período, semestre y tipo (**Teoría y práctica / Teoría / Práctica**) y el filtro rápido **Todas / Vigentes / Finalizadas**. Si hay filtros puestos aparece **Limpiar filtros**.
- **Estados**: una designación está **Vigente** hasta que su fecha de fin queda en el pasado; desde entonces figura como **Finalizada**. Si ya tiene contrato, la fila muestra la etiqueta **Contrato emitido**.
- En el celular la lista se ve como tarjetas; las acciones son las mismas y el motivo por el que **Finalizar** está bloqueado se escribe debajo de la tarjeta.
- El botón **¿Cómo funciona esta pantalla?** (arriba a la derecha) resume estas reglas dentro del sistema.

## Paso a paso

### Crear una designación

1. Abrí **Docentes y académico → Designaciones** y elegí en **Período** el período correcto.
2. Hacé clic en **Nueva designación**.
3. En **1. Docente y materia**:
   - Elegí el **Docente** (podés buscar por nombre y paginar los resultados).
   - Escribí la **Materia** (el campo sugiere materias que ya existen en el período).
   - Elegí el **Semestre** y escribí el **Grupo** (por ejemplo `M-1`, `T-2`, `N-1`; el campo sugiere los más comunes).
   - Revisá el **Tipo**: **Teoría** o **Práctica**. Si el nombre de la materia contiene «práctica» el sistema pone **Práctica** solo; si lo cambiás vos a mano, deja de adivinar.
4. En **2. Horario semanal** cargá cada clase como un bloque: **Bloque 1: día**, **Desde** y **Hasta**. Con **Agregar bloque** sumás más días; el ícono de papelera quita un bloque (siempre tiene que quedar al menos uno). Las horas académicas se calculan solas, en bloques de 45 minutos, y abajo ves **Total: N horas académicas por semana**.
5. En **3. Horas a pagar**:
   - **Horas mensuales** es obligatorio: es lo que paga la planilla. Si hay horario cargado aparece **Usar sugerido** (horas semanales × 4); cambialo si la designación oficial dice otra cosa.
   - **Horas del semestre (opcional)**: también ofrece un sugerido (mensuales × 5).
6. En **4. Fechas del contrato** poné **Fecha de inicio** y **Fecha de fin**. Si las dejás vacías, se toma todo el período académico.
7. Hacé clic en **Crear designación**. Arriba aparece el aviso **Designación creada.**; si hay planillas ya generadas de esos meses, el aviso te dice cuáles regenerar (por ejemplo: «Regenerá la planilla de teoría 3/2026 para que tome el cambio.»).

### Editar una designación

1. Buscá la fila y hacé clic en **Editar**.
2. Corregí materia, semestre, grupo, tipo, horario, horas o fechas. El docente se ve pero no se cambia desde acá (ver «Preguntas frecuentes»).
3. Hacé clic en **Guardar cambios**. Si no cambiaste nada, no se guarda nada.
4. Si el aviso indica planillas para regenerar, andá a **Cierre mensual → Planilla** y regenerá esas planillas.

### Cambiar las fechas de una designación

Las fechas se cambian desde **Editar**, en **4. Fechas del contrato**.

1. Hacé clic en **Editar** en la fila.
2. Cambiá **Fecha de inicio** y/o **Fecha de fin**.
3. Hacé clic en **Guardar cambios**.

Si los campos de fecha aparecen deshabilitados, mirá el recuadro gris que está encima: te dice por qué (por ejemplo, que el contrato emitido fijó las fechas). En ese caso las fechas se corrigen emitiendo una versión nueva del contrato desde **Contratos**.

Para **terminar** una designación antes de tiempo no uses este camino: usá **Finalizar** (siguiente sección).

### Finalizar una designación (el docente deja la materia)

1. En la fila, hacé clic en **Finalizar**.
2. En **Último día que dicta la materia** elegí la fecha. Se le paga hasta ese día inclusive. Por defecto propone hoy, dentro de las fechas de la designación.
3. Hacé clic en **Finalizar**. Aparece el aviso **Designación finalizada el DD/MM/AAAA.** y la designación pasa a **Finalizadas**, sin perder el historial.
4. Si el aviso lo indica, regenerá las planillas afectadas. Si la designación tenía contrato, el aviso agrega: «El contrato emitido no cambia; si corresponde, emití una nueva versión del contrato desde Contratos.»

Si el docente se va y entra otro en su lugar, no finalices a mano: usá **Gestión académica → Cambiar docente** (ver [cambio-de-docente.md](cambio-de-docente.md)).

### Eliminar una designación cargada por error

1. En la fila, hacé clic en el ícono de papelera (en el celular, **Eliminar**).
2. Si se puede, el cuadro pregunta **¿Eliminar esta designación?** y aclara que se borra por completo. Confirmá con **Eliminar**.
3. Si no se puede, el cuadro dice **Esta designación no se puede eliminar**, explica el motivo y, si corresponde, ofrece **Finalizar en su lugar**.

### Importar el Excel del semestre

Usalo para cargar muchas designaciones juntas. Es el único lugar para importar el archivo de designaciones (**Subir biométrico** ya no lo tiene y te remite a esta pantalla).

1. En **Designaciones**, hacé clic en **Importar archivo**.
2. Paso **1. Elegí el archivo y el período**: seleccioná el Excel oficial de designaciones (`.xlsx`; también acepta el `.json` auditado) y escribí o elegí el **Período académico** (por ejemplo `II/2026`). La importación usa ese período pero **no lo activa**.
3. Hacé clic en **Generar vista previa**. Todavía no se guarda nada.
4. Paso **2. Revisá qué va a pasar**:
   - Mirá los totales: **designaciones nuevas**, **se actualizan** y **quedan igual**.
   - Abrí cada pestaña (**Nuevas**, **Con cambios**, **Sin cambios**). En **Con cambios** la columna **Qué cambia** dice qué campo se modifica (horario, horas, fechas, tipo…).
   - Si hay docentes nuevos, la vista previa lo avisa: se crean también sus cuentas de acceso.
   - Si aparece **Hay que corregir el archivo antes de importar**, el botón de confirmar queda deshabilitado: corregí el Excel y volvé a generar la vista previa. Los **Avisos (no impiden importar)** solo informan.
5. Hacé clic en **Confirmar e importar**. En el resumen de confirmación (**Importar designaciones**) revisá archivo, período y cantidades y confirmá con **Importar designaciones**.
6. Al terminar ves **¡Designaciones cargadas!** con las cantidades. Si se crearon usuarios docentes, un aviso agrega que deberán pedir el restablecimiento de su contraseña al administrador.

Cosas que conviene saber de la importación:

- Importar el mismo archivo dos veces no duplica nada: la segunda vez todo queda «sin cambios».
- Las designaciones que ya existen y **no** vienen en el archivo no se borran.
- Si editaste una designación a mano y vuelve a venir en el archivo, se reemplaza por lo que diga el archivo.
- Si una fila del Excel no trae fecha de inicio o de fin, se conserva la que ya estaba guardada.
- El horario se escribe como uno o más bloques `DIA: inicio - fin`. Un bloque que no se puede leer se rechaza y la vista previa lo muestra como `Fila N: horario inválido: ...`.
- Los formatos admitidos están detallados en el [README](../../README.md) (sección «Formatos de designación soportados»).

> **No confundir con «Cargar designación»** (**Gestión académica → Cargar designación**). Esa pestaña **no crea ni modifica designaciones**: toma las designaciones de teoría que ya están en el sistema y, con la columna AULA del Excel, arma un **borrador de horario** para el **Planificador de horarios**. Ese borrador no cambia pagos hasta que se publica. Ver [planificador-de-horarios.md](planificador-de-horarios.md).

## Reglas y bloqueos

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| La planilla de un mes cubierto por la designación está **aprobada** | **Editar** muestra «Esta designación ya se pagó y no se puede editar». Al crear o guardar, el servidor responde «No se puede guardar porque ya se pagó con estos datos.» con el detalle, por ejemplo «La planilla de teoría 3/2026 ya está aprobada.» | Finalizá la designación en la fecha del cambio y creá una nueva desde el día siguiente. O rechazá la planilla en **Planilla** si corresponde corregir ese mes. |
| La **facturación** de un mes cubierto está **publicada** | Mismo bloqueo, con el detalle «La facturación de teoría 3/2026 ya está publicada.» | Igual que arriba: finalizá y creá una nueva desde el día siguiente. |
| La designación ya tiene **contrato emitido** y querés cambiar sus fechas | Los campos de fecha quedan deshabilitados: «Las fechas quedaron fijadas en el contrato emitido. Para cambiarlas, emití una nueva versión del contrato desde Contratos.» Si igual se intenta, el servidor responde «No se pueden cambiar las fechas de esta designación.» | Emití una versión nueva del contrato desde **Contratos**. Los demás datos (horario, horas) se siguen pudiendo editar si el mes no está pagado. |
| Ya existe esa materia, semestre y grupo para ese docente en el período | No se guarda: «Ya existe una designación de esa materia, semestre y grupo para este docente en el período.» | Editá la existente en lugar de crear otra, o corregí materia/semestre/grupo. |
| Falta algún dato o hay un dato inválido en el formulario | Aparece **Faltan datos o hay datos para corregir.** con la lista (por ejemplo «Elegí un docente.», «Bloque 1: elegí el día.», «Indicá las horas mensuales.», «Bloque 1: la hora de fin tiene que ser posterior a la de inicio.») | Corregí cada punto de la lista y guardá de nuevo. |
| La fecha de fin es anterior a la de inicio | «La fecha de fin no puede ser anterior a la fecha de inicio.» | Corregí las fechas. |
| Querés cambiar el período de una designación | «El período de una designación no se puede cambiar; finalizala y creá una nueva en el otro período.» | Finalizala y creá una nueva en el período correcto. |
| **Finalizar** en una designación que ya terminó | El botón está deshabilitado con el motivo «La designación ya está finalizada.» | No hace falta hacer nada. |
| Finalizar con fecha anterior al inicio | «La designación empieza el AAAA-MM-DD; el fin no puede ser anterior.» | Elegí una fecha desde el inicio de la designación. |
| Finalizar con fecha posterior al fin actual | «La designación ya termina el AAAA-MM-DD; solo podés adelantar el fin.» | Elegí una fecha igual o anterior al fin actual. |
| El docente tiene asistencia registrada después de la fecha de fin elegida | «El docente tiene asistencia registrada después de esa fecha (…). Elegí una fecha posterior.» | Elegí una fecha posterior a la última asistencia. |
| Hay un mes ya aprobado o publicado después de la nueva fecha de fin | «No se puede finalizar en esa fecha.» con el detalle del mes bloqueado | Elegí una fecha que no afecte meses pagados, o rechazá esa planilla primero. |
| **Eliminar** una designación con asistencia | «Tiene asistencia registrada; usá Finalizar.» | Usá **Finalizar en su lugar**. |
| **Eliminar** una designación con contrato emitido | «Ya tiene un contrato emitido; usá Finalizar.» | Finalizá; si hace falta, emití una versión nueva en **Contratos**. |
| **Eliminar** una designación con monto manual en la planilla | «Una planilla tiene un monto manual para esta designación; usá Finalizar.» | Finalizá. |
| **Eliminar** una designación que ya entró en una planilla | «La planilla de teoría 3/2026 ya se generó con esta designación; usá Finalizar.» (o el aviso de planilla aprobada / facturación publicada) | Finalizá. |
| Después de editar, finalizar o crear, hay planillas generadas de esos meses | El aviso verde dice «Regenerá la planilla de … para que tome el cambio.» | Regenerá esas planillas en **Cierre mensual → Planilla**. |
| Importar: el archivo tiene errores | **No se pudo leer o importar el archivo** o **Hay que corregir el archivo antes de importar**, con filas del tipo `Fila N: …`; no se puede confirmar | Corregí el Excel y generá una nueva vista previa. |
| Importar: período mal escrito | «El período debe usar el formato I/AAAA o II/AAAA.» | Escribí el período como `I/2026` o `II/2026`. |
| Importar: el archivo no trae filas | «El archivo no contiene designaciones.» | Revisá que sea el archivo correcto. |

## Preguntas frecuentes

**¿Cómo cambio el docente de una materia?**
No desde **Editar**: el docente no se puede cambiar ahí. Usá **Gestión académica → Cambiar docente**, que termina la designación del saliente el día anterior y crea la del entrante desde la fecha del cambio. Ver [cambio-de-docente.md](cambio-de-docente.md).

**Me equivoqué de horas en una designación de un mes que ya se pagó. ¿Qué hago?**
No se puede editar. Finalizá la designación en la fecha en que cambia el dato y creá una nueva desde el día siguiente con las horas correctas. Si el error es del mes ya pagado, hay que rechazar la planilla de ese mes antes de corregir.

**¿Cuál es la diferencia entre Finalizar y Eliminar?**
**Finalizar** corta el pago desde el día siguiente al último día elegido y deja la designación en el historial. **Eliminar** la borra por completo y solo se permite si se cargó por error y nadie la usó (sin asistencia, contrato, monto manual ni planilla).

**¿Por qué no veo una designación de un período anterior?**
La lista muestra un período por vez. Cambiá el selector **Período** (arriba) o usá **Limpiar filtros**.

**Al importar, ¿se activa el período académico?**
No. La importación guarda las designaciones en el período que elegiste, pero no lo activa.

**Importé y aparecieron usuarios nuevos. ¿Por qué?**
Si el archivo trae docentes que no existían, el sistema crea el docente y su cuenta de acceso. Esos docentes deberán pedir el restablecimiento de su contraseña al administrador.

## Relacionado

- [Cambio de docente](cambio-de-docente.md)
- [Planificador de horarios](planificador-de-horarios.md)
- [Contratos](contratos.md)
- [Cierre mensual](cierre-mensual.md)
- [Docentes y usuarios](docentes-y-usuarios.md)
- [README del proyecto](../../README.md)
