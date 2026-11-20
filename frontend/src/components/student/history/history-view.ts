// Pure view rules of the Historial: the counts of the summary legend and the tone of each period.

import type { StudentDetail } from '../../../lib/academicRecordsState.ts'
import { classifyRecord, summarizeHistory } from '../../../lib/studentHistorySummary.ts'

type History = StudentDetail['history']
type PeriodRecords = History[number]['records']

export interface HistoryCounts {
  approved: number
  total: number
  /** Distinct subjects failed that were never approved afterwards. */
  toRetake: number
  /** Records still being taken. */
  inProgress: number
}

export function historyCounts(history: History): HistoryCounts {
  const { approved, total } = summarizeHistory(history)
  const records = history.flatMap(({ records: termRecords }) => termRecords)
  const approvedCodes = new Set(records.filter((record) => classifyRecord(record.status) === 'approved').map((record) => record.subject_code))
  const toRetake = new Set(records.filter((record) => classifyRecord(record.status) === 'failed' && !approvedCodes.has(record.subject_code)).map((record) => record.subject_code))
  return { approved, total, toRetake: toRetake.size, inProgress: records.filter((record) => classifyRecord(record.status) === 'pending').length }
}

/** Decimals worth showing for an average: 75 -> 0, 62.5 -> 1, 51.67 -> 2. */
export function averageDecimals(average: number | null): number {
  if (average === null) return 0
  if (Number.isInteger(average)) return 0
  return Number.isInteger(average * 10) ? 1 : 2
}

/** Timeline tone of a period: a failed subject wins, then one still in progress, otherwise fine. */
export function periodTone(records: PeriodRecords): 'default' | 'ok' | 'warn' | 'bad' {
  if (records.length === 0) return 'default'
  const outcomes = records.map((record) => classifyRecord(record.status))
  if (outcomes.includes('failed')) return 'bad'
  if (outcomes.includes('pending')) return 'warn'
  return 'ok'
}
