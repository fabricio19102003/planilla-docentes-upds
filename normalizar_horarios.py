"""
normalizar_horarios.py
======================
Parser robusto de horarios docentes para el sistema de planilla UPDS 2026.

Lee el archivo Excel de designaciones, parsea la columna HORARIO (texto libre
con múltiples inconsistencias documentadas), normaliza grupos, calcula horas
académicas y genera un JSON estructurado.

Cobertura objetivo: 100% de las 400 entradas con horario válido.
"""

import re
import json
import math
import openpyxl
from datetime import datetime, date

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------

SOURCE_FILE = "1. DESIGNACIÒN DOCENTE 2026 - OFICIAL 2026-03-23.xlsx"
EXCEL_PATH  = r"D:\Trabajo\UPDS\Planilla Docentes UPDS\\" + SOURCE_FILE
OUTPUT_JSON = r"D:\Trabajo\UPDS\Planilla Docentes UPDS\designaciones_normalizadas.json"

MINUTOS_POR_HORA_ACADEMICA = 45

# Mapeo canónico de variantes de día → nombre normalizado (lowercase)
# Incluye typos conocidos ("juves") y variantes con acento
DAY_ALIASES = {
    "lunes":      "lunes",
    "martes":     "martes",
    "miercoles":  "miercoles",
    "miércoles":  "miercoles",  # con tilde
    "jueves":     "jueves",
    "juves":      "jueves",     # typo documentado
    "viernes":    "viernes",
    "sabado":     "sabado",
    "sábado":     "sabado",     # con tilde
}

# ---------------------------------------------------------------------------
# REGEX PRINCIPAL
# ---------------------------------------------------------------------------
# Diseñado para cubrir TODOS los casos documentados en el análisis:
#   - Días en mayúsculas, minúsculas, con/sin acento, con colon ("Lunes:")
#   - Tiempos HH:MM, HH.MM, HH:MM: (colon extra), truncado (solo MM)
#   - Separadores: " - ", "-", " -", "- ", " A ", " " (faltante)
#   - Sufijos am/pm (ya son 24h, se ignoran)
#
# Grupos nombrados: day, start, end

HORARIO_LINE_RE = re.compile(
    r'(?P<day>'
        r'lunes|martes|mi[eé]rcoles|jue?ves|viernes|s[aá]bado'
    r')'
    r':?'                                   # colon opcional tras el día: "Lunes:"
    r'\s*'                                  # 0+ espacios (incl. doble espacio)
    r'(?P<start>\d{1,2}[:.]\d{2}:?)'       # HH:MM, HH.MM, HH:MM: (colon trailing)
    r'(?:\s*(?:am|pm)\s*)?'                 # am/pm opcional tras inicio
    r'\s*(?:-|[Aa]|(?=\d))\s*'             # separador: -, A, o nada (lookahead a dígito)
    r'(?P<end>\d{1,2}[:.]\d{2}|\d{2})'     # HH:MM, HH.MM, o solo MM (hora truncada)
    r'(?:\s*(?:am|pm))?',                   # am/pm opcional al final
    re.IGNORECASE
)

# Regex solo para detectar si una línea tiene nombre de día (para advertencias)
DAY_ONLY_RE = re.compile(
    r'^(?:lunes|martes|mi[eé]rcoles|jue?ves|viernes|s[aá]bado):?\s*$',
    re.IGNORECASE
)

# ---------------------------------------------------------------------------
# FUNCIONES DE NORMALIZACIÓN
# ---------------------------------------------------------------------------

def normalize_day(raw: str) -> str:
    """Convierte cualquier variante de nombre de día a su forma canónica lowercase."""
    key = raw.lower().rstrip(":").strip()
    return DAY_ALIASES.get(key, key)


def normalize_time(time_str: str, ref_str: str = None) -> str:
    """
    Convierte el string de tiempo a formato HH:MM.

    Casos manejados:
      - "18.15"  → "18:15"  (punto en lugar de colon)
      - "08:00:" → "08:00"  (colon trailing)
      - "40"     → "08:40"  (solo minutos — infiere hora desde ref_str)
    """
    t = time_str.rstrip(":").replace(".", ":")
    if ":" not in t:
        # Solo minutos (ej: "40") — inferir hora desde tiempo de inicio
        if ref_str:
            ref_h = normalize_time(ref_str).split(":")[0]
            t = f"{ref_h}:{t}"
        else:
            # Sin referencia: asumir que son minutos con hora 00
            t = f"00:{t}"
    # Asegurar formato HH:MM con zero-padding
    parts = t.split(":")
    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"


