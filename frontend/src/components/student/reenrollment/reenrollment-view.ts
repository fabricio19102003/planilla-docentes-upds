// Pure view helpers of the editorial Rematrícula (turno icons, seats meter, request flow). No React, so they run under node --test.

import { shiftLabel } from '../../../lib/studentPortalState.ts'

export type ShiftIcon = 'sun' | 'sunset' | 'moon'
export type SeatsTone = 'ok' | 'warn' | 'bad'

/** Same cap as studentReceipt / estimateAmounts: only the first three recursado subjects are charged. */
export const RECURSADO_CHARGED_MAX = 3

const SHIFT_ICONS: Record<string, ShiftIcon> = { M: 'sun', T: 'sunset', N: 'moon' }
const SHIFT_TURNOS: Record<string, string> = { M: 'Turno mañana', T: 'Turno tarde', N: 'Turno noche' }
const SEGMENTS_MAX = 40
// A group with this share of its seats (or less) left reads as "casi lleno".
const FEW_SEATS_SHARE = 0.2

export function shiftIconName(shift: string): ShiftIcon {
  return SHIFT_ICONS[shift] ?? 'sun'
}

export function shiftTurnoName(shift: string): string {
  return SHIFT_TURNOS[shift] ?? `Turno ${shift}`
}

interface SeatsSource {
  capacity: number | null
  free: number | null
  is_full: boolean
}

export interface GroupSeats {
  free: number
  capacity: number
  occupied: number
  /** "39 de 40 libres" */
  text: string
  tone: SeatsTone
  full: boolean
  /** Segments of the seats bar: one per seat, at most 40. */
  segments: number
}

/** The seats of a group as the meter shows them; null when the group has no capacity data. */
export function groupSeats(group: SeatsSource): GroupSeats | null {
  if (group.capacity === null || group.free === null) return null
  const { capacity, free } = group
  const full = group.is_full
  const tone: SeatsTone = full ? 'bad' : capacity > 0 && free / capacity <= FEW_SEATS_SHARE ? 'warn' : 'ok'
  return {
    free,
    capacity,
    occupied: Math.max(0, capacity - free),
    text: `${free} de ${capacity} libres`,
    tone,
    full,
    segments: Math.min(Math.max(capacity, 1), SEGMENTS_MAX),
  }
}

export type RequestStatus = 'pendiente' | 'realizada' | 'observada'

export interface RequestFlow {
  steps: { label: string }[]
  /** Index of the current step; steps.length marks all of them as done. */
  current: number
  label: string
  tone: 'warn' | 'ok' | 'bad'
  hint: string
}

const FLOWS: Record<RequestStatus, RequestFlow> = {
  pendiente: {
    steps: [{ label: 'Enviada' }, { label: 'En revisión' }, { label: 'Realizada' }],
    current: 1,
    label: 'Pendiente',
    tone: 'warn',
    hint: 'Pendiente: Registro todavía no completó tu rematrícula.',
  },
  realizada: {
    steps: [{ label: 'Enviada' }, { label: 'En revisión' }, { label: 'Realizada' }],
    current: 3,
    label: 'Realizada',
    tone: 'ok',
    hint: 'Realizada: Registro completó tu rematrícula.',
  },
  observada: {
    steps: [{ label: 'Enviada' }, { label: 'Observada' }, { label: 'Realizada' }],
    current: 1,
    label: 'Observada',
    tone: 'bad',
    hint: 'Observada: Registro encontró algo que resolver antes de completar tu rematrícula.',
  },
}

export function requestFlow(status: RequestStatus): RequestFlow {
  return FLOWS[status]
}

interface GroupLike {
  code: string
  shift: string
}

/** "M-01 · Mañana · 1 recursado": what the sticky bar says about the request being built. */
export function chosenSummary(group: GroupLike | undefined, recursadoCount: number): string {
  const who = group ? `${group.code} · ${shiftLabel(group.shift)}` : 'Sin grupo elegido'
  const recursado = recursadoCount === 0 ? 'sin recursado' : `${recursadoCount} ${recursadoCount === 1 ? 'recursado' : 'recursados'}`
  return `${who} · ${recursado}`
}
