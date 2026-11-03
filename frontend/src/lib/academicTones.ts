import type { Tone } from '../components/shared/tones'

/**
 * Shared color coding for academic views (curriculum board, schedule planner, designations):
 * a stable tone per semester and per shift, so the same semester or shift reads the same everywhere.
 */

const ORDINALS = ['primero', 'segundo', 'tercero', 'cuarto', 'quinto', 'sexto', 'septimo', 'octavo', 'noveno', 'decimo']

// Adjacent semesters never share a tone; the cycle skips neutral and destructive.
const SEMESTER_TONES: readonly Tone[] = ['primary', 'violet', 'cyan', 'success', 'warning', 'info']

export type Shift = 'M' | 'T' | 'N'

const SHIFT_TONES: Record<Shift, Tone> = { M: 'warning', T: 'cyan', N: 'violet' }
const SHIFT_LABELS: Record<Shift, string> = { M: 'Mañana', T: 'Tarde', N: 'Noche' }

/** Semester as a number from `3`, `'3'` or a Spanish ordinal such as `'PRIMERO'` / `'Séptimo'`. */
export function semesterNumber(value: number | string): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const trimmed = value.trim()
  if (/^\d+$/.test(trimmed)) return Number(trimmed)
  const plain = trimmed.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  const index = ORDINALS.indexOf(plain)
  return index === -1 ? null : index + 1
}

export function semesterTone(value: number | string): Tone {
  const n = semesterNumber(value)
  return n === null || n < 1 ? 'neutral' : SEMESTER_TONES[(n - 1) % SEMESTER_TONES.length]
}

/** Shift from a group code prefix: `M-1` → `M`. */
export function shiftFromGroupCode(code: string): Shift | null {
  const first = code.trim().charAt(0).toUpperCase()
  return first === 'M' || first === 'T' || first === 'N' ? first : null
}

export function shiftTone(shift: Shift | null): Tone {
  return shift ? SHIFT_TONES[shift] : 'neutral'
}

export function shiftLabel(shift: Shift): string {
  return SHIFT_LABELS[shift]
}
