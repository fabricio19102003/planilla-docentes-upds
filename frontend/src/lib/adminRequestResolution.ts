import type { DetailRequestInfo, ScheduleResolutionSnapshot } from '@/api/types'

export type AdminRequestEvidence<TLive> =
  | { kind: 'historical'; snapshot: NonNullable<DetailRequestInfo['resolution_snapshot']> }
  | { kind: 'legacy-fallback' }
  | { kind: 'live-pending'; live: TLive }

export function selectAdminRequestEvidence<TLive>(
  request: Pick<DetailRequestInfo, 'status' | 'resolution_snapshot'>,
  live: TLive,
): AdminRequestEvidence<TLive> {
  if (request.status === 'pending') return { kind: 'live-pending', live }
  if (request.resolution_snapshot) {
    return { kind: 'historical', snapshot: request.resolution_snapshot }
  }
  return { kind: 'legacy-fallback' }
}

type ResolutionDesignation = ScheduleResolutionSnapshot['designations'][number]
type ResolutionSlot = ResolutionDesignation['schedule'][number]

export function resolutionDesignationKey(designation: ResolutionDesignation, occurrence = 0): string {
  if (designation.source_key?.trim()) return designation.source_key
  const sourceIdentity = designation.source_kind && designation.source_id != null
    ? `${designation.source_kind}:${designation.source_id}`
    : 'legacy-unknown'
  return [
    sourceIdentity,
    designation.subject,
    designation.group_code,
    designation.semester,
    designation.activity_kind ?? 'unknown',
  ].join('|') + `|${occurrence}`
}

export function resolutionSlotKey(parentKey: string, slot: ResolutionSlot, occurrence = 0): string {
  return [parentKey, slot.dia, slot.hora_inicio, slot.hora_fin, slot.horas_academicas, occurrence].join('|')
}
