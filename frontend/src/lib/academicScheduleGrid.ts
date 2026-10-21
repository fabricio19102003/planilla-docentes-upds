export const GRID_START_MINUTES = 6 * 60 + 30
export const GRID_END_MINUTES = 23 * 60 + 5
export const GRID_DAYS = [
  ['lunes', 'Lunes'], ['martes', 'Martes'], ['miercoles', 'Miércoles'],
  ['jueves', 'Jueves'], ['viernes', 'Viernes'], ['sabado', 'Sábado'],
] as const

const VIEW_URL = '/admin/academic-management/schedule-view'

export type ScheduleSource = 'current' | 'draft'

export interface ScheduleViewBlock {
  key: string
  semester: number | null
  group_code: string
  subject_code: string | null
  subject_name: string
  activity_type: 'theory' | 'practice' | string
  weekday: string
  start_time: string
  end_time: string
  teacher_ci: string
  teacher_name: string | null
  classroom_code: string | null
  classroom_name: string | null
  source_type: 'legacy' | 'published' | 'draft'
}

export interface ScheduleViewSemester {
  semester: number | null
  groups: string[]
}

export interface ScheduleViewResponse {
  academic_period: string
  source: ScheduleSource
  reference_date: string
  draft_id: number | null
  semesters: ScheduleViewSemester[]
  blocks: ScheduleViewBlock[]
}

export interface ScheduleFilters {
  period: string
  source: ScheduleSource
  draftId?: number | null
  date: string
  semester?: number | null
  group?: string | null
}

export interface DayLayoutItem {
  block: ScheduleViewBlock
  top: number
  height: number
  column: number
  columns: number
}

export function minutesOf(value: string): number {
  const [hours, minutes] = value.split(':').map(Number)
  return hours * 60 + minutes
}

export interface GridRange { start: number; end: number }

const FULL_RANGE: GridRange = { start: GRID_START_MINUTES, end: GRID_END_MINUTES }

/** Smallest half-hour-aligned window inside 06:30–23:05 that contains every block. */
export function visibleRange(blocks: ScheduleViewBlock[]): GridRange {
  if (!blocks.length) return FULL_RANGE
  const first = Math.min(...blocks.map((block) => minutesOf(block.start_time)))
  const last = Math.max(...blocks.map((block) => minutesOf(block.end_time)))
  const start = Math.max(GRID_START_MINUTES, GRID_START_MINUTES + Math.floor((first - GRID_START_MINUTES) / 30) * 30)
  const end = Math.min(GRID_END_MINUTES, GRID_START_MINUTES + Math.ceil((last - GRID_START_MINUTES) / 30) * 30)
  return { start, end: Math.max(end, start + 30) }
}

/** Position one day's blocks; overlapping blocks share the width in side-by-side columns. */
export function layoutDay(blocks: ScheduleViewBlock[], range: GridRange = FULL_RANGE): DayLayoutItem[] {
  const span = range.end - range.start
  const clamp = (value: number) => Math.min(range.end, Math.max(range.start, value))
  const sorted = [...blocks].sort((a, b) => minutesOf(a.start_time) - minutesOf(b.start_time)
    || minutesOf(b.end_time) - minutesOf(a.end_time))
  const result: DayLayoutItem[] = []
  let cluster: DayLayoutItem[] = []
  let columnEnds: number[] = []
  let clusterEnd = -1
  const closeCluster = () => {
    for (const item of cluster) item.columns = columnEnds.length
    cluster = []
    columnEnds = []
  }
  for (const block of sorted) {
    const start = minutesOf(block.start_time)
    const end = minutesOf(block.end_time)
    if (start >= clusterEnd) closeCluster()
    let column = columnEnds.findIndex((columnEnd) => columnEnd <= start)
    if (column === -1) {
      column = columnEnds.length
      columnEnds.push(end)
    } else {
      columnEnds[column] = end
    }
    const top = ((clamp(start) - range.start) / span) * 100
    const height = ((clamp(end) - clamp(start)) / span) * 100
    const item = { block, top, height, column, columns: 1 }
    cluster.push(item)
    result.push(item)
    clusterEnd = Math.max(clusterEnd, end)
  }
  closeCluster()
  return result
}

