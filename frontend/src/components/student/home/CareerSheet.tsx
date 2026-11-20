import { Check, History, RotateCcw } from 'lucide-react'

import { Eyebrow, InfoTip, Sheet } from '@/components/student'
import { formatShortDateInBolivia } from '@/lib/boliviaDates'
import type { Eligibility, ReenrollmentWindow } from '@/lib/reenrollmentState'
import type { HistorySummary } from '@/lib/studentHistorySummary'
import { careerSemesters } from './home-state'
import { LinkButton } from './LinkButton'

interface CareerSheetProps {
  history: { summary: HistorySummary | null; isError: boolean }
  eligibility: Eligibility | null
  window: ReenrollmentWindow | null | undefined
}

/** Tu carrera: the semester track (done / now / next / pending), subjects to retake and the key dates. */
export function CareerSheet({ history, eligibility, window }: CareerSheetProps) {
  const { summary } = history
  const track = eligibility
    ? careerSemesters({
        primary: eligibility.primary_semester,
        target: eligibility.target_semester,
        retake: eligibility.recursado.map((item) => item.semester),
      })
    : []
  const retake = eligibility?.recursado ?? []
  const target = eligibility?.target_semester

  return (
    <section aria-labelledby="sph-carrera">
      <Sheet depth={2} padding="md" lift className="sph-career">
        <header className="sph-sheet-head">
          <div className="grid gap-3">
            <Eyebrow>Tu carrera</Eyebrow>
            <h2 id="sph-carrera" className="sp-title">{target ? `Rumbo al semestre ${target}` : 'Tu avance de carrera'}</h2>
          </div>
          {summary && summary.total > 0 && <span className="sph-pill sp-pop" data-tone="violet">{summary.approved} de {summary.total} materias</span>}
        </header>
        {track.length > 0 && (
          <ol className="sph-track" aria-label="Avance por semestre">
            {track.map((item) => (
              <li key={item.semester} className="sph-track-item" data-state={item.state} aria-current={item.state === 'current' ? 'step' : undefined}>
                <InfoTip content={item.tip}>
                  <span className="sph-node" tabIndex={0}>
                    {item.state === 'done' ? <Check aria-hidden="true" /> : item.state === 'retake' ? <RotateCcw aria-hidden="true" /> : item.semester}
                  </span>
                </InfoTip>
                <small>{item.label}</small>
              </li>
            ))}
          </ol>
        )}
        {history.isError && <p className="sph-sub">No se pudo cargar tu avance.</p>}
        {summary && summary.total === 0 && <p className="sph-sub">Todavía no tenés materias en tu historial académico.</p>}
        {retake.length > 0 && (
          <div className="sph-foot">
            <p><RotateCcw aria-hidden="true" />{retake.length === 1 ? '1 materia por recursar' : `${retake.length} materias por recursar`}: {retake.map((item) => item.name).join(', ')}</p>
            <LinkButton to="/estudiante/rematricula" variant="link" className="sph-link--warn">Resolver</LinkButton>
          </div>
        )}
        {window?.is_open && (
          <ol className="sph-upnext" aria-label="Fechas clave">
            <li>
              <time dateTime={window.ends_on}>{formatShortDateInBolivia(window.ends_on)}</time>
              <span><b>Cierra la rematrícula {window.term_code}</b>Editá tu solicitud antes de esa fecha</span>
            </li>
          </ol>
        )}
        <LinkButton to="/estudiante/historial" icon={History}>Ver historial</LinkButton>
      </Sheet>
    </section>
  )
}