def normalize_group(raw_group: str) -> str:
    """
    Normaliza formato de grupo X-NN → X-N.
    
    Ejemplos:
      M-06 → M-6   (pero M-07 → M-7, M-01 → M-1)
      T-03 → T-3
      N-04 → N-4
      G.E. → G.E.  (invariante)
    
    Regla: strip leading zero del número.
    """
    if not raw_group:
        return raw_group
    s = str(raw_group).strip()
    if s == "G.E.":
        return "G.E."
    # Patrón X-NN donde NN puede tener cero a la izquierda
    m = re.match(r'^([A-Z])-(\d+)$', s)
    if m:
        prefix = m.group(1)
        number = int(m.group(2))  # int() elimina zeros a la izquierda
        return f"{prefix}-{number}"
    return s  # retornar original si no matchea


def calcular_horas_academicas(inicio: str, fin: str) -> tuple[int, int]:
    """
    Calcula duración en minutos y horas académicas (1 HA = 45 min).
    
    Retorna: (duracion_minutos, horas_academicas)
    
    Usa round() por slot individual: 85 min / 45 = 1.89 → round → 2 HA
    
    Razón: los horarios de la UPDS incluyen recesos de 5-10 min entre periodos
    que no se reflejan en el texto. Un bloque de 10:35-12:00 (85 min) son en
    realidad 2 periodos de 45 min con un receso de 5 min embebido.
    
    Verificado con análisis exhaustivo contra 395 designaciones:
      - floor(min/45) → 81 mismatches con Excel
      - round(min/45) → 17 mismatches (la mayoría son errores en el Excel)
    
    Ejemplos:
      06:30-08:00 = 90 min → round(2.00) = 2 HA ✓
      06:30-08:55 = 145 min → round(3.22) = 3 HA ✓
      10:35-12:00 = 85 min → round(1.89) = 2 HA ✓ (antes daba 1 con floor)
      08:10-11:10 = 180 min → round(4.00) = 4 HA ✓
    """
    try:
        h_i, m_i = map(int, inicio.split(":"))
        h_f, m_f = map(int, fin.split(":"))
        total_inicio = h_i * 60 + m_i
        total_fin    = h_f * 60 + m_f
        # Soporte para horarios nocturnos que pasan medianoche (ej: 23:05)
        duracion = total_fin - total_inicio
        if duracion <= 0:
            duracion += 24 * 60  # cruza medianoche
        horas_ac = round(duracion / MINUTOS_POR_HORA_ACADEMICA)  # round per slot
        return duracion, horas_ac
    except (ValueError, AttributeError):
        return 0, 0


# ---------------------------------------------------------------------------
# PARSER DE HORARIO
# ---------------------------------------------------------------------------

def parse_horario(horario_raw: str, fila: int, docente: str) -> tuple[list, list]:
    """
    Parsea una entrada completa de HORARIO.
    
    Retorna:
      - entries: lista de dicts con {dia, hora_inicio, hora_fin, duracion_minutos, horas_academicas}
      - warnings: lista de dicts con advertencias para líneas que no pudieron parsearse
    """
    if not horario_raw or str(horario_raw).strip() in ("", "nan"):
        return [], []

    entries  = []
    warnings = []
    raw_str  = str(horario_raw).strip()

    for line in raw_str.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Intentar parsear con regex principal
        match = HORARIO_LINE_RE.search(line)
        if match:
            day_raw = match.group("day")
            start   = normalize_time(match.group("start"))
            end     = normalize_time(match.group("end"), match.group("start"))
            day     = normalize_day(day_raw)
            dur, ha = calcular_horas_academicas(start, end)
            entries.append({
                "dia":              day,
                "hora_inicio":      start,
                "hora_fin":         end,
                "duracion_minutos": dur,
                "horas_academicas": ha,
            })
        else:
            # No se pudo parsear — registrar advertencia
            if DAY_ONLY_RE.match(line):
                msg = f"Línea de horario sin rango de tiempo: '{line}'"
            else:
                msg = f"Línea no reconocida: '{line}'"
            warnings.append({
                "fila":        fila,
                "docente":     docente,
                "mensaje":     msg,
                "horario_raw": raw_str,
                "linea":       line,
            })

    return entries, warnings


# ---------------------------------------------------------------------------
# LECTURA DEL EXCEL
# ---------------------------------------------------------------------------

