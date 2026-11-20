import { CircleCheck, CircleX, Hourglass, Info, LogOut, type LucideIcon } from 'lucide-react'

import { DisplayFigure, InfoTip, Meter } from '@/components/student'
import { recordStatus, type StudentRecord } from '@/lib/academicRecordsState'
import { classifyRecord, type RecordOutcome } from '@/lib/studentHistorySummary'

const OUTCOME_ICON: Record<RecordOutcome, LucideIcon> = {
  approved: CircleCheck,
  failed: CircleX,
  pending: Hourglass,
  withdrawn: LogOut,
}

/** One subject of a period: status icon, name and code, grade figure with its 0-100 meter. Failed subjects are highlighted. */
export function SubjectRow({ record }: { record: StudentRecord }) {
  const outcome = classifyRecord(record.status)
  const Icon = OUTCOME_ICON[outcome]
  const grade = (outcome === 'approved' || outcome === 'failed') ? record.grade : null
  const status = recordStatus(record.status).label
  return (
    <li className="sp-hist-row" data-outcome={outcome}>
      <Icon aria-hidden="true" className="sp-hist-row-icon" />
      <div className="sp-hist-row-name">
        <b>{record.subject_name}</b>
        <span className="sp-hist-row-codes">
          <InfoTip content="Código de la materia en tu plan de estudios." label={`Código ${record.subject_code}`}>
            <button type="button" className="sp-hist-code">{record.subject_code}</button>
          </InfoTip>
          {!record.in_curriculum && (
            <InfoTip content="Esta materia no pertenece a la malla de tu plan de estudios actual, pero figura en tu historial." label="Qué significa «Fuera de malla»">
              <button type="button" className="sp-hist-oos"><Info aria-hidden="true" />Fuera de malla</button>
            </InfoTip>
          )}
        </span>
      </div>
      {grade !== null
        ? <Meter value={grade} max={100} label={`Nota de ${record.subject_name}`} valueText={`${grade} de 100`} tone={outcome === 'failed' ? 'bad' : 'ok'} className="sp-hist-meter" />
        : <div aria-hidden="true" className="sp-hist-meter-empty" />}
      <div className="sp-hist-grade">
        {grade !== null ? <DisplayFigure value={grade} size="md" /> : <span className="sp-figure" data-size="md" aria-hidden="true">—</span>}
        <small>{status}</small>
      </div>
    </li>
  )
}
