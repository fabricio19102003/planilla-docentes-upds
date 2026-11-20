import { CircleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

import { DisplayFigure, InfoTip, ProgressRing } from '@/components/student'
import { Skeleton } from '@/components/ui/skeleton'
import { formatBs, type Eligibility } from '@/lib/reenrollmentState'
import type { HistorySummary } from '@/lib/studentHistorySummary'
import { STAT_TIPS } from './home-state'

interface StatsStripProps {
  history: { summary: HistorySummary | null; isError: boolean }
  eligibility: { data: Eligibility | null; isError: boolean }
}

function StatCell({ label, tip, tipLabel, children, sub }: { label: string; tip: string; tipLabel: string; children: ReactNode; sub?: ReactNode }) {
  return (
    <li className="sph-stat">
      <span className="sph-lbl">
        {label}
        <InfoTip content={tip} label={tipLabel} />
      </span>
      {children}
      {sub ? <span className="sph-stat-sub">{sub}</span> : null}
    </li>
  )
}

function Missing({ children }: { children: string }) {
  return <span className="sph-missing"><CircleAlert aria-hidden="true" />{children}</span>
}

function Pending({ failed, children }: { failed: boolean; children: ReactNode }) {
  return failed ? <Missing>Sin dato</Missing> : <>{children}</>
}

/** Promedio, avance, aprobadas and cuota as display figures, each with a tip that explains it. */
export function StatsStrip({ history, eligibility }: StatsStripProps) {
  const { summary } = history
  const scholarship = eligibility.data?.scholarship
  const empty = summary !== null && summary.total === 0
  const loadingHistory = summary === null && !history.isError
  const loadingScholarship = !scholarship && !eligibility.isError

  return (
    <ul aria-label="Resumen académico" className="sph-strip">
      <StatCell
        label="Promedio"
        tip={STAT_TIPS.promedio}
        tipLabel="Qué es el promedio"
        sub={eligibility.data ? (scholarship?.average == null
          ? 'Sin notas finales en tu último período.'
          : `Promedio de tu último período (${eligibility.data.graded_term}): ${scholarship.average}`) : undefined}
      >
        {loadingHistory ? <Skeleton className="sph-skel-fig" /> : summary && summary.average !== null
          ? <DisplayFigure value={summary.average} decimals={1} size="lg" />
          : <Missing>Sin notas</Missing>}
      </StatCell>
      <StatCell label="Avance de carrera" tip={STAT_TIPS.avance} tipLabel="Qué es el avance de carrera" sub={summary && !empty ? 'de las materias de tu historial' : undefined}>
        {loadingHistory ? <Skeleton className="sph-skel-ring" /> : summary && !empty
          ? <ProgressRing value={summary.progress} size={112} label="Avance de carrera" />
          : <Pending failed={history.isError}><Missing>Sin materias</Missing></Pending>}
      </StatCell>
      <StatCell label="Aprobadas" tip={STAT_TIPS.aprobadas} tipLabel="Qué son las materias aprobadas" sub={summary && !empty ? 'materias aprobadas' : undefined}>
        {loadingHistory ? <Skeleton className="sph-skel-fig" /> : summary && !empty
          ? <DisplayFigure value={summary.approved} size="lg" suffix={`de ${summary.total}`} />
          : <Pending failed={history.isError}><Missing>Sin materias</Missing></Pending>}
      </StatCell>
      <StatCell
        label="Cuota mensual"
        tip={STAT_TIPS.cuota}
        tipLabel="Qué es la cuota mensual"
        sub={scholarship ? (
          <>
            {scholarship.label} · total {formatBs(scholarship.total)}
            {!scholarship.never_failed ? <span className="sph-stat-note">Las becas requieren no haber reprobado ninguna materia.</span> : null}
            <span className="sph-stat-note">Montos informativos; el pago se realiza en caja.</span>
          </>
        ) : undefined}
      >
        {scholarship
          ? <DisplayFigure value={scholarship.cuota} decimals={Number.isInteger(scholarship.cuota) ? 0 : 2} size="lg" prefix="Bs" suffix={`× ${scholarship.cuotas}`} />
          : loadingScholarship ? <Skeleton className="sph-skel-fig" /> : <Missing>Sin dato</Missing>}
      </StatCell>
    </ul>
  )
}
