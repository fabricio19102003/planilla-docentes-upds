// Pure rules behind the editorial Inicio of the student portal. No React and no alias imports, so they run under node --test.

export type RequestStatusValue = 'pendiente' | 'realizada' | 'observada'

/** Steps of the glass request stepper, in order. */
export const REQUEST_STEPS = ['Enviada', 'En revisión', 'Realizada'] as const

export interface RequestFlow {
  /** Index of the current step; REQUEST_STEPS.length means every step is done. */
  current: number
  /** Registro observed the request: the review step is shown as an alert instead of progress. */
  alert: boolean
}

/** Stepper position from the real request status (no request yet means the first step is still to do). */
export function requestFlow(status: RequestStatusValue | null | undefined): RequestFlow {
  if (status === 'pendiente') return { current: 1, alert: false }
  if (status === 'observada') return { current: 1, alert: true }
  if (status === 'realizada') return { current: REQUEST_STEPS.length, alert: false }
  return { current: 0, alert: false }
}

interface RequestNoteDetails {
  submittedOn?: string
  handledOn?: string | null
  observationLabel?: string | null
  closesOn?: string | null
}

/** The line under each step of the stepper. */
export function requestStepNotes(status: RequestStatusValue | null | undefined, details: RequestNoteDetails = {}): string[] {
  if (!status) {
    return ['Todavía no la enviaste', 'Registro la revisa cuando la recibe', details.closesOn ? `Abierta hasta el ${details.closesOn}` : 'Se confirma al aprobarla']
  }
  const sent = details.submittedOn ? `Enviada el ${details.submittedOn}` : 'Ya la enviaste'
  if (status === 'observada') {
    return [sent, details.observationLabel ? `Observada: ${details.observationLabel}` : 'Tiene una observación de Registro', 'Corregila para que se pueda aprobar']
  }
  if (status === 'realizada') return [sent, 'Registro ya la revisó', details.handledOn ? `Realizada el ${details.handledOn}` : 'Realizada']
  return [sent, 'Registro la está revisando', 'Se confirma al aprobarla']
}

export type CareerState = 'done' | 'retake' | 'current' | 'next' | 'pending'

export interface CareerSemester {
  semester: number
  state: CareerState
  /** Short label under the node. */
  label: string
  /** Explanation shown by the InfoTip of the node. */
  tip: string
}

/** Length of the plan when the portal does not know it (Medicina has ten semesters). */
export const DEFAULT_SEMESTERS = 10

interface CareerInput {
  /** Semester the student is attending now. */
  primary: number | null
  /** Semester the student is enrolling in. */
  target: number | null
  /** Semesters that still hold subjects to retake. */
  retake: number[]
}

/** One node per semester: done before the current one, then current, next and pending. */
export function careerSemesters({ primary, target, retake }: CareerInput): CareerSemester[] {
  const current = primary ?? (target ? target - 1 : null)
  const total = Math.max(DEFAULT_SEMESTERS, primary ?? 0, target ?? 0)
  return Array.from({ length: total }, (_, index) => {
    const semester = index + 1
    if (current !== null && semester === current) {
      return { semester, state: 'current', label: 'Ahora', tip: `Estás aquí: semestre ${semester}.` }
    }
    if (target !== null && semester === target) {
      return { semester, state: 'next', label: 'Próximo', tip: `Te corresponde cursar el semestre ${semester}.` }
    }
    if (current !== null && semester < current) {
      return retake.includes(semester)
        ? { semester, state: 'retake', label: `Sem ${semester}`, tip: `Semestre ${semester} · tenés materias por recursar.` }
        : { semester, state: 'done', label: `Sem ${semester}`, tip: `Semestre ${semester} · completo.` }
    }
    return { semester, state: 'pending', label: `Sem ${semester}`, tip: `Semestre ${semester} · todavía no cursado.` }
  })
}

/** A profile value, or null when it is empty so the UI can show a styled "Sin dato" instead of a bare dash. */
export function dataValue(value: string | null | undefined): string | null {
  const trimmed = value?.trim()
  return trimmed ? trimmed : null
}

const toMinutes = (time: string) => {
  const [hours, minutes] = time.split(':')
  return Number(hours) * 60 + Number(minutes)
}

/** The big figure of the "Hoy" sheet: minutes, or whole hours plus the rest. */
export function countdownParts({ state, minutes }: { state: 'in_progress' | 'upcoming'; minutes: number }): { value: number; unit: string; caption: string } {
  const caption = state === 'in_progress' ? 'para que termine' : 'para que empiece'
  if (minutes < 60) return { value: minutes, unit: 'min', caption }
  const rest = minutes % 60
  return { value: Math.floor(minutes / 60), unit: rest === 0 ? 'h' : `h ${rest} min`, caption }
}

/** Elapsed share (0-100) of the class in progress; 0 before it starts or when it has no duration. */
export function classProgress({ entry, state, minutes }: { entry: { start_time: string; end_time: string }; state: 'in_progress' | 'upcoming'; minutes: number }): number {
  if (state !== 'in_progress') return 0
  const duration = toMinutes(entry.end_time) - toMinutes(entry.start_time)
  if (duration <= 0) return 0
  return Math.min(100, Math.max(0, Math.round(((duration - minutes) / duration) * 100)))
}

/** What each figure of the stats strip means, shown by its InfoTip. */
export const STAT_TIPS = {
  promedio: 'Promedio de las notas finales de las materias aprobadas y reprobadas de todo tu historial.',
  avance: 'Porcentaje de las materias de tu historial que ya aprobaste. Se actualiza cuando Registro carga tus notas.',
  aprobadas: 'Materias distintas que aprobaste al menos una vez, sobre el total de materias de tu historial.',
  cuota: 'Cuota mensual con tu beca aplicada, por la cantidad de cuotas del período. Son montos informativos; el pago se realiza en caja.',
} as const

/** "Viernes 20 de noviembre" in Bolivia time, for the eyebrow of the hero. */
export function heroDateLabel(now: Date): string {
  const label = new Intl.DateTimeFormat('es-BO', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'America/La_Paz' }).format(now)
  return label.charAt(0).toUpperCase() + label.slice(1)
}
