import { AlertCircle, CheckCircle2 } from 'lucide-react'

import type { DesignationBootstrapPreview as BootstrapPreview } from '@/api/types'
import { Button } from '@/components/ui/button'
import {
  designationBootstrapIssueCopy,
  designationBootstrapWarningCopy,
} from '@/lib/designationBootstrapState'

const aliasBlockerCodes = new Set(['unresolved_teacher_alias', 'unresolved_subject_alias'])

export function DesignationBootstrapPreview({
  preview,
  resolving,
  onResolve,
}: {
  preview: BootstrapPreview
  resolving: boolean
  onResolve: () => void
}) {
  const readyItems = [
    ['Bloques de teoría', preview.planned.theory_block_count],
    ['Asignaciones de teoría', preview.planned.theory_assignment_count],
    ['Bloques de práctica', preview.planned.practice_block_count],
    ['Asignaciones de práctica', preview.planned.practice_assignment_count],
  ] as const
  const canResolve = preview.blockers.some((blocker) => aliasBlockerCodes.has(blocker.code))

  return (
    <div className="space-y-4" aria-live="polite">
      <section aria-labelledby="bootstrap-ready-title" className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
        <div className="flex items-start gap-2">
          <CheckCircle2 aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-emerald-700" />
          <div className="min-w-0 flex-1">
            <h3 id="bootstrap-ready-title" className="font-semibold text-emerald-950">Registros preparados</h3>
            <dl className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
              {readyItems.map(([label, value]) => (
                <div key={label} className="flex items-center justify-between gap-3 border-b border-emerald-200 pb-1">
                  <dt className="text-emerald-900">{label}</dt>
                  <dd className="font-semibold tabular-nums text-emerald-950">{value}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-xs leading-5 text-emerald-900">
              Se leyeron {preview.theory.parsed_row_count} filas de teoría, {preview.practice.official_parsed_row_count} filas oficiales de práctica y {preview.practice.salary_parsed_row_count} filas salariales de práctica.
            </p>
          </div>
        </div>
      </section>

      <section aria-labelledby="bootstrap-warning-title" className="rounded-lg border border-amber-200 bg-amber-50 p-4">
        <h3 id="bootstrap-warning-title" className="font-semibold text-amber-950">Advertencias</h3>
        {preview.warnings.length ? (
          <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-5 text-amber-950">
            {preview.warnings.map((warning) => (
              <li key={warning.code}>{designationBootstrapWarningCopy(warning)} <strong>({warning.count})</strong></li>
            ))}
          </ul>
        ) : <p className="mt-2 text-sm text-amber-900">No se detectaron advertencias.</p>}
      </section>

      <section aria-labelledby="bootstrap-blocker-title" className={`rounded-lg border p-4 ${preview.blockers.length ? 'border-red-200 bg-red-50' : 'border-slate-200 bg-slate-50'}`}>
        <div className="flex items-start gap-2">
          <AlertCircle aria-hidden="true" className={`mt-0.5 size-5 shrink-0 ${preview.blockers.length ? 'text-red-700' : 'text-slate-500'}`} />
          <div className="min-w-0 flex-1">
            <h3 id="bootstrap-blocker-title" className={`font-semibold ${preview.blockers.length ? 'text-red-950' : 'text-slate-900'}`}>Problemas que impiden aplicar</h3>
            {preview.blockers.length ? (
              <ul className="mt-3 space-y-3">
                {preview.blockers.map((blocker) => {
                  const copy = designationBootstrapIssueCopy(blocker)
                  return (
                    <li key={blocker.code} className="border-b border-red-200 pb-3 last:border-0 last:pb-0">
                      <p className="text-sm font-medium text-red-950">{copy.title} <span className="tabular-nums">({blocker.count})</span></p>
                      <p className="mt-1 text-sm leading-5 text-red-800">Siguiente acción: {copy.action}</p>
                    </li>
                  )
                })}
              </ul>
            ) : <p className="mt-2 text-sm text-slate-600">No hay problemas bloqueantes. Puede confirmar la importación.</p>}
            {canResolve && (
              <Button type="button" className="mt-4 w-full sm:w-auto" onClick={onResolve} disabled={resolving}>
                {resolving ? 'Preparando coincidencias…' : 'Resolver coincidencias'}
              </Button>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
