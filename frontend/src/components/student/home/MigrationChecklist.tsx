import { CalendarX2, CircleCheck, FileX2 } from 'lucide-react'

import { Eyebrow, Sheet } from '@/components/student'
import { pendingLabels, regularizadoBadge, type PendingDocuments } from '@/lib/migrationDocumentsState'

/** Documentos migratorios of a foreign student: a checklist of what is missing or expired, or an all-clear. */
export function MigrationChecklist({ migration }: { migration: PendingDocuments }) {
  const badge = regularizadoBadge(migration)
  if (!migration.applies || !badge) return null
  const labels = pendingLabels(migration)

  return (
    <section aria-labelledby="sph-migracion">
      <Sheet depth={2} padding="md" className="sph-check-sheet" >
        <header className="sph-sheet-head">
          <div className="grid gap-3">
            <Eyebrow>Estado migratorio</Eyebrow>
            <h2 id="sph-migracion" className="sp-title">Documentos migratorios</h2>
          </div>
          <span className="sph-pill sp-pop" data-tone={migration.regularizado ? 'ok' : 'bad'}>
            {migration.regularizado ? <CircleCheck aria-hidden="true" /> : <FileX2 aria-hidden="true" />}{badge.label}
          </span>
        </header>
        {migration.regularizado ? (
          <p className="sph-check-ok"><CircleCheck aria-hidden="true" />Tenés todos tus documentos migratorios al día.</p>
        ) : (
          <>
            <p className="sph-sub">Te faltan documentos o alguno está vencido.</p>
            <ul className="sph-check" aria-label="Documentos pendientes">
              {labels.map((label, index) => {
                const missing = index < migration.missing.length
                return (
                  <li key={label} className="sph-check-item" data-tone={missing ? 'bad' : 'warn'}>
                    <span aria-hidden="true" className="sph-tile">{missing ? <FileX2 /> : <CalendarX2 />}</span>
                    <span className="sph-check-text">{label}</span>
                    <span className="sph-pill" data-tone={missing ? 'bad' : 'warn'}>{missing ? 'Falta' : 'Vencido'}</span>
                  </li>
                )
              })}
            </ul>
            <p className="sph-sub">Presentalos en Registro para poder completar tu rematrícula.</p>
          </>
        )}
      </Sheet>
    </section>
  )
}
