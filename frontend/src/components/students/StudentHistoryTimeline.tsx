import { Badge } from '@/components/ui/badge'
import { DisplayFigure, Timeline, TimelineItem } from '@/components/student'
import { HistorySummary } from '@/components/student/history/HistorySummary'
import { SubjectRow } from '@/components/student/history/SubjectRow'
import { averageDecimals, periodTone } from '@/components/student/history/history-view'
import { termAverage, type StudentDetail } from '@/lib/academicRecordsState'
import '@/styles/student/history.css'

/** Student portal history: the summary sheet on top, then one collapsible timeline item per period with its subjects. */
export function StudentHistoryTimeline({ history }: { history: StudentDetail['history'] }) {
  return (
    <div className="sp-hist">
      <HistorySummary history={history} />
      <Timeline>
        {history.map(({ term, records }, index) => {
          const average = termAverage(records)
          return (
            <TimelineItem
              key={term.code}
              tone={periodTone(records)}
              defaultOpen={index === 0}
              toggleLabel={`${term.name}: ${records.length} materia(s)${average === null ? '' : `, promedio ${average}`}`}
              title={
                <>
                  <b className="sp-hist-period">{term.name}</b>
                  <small className="sp-hist-period-sub">
                    {records.length} materia(s)
                    {term.is_intensive && <Badge variant="info" size="sm">Curso intensivo</Badge>}
                  </small>
                </>
              }
              meta={
                <span className="sp-hist-period-avg">
                  <small>Promedio</small>
                  {average === null ? <b>—</b> : <DisplayFigure value={average} decimals={averageDecimals(average)} size="md" />}
                </span>
              }
            >
              <ul className="sp-hist-subjects">
                {records.map((record) => <SubjectRow key={record.legacy_registration_id} record={record} />)}
              </ul>
            </TimelineItem>
          )
        })}
      </Timeline>
    </div>
  )
}