const PALETTE = [
  { background: '#dbeafe', border: '#2563eb', text: '#1e3a8a' },
  { background: '#dcfce7', border: '#16a34a', text: '#14532d' },
  { background: '#fef3c7', border: '#d97706', text: '#78350f' },
  { background: '#fce7f3', border: '#db2777', text: '#831843' },
  { background: '#e0e7ff', border: '#4f46e5', text: '#312e81' },
  { background: '#ccfbf1', border: '#0d9488', text: '#134e4a' },
  { background: '#ffedd5', border: '#ea580c', text: '#7c2d12' },
  { background: '#ede9fe', border: '#7c3aed', text: '#4c1d95' },
  { background: '#fee2e2', border: '#dc2626', text: '#7f1d1d' },
  { background: '#ecfccb', border: '#65a30d', text: '#365314' },
  { background: '#cffafe', border: '#0891b2', text: '#164e63' },
  { background: '#f5f5f4', border: '#57534e', text: '#292524' },
]

/** Stable colour per subject name (FNV-1a hash over the palette). */
export function subjectColor(subject: string) {
  let hash = 0x811c9dc5
  for (const char of subject) {
    hash ^= char.codePointAt(0) ?? 0
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return PALETTE[hash % PALETTE.length]
}

function filterParams(filters: ScheduleFilters) {
  const params: Record<string, string | number> = {
    academic_period: filters.period,
    source: filters.source,
  }
  if (filters.source === 'draft' && filters.draftId) params.draft_id = filters.draftId
  params.date = filters.date
  if (filters.semester) params.semester = filters.semester
  if (filters.group) params.group = filters.group
  return params
}

export function scheduleViewRequest(filters: ScheduleFilters) {
  return {
    queryKey: ['academic-management', 'schedule-view', filters.period, filters.source,
      filters.source === 'draft' ? (filters.draftId ?? null) : null, filters.date,
      filters.semester ?? null, filters.group || null] as const,
    url: VIEW_URL,
    params: filterParams(filters),
    enabled: Boolean(filters.period && filters.date && (filters.source === 'current' || filters.draftId)),
  }
}

export function scheduleExportRequest(filters: ScheduleFilters) {
  return { url: `${VIEW_URL}/export`, params: filterParams(filters) }
}

export function exportFilename(contentDisposition: string | undefined | null): string {
  const match = /filename="?([^";]+)"?/i.exec(contentDisposition ?? '')
  return match?.[1] ?? 'horarios.xlsx'
}

const SHIFT_ORDER: Record<string, number> = { M: 0, T: 1, N: 2 }

/** Morning, afternoon and night groups by number (M-2 before M-10), then other codes alphabetically. */
export function compareGroupCodes(a: string, b: string): number {
  const parse = (code: string) => {
    const match = /^([A-Z]+)-(\d+)$/.exec(code)
    const shift = match ? SHIFT_ORDER[match[1]] : undefined
    return shift === undefined ? [3, 0, code] as const : [shift, Number(match![2]), code] as const
  }
  const [shiftA, numberA, codeA] = parse(a)
  const [shiftB, numberB, codeB] = parse(b)
  return shiftA - shiftB || numberA - numberB || codeA.localeCompare(codeB)
}

export interface GroupSchedule {
  semester: number | null
  group: string
  blocks: ScheduleViewBlock[]
}

export function groupBlocksBySchedule(blocks: ScheduleViewBlock[]): GroupSchedule[] {
  const map = new Map<string, GroupSchedule>()
  for (const block of blocks) {
    const key = `${block.semester ?? 'none'}|${block.group_code}`
    const entry = map.get(key) ?? { semester: block.semester, group: block.group_code, blocks: [] }
    entry.blocks.push(block)
    map.set(key, entry)
  }
  return [...map.values()].sort((a, b) => (a.semester === null ? 1 : 0) - (b.semester === null ? 1 : 0)
    || (a.semester ?? 0) - (b.semester ?? 0) || compareGroupCodes(a.group, b.group))
}

export const activityLabel = (activity: string) => (activity === 'practice' ? 'Práctica' : 'Teoría')
