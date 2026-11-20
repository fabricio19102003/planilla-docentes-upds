import { CircleCheck, CircleX, Hourglass, type LucideIcon } from 'lucide-react'

import { DisplayFigure, InfoTip, ProgressRing, Sheet } from '@/components/student'
import type { StudentDetail } from '@/lib/academicRecordsState'
import { summarizeHistory } from '@/lib/studentHistorySummary'
import { averageDecimals, historyCounts } from './history-view'

interface LegendRowProps {
  icon: LucideIcon
  tone: 'ok' | 'bad' | 'warn'
  label: string
  tip: string
  value: number
  of?: number
}

function LegendRow({ icon: Icon, tone, label, tip, value, of }: LegendRowProps) {
  return (
    <li className="sp-hist-legend-row" data-tone={tone}>
      <span aria-hidden="true" className="sp-hist-legend-tile"><Icon /></span>
      <span className="sp-hist-legend-label">
        {label}
        <InfoTip content={tip} label={`Qué significa «${label}»`} />
      </span>
      <b className="sp-hist-legend-value">
        <DisplayFigure value={value} size="md" />
        {of === undefined ? null : <small>de {of}</small>}
      </b>
    </li>
  )
}

/** The editorial summary of the history: a big average, the career ring and the legend of subjects. */
export function HistorySummary({ history }: { history: StudentDetail['history'] }) {
  const { average, progress } = summarizeHistory(history)
  const counts = historyCounts(history)
  return (
    <section aria-label="Resumen de tu avance">
      <Sheet depth={3} padding="none" className="sp-hist-summary">
        <div className="sp-hist-avg">
          <span className="sp-hist-avg-label">
            Promedio general
            <InfoTip content="Promedio de las notas finales de tus materias aprobadas y reprobadas. Las materias retiradas o en curso no cuentan." label="Qué es el promedio general" />
          </span>
          {average === null
            ? <span className="sp-figure sp-hist-avg-empty" data-size="xl">—</span>
            : <DisplayFigure value={average} decimals={averageDecimals(average)} size="xl" />}
          <span className="sp-hist-avg-sub">sobre 100</span>
        </div>
        <div className="sp-hist-ring">
          <ProgressRing value={progress} size={150} stroke={12} label="Avance de tu carrera">
            <span className="sp-hist-ring-text">{progress}%</span>
          </ProgressRing>
          <span className="sp-hist-ring-caption">
            Avance de tu carrera
            <InfoTip content="Materias aprobadas sobre las que figuran en tu historial; el portal no recibe el total de tu malla." label="Cómo se calcula el avance" />
          </span>
        </div>
        <ul className="sp-hist-legend">
          <LegendRow icon={CircleCheck} tone="ok" label="Materias aprobadas" tip="Materias distintas que aprobaste al menos una vez." value={counts.approved} of={counts.total} />
          {counts.toRetake > 0 && (
            <LegendRow icon={CircleX} tone="bad" label="Por recursar" tip="Materias reprobadas que todavía no aprobaste en un período posterior." value={counts.toRetake} />
          )}
          {counts.inProgress > 0 && (
            <LegendRow icon={Hourglass} tone="warn" label="En curso" tip="Materias que estás cursando y todavía no tienen nota final." value={counts.inProgress} />
          )}
        </ul>
      </Sheet>
    </section>
  )
}
