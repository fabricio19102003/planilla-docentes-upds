import { useId } from 'react'

import { Badge } from '@/components/ui/badge'
import type { DetailRequestResolutionSnapshot } from '@/api/types'
import { resolutionDesignationKey, resolutionSlotKey } from '@/lib/adminRequestResolution'

export function ResolutionSnapshotPanel({
  snapshot,
  heading = 'Información resuelta',
}: {
  snapshot: DetailRequestResolutionSnapshot
  heading?: string
}) {
  const headingId = useId()

  if (snapshot.kind === 'hours_summary') {
    const statusCounts = snapshot.status_counts ?? {}
    return (
      <section aria-labelledby={headingId} className="space-y-2">
        <h3 id={headingId} className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{heading}</h3>
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-gray-700">
          <p><span className="font-medium">Horas académicas:</span> {snapshot.total_academic_hours ?? 0}</p>
          <p><span className="font-medium">Registros:</span> {snapshot.total_records ?? 0}</p>
          {Object.keys(statusCounts).length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-2" aria-label="Registros históricos por estado">
              {Object.entries(statusCounts).map(([status, count]) => (
                <li key={status} className="rounded-full bg-white px-2 py-1 text-xs">{status}: {count}</li>
              ))}
            </ul>
          )}
        </div>
      </section>
    )
  }

  if (snapshot.kind === 'schedule_detail') {
    const designations = snapshot.designations ?? []
    return (
      <section aria-labelledby={headingId} className="space-y-2">
        <h3 id={headingId} className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{heading}</h3>
        <p className="text-xs text-gray-500">
          Período académico: {snapshot.academic_period || 'No registrado'}
          {snapshot.effective_date ? ` · Vigente al ${snapshot.effective_date}` : ''}
        </p>
        {designations.length > 0 ? (
          <div className="space-y-2">
            {designations.map((designation, designationIndex) => {
              const designationKey = resolutionDesignationKey(designation, designationIndex)
              const schedule = designation.schedule ?? []
              return (
                <article key={designationKey} className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-[#003366]">{designation.subject} ({designation.group_code})</p>
                    {designation.source_kind && (
                      <Badge variant="outline" className="bg-white text-xs">
                        {designation.source_kind === 'published' ? 'Publicado' : 'Legado'}
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-gray-500">{designation.semester}</p>
                  {schedule.length > 0 ? (
                    <ul className="mt-2 space-y-1" aria-label={`Horario histórico de ${designation.subject}`}>
                      {schedule.map((slot, slotIndex) => (
                        <li key={resolutionSlotKey(designationKey, slot, slotIndex)} className="text-xs text-gray-700">
                          {slot.dia}: {slot.hora_inicio}–{slot.hora_fin} · {slot.horas_academicas}h
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-xs text-gray-500">Sin horario registrado al resolver.</p>
                  )}
                </article>
              )
            })}
          </div>
        ) : (
          <p className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-500">Sin horarios asignados al responder.</p>
        )}
      </section>
    )
  }

  const records = snapshot.records ?? []
  return (
    <section aria-labelledby={headingId} className="space-y-2">
      <h3 id={headingId} className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{heading}</h3>
      {records.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-blue-200" role="region" aria-label="Detalle biométrico histórico">
          <table className="min-w-[520px] w-full text-xs">
            <caption className="sr-only">Detalle biométrico histórico solicitado</caption>
            <thead className="bg-blue-50 text-left text-gray-600">
              <tr><th className="px-3 py-2">Fecha</th><th className="px-3 py-2">Entrada</th><th className="px-3 py-2">Salida</th><th className="px-3 py-2">Minutos</th><th className="px-3 py-2">Turno</th></tr>
            </thead>
            <tbody>
              {records.map((record, recordIndex) => (
                <tr key={[record.date, record.entry_time ?? '', record.exit_time ?? '', record.shift ?? '', recordIndex].join('|')} className="border-t border-blue-100">
                  <td className="px-3 py-2">{record.date}</td><td className="px-3 py-2">{record.entry_time ?? '—'}</td><td className="px-3 py-2">{record.exit_time ?? '—'}</td><td className="px-3 py-2">{record.worked_minutes ?? '—'}</td><td className="px-3 py-2">{record.shift ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-500">Sin marcaciones biométricas al responder.</p>
      )}
    </section>
  )
}
