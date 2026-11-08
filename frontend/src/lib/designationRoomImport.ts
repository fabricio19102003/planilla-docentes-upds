import type { DesignationAdminItem } from '@/api/types'
import { apiErrorMessage } from './userCredentials.ts'

export interface DesignationRoom {
  id: number
  code: string
  name: string
}

/** A designation as the admin API returns it, with the classroom of its theory classes. */
export type DesignationRoomItem = DesignationAdminItem & {
  classroom_id?: number | null
  classroom?: DesignationRoom | null
}

export interface RoomPreviewMatch {
  designation_id: number
  teacher_ci: string
  teacher_name: string
  subject: string
  semester: string
  group_code: string
  current_classroom: DesignationRoom | null
  new_classroom: DesignationRoom
  changed: boolean
}

export interface RoomPreviewUnknown {
  row: number
  teacher: string
  subject: string
  group_code: string
  aula: string
  reason: string
}

export interface RoomPreviewUnmatched {
  row: number
  teacher: string
  subject: string
  semester: string
  group_code: string
  aula: string
}

export interface RoomPreviewWithoutRow {
  designation_id: number
  teacher_name: string
  subject: string
  group_code: string
}

export interface DesignationRoomPreview {
  academic_period: string
  matched: RoomPreviewMatch[]
  unknown_rooms: RoomPreviewUnknown[]
  unmatched_rows: RoomPreviewUnmatched[]
  designations_without_row: RoomPreviewWithoutRow[]
  summary: {
    matched: number
    changed: number
    unknown_rooms: number
    unmatched_rows: number
    designations_without_row: number
  }
  preview_digest: string
}

export interface DesignationRoomApplyResult {
  academic_period: string
  summary: DesignationRoomPreview['summary']
  changed_designation_ids: number[]
}

export type RoomSectionKey = 'assign' | 'unknown' | 'unmatched' | 'withoutRow'

export function roomPreviewSections(preview: DesignationRoomPreview) {
  return {
    assign: preview.matched.filter((row) => row.changed),
    unchanged: preview.matched.filter((row) => !row.changed),
    unknown: preview.unknown_rooms,
    unmatched: preview.unmatched_rows,
    withoutRow: preview.designations_without_row,
  }
}

export function roomSectionTabs(preview: DesignationRoomPreview): { key: RoomSectionKey; label: string; count: number }[] {
  const sections = roomPreviewSections(preview)
  return [
    { key: 'assign', label: 'Se asignan', count: sections.assign.length },
    { key: 'unknown', label: 'Aulas no reconocidas', count: sections.unknown.length },
    { key: 'unmatched', label: 'Filas sin designación', count: sections.unmatched.length },
    { key: 'withoutRow', label: 'Designaciones sin fila', count: sections.withoutRow.length },
  ]
}

function changeCount(preview: DesignationRoomPreview) {
  return preview.matched.filter((row) => row.changed).length
}

export function applyRoomsLabel(preview: DesignationRoomPreview) {
  const count = changeCount(preview)
  return `Aplicar ${count} ${count === 1 ? 'cambio' : 'cambios'}`
}

export function canApplyRooms(preview: DesignationRoomPreview) {
  return changeCount(preview) > 0
}

export function roomLabel(room: DesignationRoom | null | undefined) {
  return room?.name ?? 'Sin aula'
}

/** Classrooms an admin can still pick, in catalog order by name. */
export function activeClassrooms<T extends { name: string; active: boolean }>(classrooms: T[]) {
  return classrooms
    .filter((classroom) => classroom.active)
    .sort((a, b) => a.name.localeCompare(b.name, 'es', { numeric: true }))
}

/** A 409 on apply means the file or the designations changed after the preview was generated. */
export function roomImportError(error: unknown, fallback: string) {
  const status = (error as { response?: { status?: number } })?.response?.status
  return { stale: status === 409, message: apiErrorMessage(error, fallback) }
}
