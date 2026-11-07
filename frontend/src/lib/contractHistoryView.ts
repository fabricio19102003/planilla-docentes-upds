import type { Tone } from '../components/shared/tones'

/**
 * View model for the contract ledger page: documents grouped by teacher, KPIs, filters and the
 * tone of each line change. Pure, so the page only renders what these helpers return.
 */

export type KindFilter = 'all' | 'original' | 'amendment'

export interface HistoryLine {
  hours: number
  hourly_rate: number
  source_kind?: string
  source_id?: number
  change_kind: string
}

export interface HistoryDocument {
  public_id: string
  teacher_ci: string
  teacher_name: string
  academic_period: string
  document_kind: 'original' | 'amendment'
  amendment_sequence: number
  version: number
  lines: HistoryLine[]
}

export interface TeacherGroup<D extends HistoryDocument = HistoryDocument> {
  teacher_ci: string
  teacher_name: string
  documents: D[]
}

export interface HistoryKpis {
  documents: number
  originals: number
  amendments: number
  teachers: number
  hours: number
  amount: number
}

export interface HistoryFilters {
  search?: string
  period?: string
  kind?: KindFilter
}

const fold = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim()

/** Sortable key of a period such as `I/2026` or `2-2025`; unknown formats sort by their text. */
function periodKey(period: string): number {
  const match = /^\s*(I{1,2}|1|2)\s*[/-]\s*(\d{4})\s*$/i.exec(period)
  if (!match) return 0
  const term = match[1].toUpperCase() === 'II' || match[1] === '2' ? 2 : 1
  return Number(match[2]) * 10 + term
}

function comparePeriods(a: string, b: string): number {
  return periodKey(a) - periodKey(b) || a.localeCompare(b)
}

function compareDocuments(a: HistoryDocument, b: HistoryDocument): number {
  return (
    comparePeriods(a.academic_period, b.academic_period) ||
    a.amendment_sequence - b.amendment_sequence ||
    a.version - b.version
  )
}

/** Teachers ordered by name, each with its documents from the oldest version to the newest. */
export function groupByTeacher<D extends HistoryDocument>(documents: D[]): TeacherGroup<D>[] {
  const byTeacher = new Map<string, TeacherGroup<D>>()
  for (const document of documents) {
    const group = byTeacher.get(document.teacher_ci)
    if (group) group.documents.push(document)
    else byTeacher.set(document.teacher_ci, { teacher_ci: document.teacher_ci, teacher_name: document.teacher_name, documents: [document] })
  }
  const groups = [...byTeacher.values()]
  for (const group of groups) group.documents.sort(compareDocuments)
  return groups.sort((a, b) => fold(a.teacher_name).localeCompare(fold(b.teacher_name)) || a.teacher_ci.localeCompare(b.teacher_ci))
}

/**
 * The load a teacher has today: the original document of their latest period plus the amendment
 * deltas on top (added and changed lines replace by source, removed lines drop out).
 */
export function currentLines(group: TeacherGroup): HistoryLine[] {
  const latest = group.documents.at(-1)
  if (!latest) return []
  const lines = new Map<string, HistoryLine>()
  group.documents
    .filter((document) => document.academic_period === latest.academic_period)
    .forEach((document, documentIndex) => {
      document.lines.forEach((line, lineIndex) => {
        const key = line.source_id == null ? `${documentIndex}:${lineIndex}` : `${line.source_kind ?? ''}:${line.source_id}`
        if (line.change_kind === 'removed') lines.delete(key)
        else lines.set(key, line)
      })
    })
  return [...lines.values()]
}

export function historyKpis(documents: HistoryDocument[]): HistoryKpis {
  const groups = groupByTeacher(documents)
  let hours = 0
  let amount = 0
  for (const group of groups) {
    for (const line of currentLines(group)) {
      hours += Number(line.hours)
      amount += Number(line.hours) * Number(line.hourly_rate)
    }
  }
  const originals = documents.filter((document) => document.document_kind === 'original').length
  return { documents: documents.length, originals, amendments: documents.length - originals, teachers: groups.length, hours, amount }
}

export function filterHistory<D extends HistoryDocument>(documents: D[], filters: HistoryFilters): D[] {
  const search = fold(filters.search ?? '')
  const period = filters.period ?? 'all'
  const kind = filters.kind ?? 'all'
  return documents.filter(
    (document) =>
      (period === 'all' || document.academic_period === period) &&
      (kind === 'all' || document.document_kind === kind) &&
      (!search || fold(document.teacher_name).includes(search) || document.teacher_ci.toLowerCase().includes(search)),
  )
}

export function kindCounts(documents: HistoryDocument[]): Record<KindFilter, number> {
  const originals = documents.filter((document) => document.document_kind === 'original').length
  return { all: documents.length, original: originals, amendment: documents.length - originals }
}

/** Distinct periods, newest first. */
export function historyPeriods(documents: HistoryDocument[]): string[] {
  return [...new Set(documents.map((document) => document.academic_period))].sort((a, b) => comparePeriods(b, a))
}

const CHANGE_KIND: Record<string, { tone: Tone; label: string }> = {
  added: { tone: 'success', label: 'Agregada' },
  removed: { tone: 'destructive', label: 'Quitada' },
  changed: { tone: 'warning', label: 'Modificada' },
  full: { tone: 'neutral', label: 'Completa' },
}

export function changeKindTone(changeKind: string): Tone {
  return CHANGE_KIND[changeKind]?.tone ?? 'neutral'
}

export function changeKindLabel(changeKind: string): string {
  return CHANGE_KIND[changeKind]?.label ?? CHANGE_KIND.full.label
}

/** Every contract version is a complete contract: "Original", then "Versión 2", "Versión 3"… */
export function contractVersionLabel(
  document: Pick<HistoryDocument, 'document_kind' | 'amendment_sequence'>,
): string {
  return document.document_kind === 'original' ? 'Original' : `Versión ${document.amendment_sequence + 1}`
}