def leer_excel(path: str) -> list[dict]:
    """
    Lee el archivo Excel con openpyxl y retorna lista de dicts por fila.
    
    Columnas mapeadas (0-indexed, col A = índice 0):
      [0] = (vacía)
      [1] = DOCENTE
      [2] = MATERIAS
      [3] = SEMESTRE
      [4] = GRUPO
      [5] = SAADS
      [6] = AULA
      [7] = HORARIO
      [8] = CARGA HORARIA (semestral)
      [9] = TOTAL (???)
      [10] = MES
      [11] = SEMANA
      [12] = REAL
    """
    print(f"[INFO] Leyendo: {path}")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            # Fila de encabezado — skip
            continue
        # Filtrar filas completamente vacías (Excel suele añadir filas vacías al final)
        if all(c is None for c in row[:13]):
            continue
        # Extraer valores por posición
        docente           = row[1]
        materia           = row[2]
        semestre          = row[3]
        grupo             = row[4]
        aula              = row[6]
        horario           = row[7]
        carga_semestral   = row[8]
        carga_mensual     = row[10]
        carga_semanal_ex  = row[11]   # valor esperado del Excel (col SEMANA)

        def safe_int(v):
            """Convierte valor de celda openpyxl a int de forma segura."""
            if v is None:
                return None
            try:
                return int(float(str(v)))
            except (ValueError, TypeError):
                return None

        rows.append({
            "fila":             i + 1,   # número de fila Excel (1-based, +1 por header)
            "docente":          str(docente).strip() if docente else None,
            "materia":          str(materia).strip() if materia else None,
            "semestre":         str(semestre).strip() if semestre else None,
            "grupo":            str(grupo).strip() if grupo else None,
            "aula":             aula,
            "horario_raw":      str(horario).strip() if horario else None,
            "carga_semestral":  safe_int(carga_semestral),
            "carga_mensual":    safe_int(carga_mensual),
            "carga_semanal_ex": safe_int(carga_semanal_ex),
        })

    wb.close()
    print(f"[INFO] Filas leídas: {len(rows)} (excluyendo header)")
    return rows


# ---------------------------------------------------------------------------
# PROCESAMIENTO PRINCIPAL
# ---------------------------------------------------------------------------

def procesar() -> dict:
    """
    Orquesta la lectura, parseo y generación del JSON final.
    """
    rows = leer_excel(EXCEL_PATH)

    designaciones = []
    errores       = []
    advertencias  = []
    mismatches    = []

    conteo = {
        "total":          len(rows),
        "parsed_ok":      0,
        "skipped_null":   0,   # filas sin horario (prácticas clínicas, campo vacío)
        "skipped_no_time": 0,  # filas con horario pero sin rango de tiempo válido (ej: "MIERCOLES" solo)
        "parse_errors":   0,
    }

    for row in rows:
        docente  = row["docente"]
        horario  = row["horario_raw"]
        fila     = row["fila"]

        # ── CASO 1: Sin horario (prácticas sin docente asignado) ──────────
        if not horario or horario in ("None", ""):
            conteo["skipped_null"] += 1
            continue

        # ── CASO 2: Parsear horario ───────────────────────────────────────
        entries, warns = parse_horario(horario, fila, docente or "")
        advertencias.extend(warns)

        # Si no se obtuvo ninguna entrada con tiempo válido (ej: "MIERCOLES" solo)
        # → se cuenta como advertencia, NO como error de parseo
        # (el horario existe pero no tiene rango de tiempo válido)
        if not entries:
            # Solo es error real si la línea tiene formato completamente irreconocible
            # (no es un nombre de día conocido sin tiempo)
            if not warns:
                # Ninguna advertencia generada = formato completamente inesperado
                conteo["parse_errors"] += 1
                errores.append({
                    "fila":        fila,
                    "docente":     docente,
                    "materia":     row["materia"],
                    "horario_raw": horario,
                    "razon":       "No se pudo extraer ningún rango horario (formato desconocido)",
                })
            else:
                # Advertencia ya registrada (ej: "MIERCOLES" sin tiempo)
                # — cuenta separado de las filas sin horario
                conteo["skipped_no_time"] += 1
            continue

        conteo["parsed_ok"] += 1

        # ── Normalizar grupo ─────────────────────────────────────────────
        grupo_norm = normalize_group(row["grupo"])

        # ── Calcular horas académicas semanales totales ──────────────────
        total_ha_semanal = sum(e["horas_academicas"] for e in entries)

        # ── Detectar mismatch con valor del Excel ────────────────────────
        esperado = row["carga_semanal_ex"]
        if esperado is not None and esperado != total_ha_semanal:
            mismatches.append({
                "fila":       fila,
                "docente":    docente,
                "materia":    row["materia"],
                "grupo":      grupo_norm,
                "calculado":  total_ha_semanal,
                "excel":      esperado,
                "diferencia": total_ha_semanal - esperado,
                "horario_raw": horario,
            })

        designaciones.append({
            "docente":                           docente,
            "materia":                           row["materia"],
            "semestre":                          row["semestre"],
            "grupo":                             grupo_norm,
            "carga_horaria_semestral":           row["carga_semestral"],
            "carga_horaria_mensual":             row["carga_mensual"],
            "carga_horaria_semanal":             esperado,
            "horario":                           entries,
            "total_horas_academicas_semanal_calculado": total_ha_semanal,
            "horario_raw":                       horario,
        })

    # ── Construir JSON final ─────────────────────────────────────────────
    output = {
        "metadata": {
            "source_file":          SOURCE_FILE,
            "generated_at":         datetime.now().isoformat(),
            "total_designaciones":  conteo["total"],
            "parsed_successfully":  conteo["parsed_ok"],
            "skipped_no_schedule":  conteo["skipped_null"],    # sin horario (prácticas)
            "skipped_no_time":      conteo["skipped_no_time"], # horario sin rango de tiempo
            "parse_errors":         conteo["parse_errors"],
            "mismatches_semana":    len(mismatches),           # discrepancias vs col SEMANA
        },
        "designaciones": designaciones,
        "errores":        errores,
        "advertencias":   advertencias,
        "_mismatches_semana": mismatches,  # reporte interno de diferencias
    }

    return output


