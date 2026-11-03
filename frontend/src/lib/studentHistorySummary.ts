/** Pure summary of a student's academic history for the student portal. */

import { termAverage, type RecordStatus, type StudentDetail } from './academicRecordsState.ts'

export type RecordOutcome = 'approved' | 'failed' | 'withdrawn' | 'pending'

export interface HistorySummary {
  /** Average of the final grades of approved and failed records, like the period average. */
  average: number | null
  /** Distinct subjects approved at least once. */
  approved: number
  /** Distinct subjects in the history: the portal does not receive the curriculum total. */
  total: number
  /** Approved over total, rounded to a whole percentage. */
  progress: number
}

const OUTCOMES: Record<RecordStatus, RecordOutcome> = {
  aprobado: 'approved',
  reprobado: 'failed',
  retirado: 'withdrawn',
  pendiente: 'pending',
}

export function classifyRecord(status: RecordStatus): RecordOutcome {
  return OUTCOMES[status]
}

export function summarizeHistory(history: StudentDetail['history']): HistorySummary {
  const records = history.flatMap(({ records: termRecords }) => termRecords)
  const subjects = new Set(records.map((record) => record.subject_code))
  const approved = new Set(records.filter((record) => record.status === 'aprobado').map((record) => record.subject_code))
  return {
    average: termAverage(records),
    approved: approved.size,
    total: subjects.size,
    progress: subjects.size === 0 ? 0 : Math.round((approved.size / subjects.size) * 100),
  }
}
