// Pure layout math of the Horario "Hoy" day timeline: hourly axis, block position and size, lanes for overlapping
// classes, the "now" line and the color of a subject. No React, so it runs under node --test.

/** Vertical scale of the axis: one hour is this many px tall. */
export const PX_PER_HOUR = 112
/** A class never renders shorter than this, so its name and room stay readable. */
export const MIN_BLOCK_PX = 112
/** How many subject colors schedule.css defines (`data-tone='0'` ... `data-tone='N-1'`). */
export const TONE_COUNT = 6

const PX_PER_MINUTE = PX_PER_HOUR / 60
const MIN_BLOCK_MINUTES = MIN_BLOCK_PX / PX_PER_MINUTE

export interface TimelineEntry {
  subject_code: string
  start_time: string
  end_time: string
}

export type BlockStatus = 'done' | 'now' | 'later'

export interface DayBlock<T extends TimelineEntry> {
  entry: T
  /** px from the top of the axis. */
  top: number
  height: number
  /** Column of the block among the classes that overlap it, and how many columns that group has. */
  lane: number
  lanes: number
  /** Index of the subject color, stable per subject. */
  tone: number
  status: BlockStatus
}

export interface DayTick {
  minutes: number
  label: string
  top: number
}

export type NowState = 'before' | 'within' | 'after'

export interface NowPosition {
  state: NowState
  minutes: number
  /** px from the top of the axis, only while the time is inside the range. */
  top: number | null
  label: string
}

export interface DayTimeline<T extends TimelineEntry> {
  startMinutes: number
  endMinutes: number
  height: number
  ticks: DayTick[]
  blocks: DayBlock<T>[]
  now: NowPosition | null
}

function toMinutes(time: string): number {
  const [hours, minutes] = time.split(':')
  return Number(hours) * 60 + Number(minutes)
}

/** 07:05 for 425 minutes. */
export function clockLabel(minutes: number): string {
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}

/** Stable color index of a subject (FNV-1a with a final mix, so codes that differ in one digit still land on different colors). */
export function toneIndex(key: string, count = TONE_COUNT): number {
  let hash = 0x811c9dc5
  for (let index = 0; index < key.length; index += 1) hash = Math.imul(hash ^ key.charCodeAt(index), 0x01000193)
  hash ^= hash >>> 16
  hash = Math.imul(hash, 0x45d9f3b)
  hash ^= hash >>> 16
  return (hash >>> 0) % count
}

/** Where the "now" line goes: inside the axis it has a top, outside it only says whether the day has not started or is over. */
export function nowPosition(minutes: number, startMinutes: number, endMinutes: number): NowPosition {
  const label = clockLabel(minutes)
  if (minutes < startMinutes) return { state: 'before', minutes, top: null, label }
  if (minutes > endMinutes) return { state: 'after', minutes, top: null, label }
  return { state: 'within', minutes, top: (minutes - startMinutes) * PX_PER_MINUTE, label }
}

function statusAt(start: number, end: number, now: number | null): BlockStatus {
  if (now === null) return 'later'
  if (end <= now) return 'done'
  return start <= now ? 'now' : 'later'
}

/**
 * The timeline of one day, or null when no class can be placed. The axis starts at the hour of the earliest class and
 * ends at the hour after the latest one. Classes that overlap split the width into lanes; a class that starts when
 * another ends does not overlap it.
 */
export function buildDayTimeline<T extends TimelineEntry>(entries: T[], nowMinutes: number | null): DayTimeline<T> | null {
  const placed = entries
    .map((entry) => ({ entry, start: toMinutes(entry.start_time), end: toMinutes(entry.end_time) }))
    .filter(({ start, end }) => Number.isFinite(start) && Number.isFinite(end))
    .sort((a, b) => a.start - b.start || a.end - b.end)
  if (placed.length === 0) return null

  const startMinutes = Math.floor(Math.min(...placed.map(({ start }) => start)) / 60) * 60
  const endMinutes = Math.max(Math.ceil(Math.max(...placed.map(({ end }) => end)) / 60) * 60, startMinutes + 60)

  // Lanes: greedy, a class takes the first lane that is free at its start; a cluster closes when nothing overlaps it.
  const laneOf: number[] = []
  const lanesOf: number[] = []
  let laneEnds: number[] = []
  let cluster: number[] = []
  const closeCluster = () => {
    for (const index of cluster) lanesOf[index] = laneEnds.length
    laneEnds = []
    cluster = []
  }
  placed.forEach(({ start, end }, index) => {
    // The minimum height counts as occupied time, so two short classes never draw on top of each other.
    const occupiedEnd = Math.max(end, start + MIN_BLOCK_MINUTES)
    if (laneEnds.length > 0 && start >= Math.max(...laneEnds)) closeCluster()
    let lane = laneEnds.findIndex((laneEnd) => laneEnd <= start)
    if (lane === -1) lane = laneEnds.length
    laneEnds[lane] = occupiedEnd
    laneOf[index] = lane
    cluster.push(index)
  })
  closeCluster()

  const blocks = placed.map(({ entry, start, end }, index): DayBlock<T> => ({
    entry,
    top: (start - startMinutes) * PX_PER_MINUTE,
    height: Math.max((end - start) * PX_PER_MINUTE, MIN_BLOCK_PX),
    lane: laneOf[index],
    lanes: lanesOf[index],
    tone: toneIndex(entry.subject_code),
    status: statusAt(start, end, nowMinutes),
  }))

  const ticks: DayTick[] = []
  for (let minutes = startMinutes; minutes <= endMinutes; minutes += 60) {
    ticks.push({ minutes, label: clockLabel(minutes), top: (minutes - startMinutes) * PX_PER_MINUTE })
  }

  return {
    startMinutes,
    endMinutes,
    height: (endMinutes - startMinutes) * PX_PER_MINUTE,
    ticks,
    blocks,
    now: nowMinutes === null ? null : nowPosition(nowMinutes, startMinutes, endMinutes),
  }
}
