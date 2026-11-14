import { Award, GraduationCap } from 'lucide-react'
import { useReducedMotion } from 'motion/react'
import { useEffect, useState, type CSSProperties } from 'react'

import { TONE_CHIP, type Tone } from '@/components/shared/tones'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress, ProgressIndicator, ProgressLabel, ProgressTrack, ProgressValue } from '@/components/ui/progress'
import { formatGrade, recordStatus, termAverage, type StudentDetail } from '@/lib/academicRecordsState'
import { classifyRecord, summarizeHistory, type RecordOutcome } from '@/lib/studentHistorySummary'

const OUTCOME_TONE: Record<RecordOutcome, Tone> = {
  approved: 'success',
  failed: 'destructive',
  withdrawn: 'neutral',
  pending: 'warning',
}

const metricIcon = 'grid size-9 shrink-0 place-items-center rounded-xl bg-student-accent-soft text-student-accent-text transition-transform duration-300 ease-out group-hover:-rotate-6 motion-reduce:transition-none motion-reduce:group-hover:rotate-0'

/** The width the progress bar shows: it grows from 0 to `target` when it mounts; with reduced motion it starts at the final width. */
function useFill(target: number): number {
  const reduceMotion = useReducedMotion()
  const [grown, setGrown] = useState(false)
  useEffect(() => {
    const frame = requestAnimationFrame(() => setGrown(true))
    return () => cancelAnimationFrame(frame)
  }, [])
  return reduceMotion || grown ? target : 0
}

function HistorySummaryCard({ history }: { history: StudentDetail['history'] }) {
  const { average, approved, total, progress } = summarizeHistory(history)
  const fill = useFill(progress)
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Resumen de tu avance</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div className="group flex items-center gap-3">
            <span aria-hidden="true" className={metricIcon}><Award className="size-5" /></span>
            <div>
              <dt className="text-xs text-muted-foreground">Promedio general</dt>
              <dd className="text-2xl font-semibold tabular-nums text-brand">{average ?? '—'}</dd>
            </div>
          </div>
          <div className="group flex items-center gap-3">
            <span aria-hidden="true" className={metricIcon}><GraduationCap className="size-5" /></span>
            <div>
              <dt className="text-xs text-muted-foreground">Materias aprobadas</dt>
              <dd className="text-2xl font-semibold tabular-nums text-brand">{approved} / {total}</dd>
            </div>
          </div>
        </dl>
        <Progress value={fill}>
          <div className="flex items-center justify-between">
            <ProgressLabel>Avance de tu carrera</ProgressLabel>
            <ProgressValue>{() => `${progress}%`}</ProgressValue>
          </div>
          <ProgressTrack className="h-2.5"><ProgressIndicator className="bg-brand-strong duration-1000 ease-out motion-reduce:transition-none" /></ProgressTrack>
        </Progress>
        <p className="text-xs text-muted-foreground">El avance se calcula sobre las materias que figuran en tu historial.</p>
      </CardContent>
    </Card>
  )
}

/** Student portal history: summary on top, then one timeline entry per period with colored grade chips. */
export function StudentHistoryTimeline({ history }: { history: StudentDetail['history'] }) {
  return (
    <>
      <HistorySummaryCard history={history} />
      <ol className="space-y-6">
        {history.map(({ term, records }, index) => {
          const average = termAverage(records)
          return (
            <li key={term.code} className="relative border-l-2 border-brand-strong/30 pl-6">
              <span aria-hidden="true" style={{ '--i': index } as CSSProperties} className="sp-timeline-dot absolute -left-[7px] top-1.5 size-3 rounded-full bg-brand-strong ring-4 ring-background" />
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <h3 className="text-base font-semibold">{term.name}</h3>
                {term.is_intensive && <Badge variant="info" size="sm">Curso intensivo</Badge>}
                <span className="text-xs text-muted-foreground">
                  {records.length} materia(s){average === null ? '' : ` · promedio del período ${average}`}
                </span>
              </div>
              <ul className="divide-y rounded-xl border bg-card">
                {records.map((record) => {
                  const outcome = classifyRecord(record.status)
                  const graded = outcome === 'approved' || outcome === 'failed'
                  return (
                    <li key={record.legacy_registration_id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                      <div className="min-w-0">
                        <p className="font-medium text-foreground">{record.subject_name}</p>
                        <p className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                          {record.subject_code}
                          {!record.in_curriculum && <Badge variant="warning" size="sm">Fuera de malla</Badge>}
                        </p>
                      </div>
                      <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${TONE_CHIP[OUTCOME_TONE[outcome]]}`}>
                        {recordStatus(record.status).label}
                        {graded && <span className="tabular-nums">· {formatGrade(record.grade)}</span>}
                      </span>
                    </li>
                  )
                })}
              </ul>
            </li>
          )
        })}
      </ol>
    </>
  )
}
