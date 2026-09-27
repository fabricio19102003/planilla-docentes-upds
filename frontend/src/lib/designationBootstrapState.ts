import type {
  DesignationBootstrapAliasSelections,
  DesignationBootstrapIssue,
  DesignationBootstrapResolutionContext,
} from '@/api/types'

interface IssueCopy {
  title: string
  action: string
}

const issueCopy: Record<string, IssueCopy> = {
  unresolved_teacher_alias: {
    title: 'Hay nombres de docentes de práctica que no coinciden entre ambos archivos.',
    action: 'Seleccione “Resolver coincidencias” y elija explícitamente cada identidad salarial.',
  },
  unresolved_subject_alias: {
    title: 'Hay materias de práctica que no coinciden entre ambos archivos.',
    action: 'Seleccione “Resolver coincidencias” y vincule cada materia con una opción del mismo semestre.',
  },
  practice_join_missing: {
    title: 'Faltan pagos de práctica que respalden filas del archivo oficial.',
    action: 'Corrija el archivo salarial para incluir las asignaciones faltantes y genere otra vista previa.',
  },
  practice_join_ambiguous: {
    title: 'Una asignación de práctica coincide con más de una identidad salarial.',
    action: 'Corrija las identidades repetidas en el archivo salarial; el sistema no elegirá una automáticamente.',
  },
  practice_join_missing_ci: {
    title: 'Hay docentes de práctica sin CI en el archivo salarial.',
    action: 'Complete el CI en el archivo salarial y vuelva a cargarlo.',
  },
  practice_join_conflicting_ci: {
    title: 'Hay CI contradictorios para una misma asignación de práctica.',
    action: 'Verifique y corrija el CI en el archivo salarial antes de continuar.',
  },
  orphan_salary_assignment: {
    title: 'El archivo salarial contiene asignaciones sin una fila oficial correspondiente.',
    action: 'Quite o corrija esas asignaciones en el archivo salarial y genere otra vista previa.',
  },
  missing_program: {
    title: 'El programa seleccionado no está disponible en el catálogo.',
    action: 'Active o registre el programa en Gestión académica y vuelva a intentar.',
  },
  ambiguous_program: {
    title: 'El catálogo contiene más de un programa con la misma identidad.',
    action: 'Corrija los programas duplicados en Gestión académica antes de importar.',
  },
  missing_subject: {
    title: 'Hay materias del archivo oficial que no existen en el catálogo.',
    action: 'Registre las materias faltantes en Gestión académica y genere otra vista previa.',
  },
  missing_salary_subject: {
    title: 'Hay materias del archivo salarial que no existen en el catálogo.',
    action: 'Registre la materia o corrija su nombre en el archivo salarial.',
  },
  missing_offering: {
    title: 'Faltan ofertas académicas para materias y semestres importados.',
    action: 'Registre las ofertas para II/2026 en Gestión académica y vuelva a intentar.',
  },
  missing_group: {
    title: 'Faltan grupos académicos requeridos por el horario.',
    action: 'Registre los grupos para II/2026 en Gestión académica y vuelva a intentar.',
  },
  missing_classroom: {
    title: 'Faltan aulas utilizadas por el horario.',
    action: 'Registre o active las aulas en Gestión académica y vuelva a intentar.',
  },
  missing_teacher: {
    title: 'Hay docentes que no existen en el registro institucional.',
    action: 'Registre a los docentes o corrija sus identidades en la fuente correspondiente.',
  },
  missing_availability: {
    title: 'La disponibilidad registrada no cubre todos los horarios.',
    action: 'Complete la disponibilidad docente para II/2026 en Gestión académica.',
  },
  duplicate_block: {
    title: 'El archivo produciría bloques de horario duplicados.',
    action: 'Elimine las filas duplicadas del archivo oficial y genere otra vista previa.',
  },
  schedule_overlap: {
    title: 'El horario contiene cruces de docente, grupo o aula.',
    action: 'Corrija los horarios en el archivo oficial; no se aplicarán cruces automáticamente.',
  },
  blank_schedule: {
    title: 'Hay filas sin horario.',
    action: 'Complete el horario en el archivo oficial y vuelva a cargarlo.',
  },
  invalid_schedule: {
    title: 'Hay horarios que no se pueden interpretar de forma segura.',
    action: 'Corrija el texto del horario en el archivo oficial y genere otra vista previa.',
  },
  impossible_interval: {
    title: 'Hay intervalos de horario imposibles.',
    action: 'Corrija las horas de inicio y fin en el archivo oficial.',
  },
}

const warningCopy: Record<string, string> = {
  salary_payment_hours_noncomparable: 'Las horas del archivo salarial representan pagos y se muestran solo como referencia; no se comparan con la duración del horario.',
  normalized_day_name: 'Se normalizaron nombres de días para interpretar el horario.',
  normalized_time_separator: 'Se normalizaron separadores de hora sin cambiar la duración.',
  normalized_meridiem_spacing: 'Se normalizó el formato AM/PM de algunos horarios.',
}

function genericIssueCopy(code: string): IssueCopy {
  if (code.startsWith('alias_') || code.includes('_alias')) {
    return {
      title: 'El archivo de equivalencias no corresponde exactamente a estos archivos o contiene datos inválidos.',
      action: 'Vuelva a resolver las coincidencias en esta pantalla para generar opciones ligadas a las fuentes actuales.',
    }
  }
  if (code.startsWith('ambiguous_')) {
    return {
      title: 'El catálogo contiene coincidencias ambiguas que el sistema no puede elegir de forma segura.',
      action: 'Corrija los registros duplicados en Gestión académica y genere otra vista previa.',
    }
  }
  if (code.includes('workbook') || code.includes('header') || code.includes('column')) {
    return {
      title: 'Uno de los archivos no tiene la estructura oficial esperada.',
      action: 'Use una copia XLSX sin modificar de la plantilla oficial y vuelva a cargarla.',
    }
  }
  return {
    title: 'La importación contiene datos que no pueden aplicarse de forma segura.',
    action: 'Revise los archivos fuente con el responsable de datos y genere una nueva vista previa.',
  }
}

export function designationBootstrapIssueCopy(issue: DesignationBootstrapIssue) {
  return issueCopy[issue.code] ?? genericIssueCopy(issue.code)
}

export function designationBootstrapWarningCopy(issue: DesignationBootstrapIssue) {
  return warningCopy[issue.code] ?? 'Se detectó una normalización informativa. Revise los conteos antes de confirmar.'
}

export function designationAliasSelectionState(
  context: DesignationBootstrapResolutionContext,
  teacherSelections: Record<string, string>,
  subjectSelections: Record<string, string>,
) {
  const missingCandidates = context.teacher_resolutions.some((item) => !item.candidates.length)
    || context.subject_resolutions.some((item) => !item.candidates.length)
  const complete = context.teacher_resolutions.every((item) => teacherSelections[item.official_teacher_key])
    && context.subject_resolutions.every((item) => subjectSelections[`${item.semester}:${item.salary_subject_key}`])
    && !missingCandidates
  const selections: DesignationBootstrapAliasSelections = {
    teacher_selections: context.teacher_resolutions.map((item) => ({
      official_teacher_key: item.official_teacher_key,
      candidate_token: teacherSelections[item.official_teacher_key],
    })),
    subject_selections: context.subject_resolutions.map((item) => ({
      salary_subject_key: item.salary_subject_key,
      semester: item.semester,
      official_subject_key: subjectSelections[`${item.semester}:${item.salary_subject_key}`],
    })),
  }
  return { complete, selections }
}