# ---------------------------------------------------------------------------
# REPORTE
# ---------------------------------------------------------------------------

def imprimir_reporte(output: dict) -> None:
    """Imprime resumen de resultados en consola (compatible con Windows cp1252)."""
    import sys
    # Forzar UTF-8 en stdout si el entorno lo soporta; si no, usar ASCII safe
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    m  = output["metadata"]
    mm = output["_mismatches_semana"]
    ad = output["advertencias"]
    er = output["errores"]

    OK    = "[OK]"
    WARN  = "[WARN]"
    ERROR = "[ERROR]"
    INFO  = "[INFO]"

    print("\n" + "=" * 60)
    print("  REPORTE PARSER HORARIOS - PLANILLA DOCENTES UPDS 2026")
    print("=" * 60)
    print(f"  Total filas procesadas  : {m['total_designaciones']}")
    print(f"  Parseadas exitosamente  : {m['parsed_successfully']}")
    print(f"  Saltadas (sin horario)  : {m['skipped_no_schedule']}  <- practicas clinicas")
    print(f"  Saltadas (sin tiempo)   : {m['skipped_no_time']}   <- dia sin rango (ej: 'MIERCOLES' solo)")
    print(f"  Errores de parseo       : {m['parse_errors']}")
    print(f"  Mismatches vs SEMANA    : {m['mismatches_semana']}")
    print("-" * 60)

    if ad:
        print(f"\n{WARN} ADVERTENCIAS ({len(ad)}):")
        for a in ad:
            print(f"  Fila {a['fila']:>3} | {a.get('docente', '')}")
            print(f"         -> {a['mensaje']}")
    else:
        print(f"\n{OK} Sin advertencias")

    if er:
        print(f"\n{ERROR} ERRORES DE PARSEO ({len(er)}):")
        for e in er:
            print(f"  Fila {e['fila']:>3} | {e['docente']} | {e['materia']}")
            print(f"         -> {e['razon']}")
            print(f"         Raw: {e['horario_raw']!r}")
    else:
        print(f"\n{OK} Cero errores de parseo")

    if mm:
        print(f"\n{INFO} MISMATCHES horas semanales calculadas vs Excel ({len(mm)}):")
        print(f"  {'Fila':>4}  {'Calculado':>9}  {'Excel':>5}  {'Dif':>4}  Docente / Materia")
        print(f"  {'----':>4}  {'---------':>9}  {'-----':>5}  {'---':>4}  -----------------")
        for x in mm:
            print(f"  {x['fila']:>4}  {x['calculado']:>9}  {x['excel']:>5}  {x['diferencia']:>+4}  "
                  f"{x['docente']} / {x['materia']} [{x['grupo']}]")
        print(f"\n  Total mismatches: {len(mm)}")
    else:
        print(f"\n{OK} Todas las horas calculadas coinciden con columna SEMANA del Excel")

    print("\n" + "=" * 60)
    print(f"  JSON guardado en: {OUTPUT_JSON}")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Procesar
    output = procesar()

    # 2. Guardar JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 3. Imprimir reporte
    imprimir_reporte(output)
