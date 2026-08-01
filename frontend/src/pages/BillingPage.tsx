import { useCurrentBilling } from '@/api/hooks/useAuth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Receipt, Clock, DollarSign, AlertCircle, Calendar, CalendarOff, BookOpen } from 'lucide-react'
import type { BillingInfo, BillingUnavailableInfo } from '@/api/types'

function formatBs(value: number) {
  return `Bs ${value.toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatPortalDate(value: string) {
  const [year, month, day] = value.split('-')
  const monthNames = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
  const monthIndex = Number(month) - 1

  if (!year || !month || !day || monthIndex < 0 || monthIndex > 11) return value

  return `${Number(day)}/${monthNames[monthIndex]}/${year}`
}

const REGULAR_GRADIENT = 'linear-gradient(135deg, #003366 0%, #0066CC 60%, #4DA8DA 100%)'
const PRACTICE_GRADIENT = 'linear-gradient(135deg, #1a5c3a 0%, #2d8a5a 60%, #5ab98a 100%)'

function BillingCard({ billing }: { billing: BillingInfo }) {
  const isPractice = billing.planilla_type === 'practice'
  const gradient = isPractice ? PRACTICE_GRADIENT : REGULAR_GRADIENT
  const displayPayment = billing.net_payment
  const hasAdjustments = billing.has_admin_override
  const hasBillingPeriod = Boolean(billing.start_date && billing.end_date)
  const hasExcludedDays = Boolean(billing.excluded_days?.length)

  return (
    <div className="space-y-4">
      {/* Main billing hero card */}
      <div
        className="rounded-2xl p-8 text-white relative overflow-hidden"
        style={{ background: gradient }}
      >
        {/* Decorative circle */}
        <div
          className="absolute -right-16 -top-16 w-56 h-56 rounded-full opacity-10"
          style={{ backgroundColor: '#ffffff' }}
        />

        <div className="flex items-start justify-between relative">
          <div>
            <div className="flex items-center gap-2 mb-2">
              {isPractice ? (
                <BookOpen size={18} className="text-white/70" />
              ) : (
                <Receipt size={18} className="text-white/70" />
              )}
              <p className="text-white/70 text-sm font-medium uppercase tracking-wider">
                {isPractice ? 'Prácticas Internas' : 'Facturación'} — {billing.month_name} {billing.year}
              </p>
            </div>
            <p className="text-5xl font-black tracking-tight mt-4">
              {formatBs(displayPayment)}
            </p>
            {billing.has_admin_override && (
              <div className="mt-2 flex items-center gap-2">
                <Badge className="bg-yellow-400/20 text-yellow-200 border-yellow-300/30 text-xs">
                  Ajustado
                </Badge>
                <span className="text-white/50 text-sm line-through">
                  Base luego de retención: {formatBs(billing.gross_payment - billing.retention_amount)}
                </span>
              </div>
            )}
          </div>
          <div className="text-right">
            <div className="bg-white/10 rounded-xl p-4 text-center min-w-[100px]">
              <p className="text-3xl font-bold">{billing.total_hours}</p>
              <p className="text-white/70 text-xs mt-1">horas académicas</p>
            </div>
          </div>
        </div>

        <div className="mt-6 pt-5 border-t border-white/20 flex items-center gap-5 text-sm text-white/70">
          <div className="flex items-center gap-1.5">
            <DollarSign size={14} />
            <span>
              Tarifa: <span className="text-white font-semibold">{formatBs(billing.rate_per_hour)}</span>/hora académica
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <Clock size={14} />
            <span>
              {billing.designations.length} materia{billing.designations.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold" style={{ color: '#003366' }}>
            Conciliación del pago
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex justify-between gap-4"><span>Bruto</span><strong>{formatBs(billing.gross_payment)}</strong></div>
          <div className="flex justify-between gap-4 text-red-700">
            <span>RC-IVA / retención ({(billing.retention_rate * 100).toFixed(0)}%)</span>
            <strong>- {formatBs(billing.retention_amount)}</strong>
          </div>
          {billing.has_admin_override && (
            <div className="flex justify-between gap-4 text-yellow-700">
              <span>Ajuste administrativo</span>
              <strong>{billing.admin_adjustment >= 0 ? '+ ' : '- '}{formatBs(Math.abs(billing.admin_adjustment))}</strong>
            </div>
          )}
          <div className="flex justify-between gap-4 border-t pt-2 text-base" style={{ color: '#003366' }}>
            <span className="font-semibold">Neto final</span><strong>{formatBs(billing.net_payment)}</strong>
          </div>
        </CardContent>
      </Card>

      {(hasBillingPeriod || hasExcludedDays) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold" style={{ color: '#003366' }}>
              Contexto de planilla
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {hasBillingPeriod && billing.start_date && billing.end_date && (
              <div className="flex items-center gap-3 rounded-xl border border-blue-100 bg-blue-50/60 px-4 py-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-[#003366] shadow-sm">
                  <Calendar size={18} />
                </div>
                <p className="text-sm text-gray-700">
                  <span className="font-semibold" style={{ color: '#003366' }}>Período:</span>{' '}
                  {formatPortalDate(billing.start_date)} al {formatPortalDate(billing.end_date)}
                </p>
              </div>
            )}

            {hasExcludedDays && (
              <div className="rounded-xl border border-gray-200 bg-white">
                <div className="flex items-center gap-3 border-b border-gray-100 px-4 py-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gray-50 text-[#003366]">
                    <CalendarOff size={18} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: '#003366' }}>
                      Días no trabajados
                    </p>
                    <p className="text-xs text-gray-500">Aplican a tus materias o semestre asignado.</p>
                  </div>
                </div>
                <ul className="divide-y divide-gray-100">
                  {billing.excluded_days?.map((day) => (
                    <li key={day.date} className="px-4 py-3 text-sm text-gray-700">
                      <span className="font-medium text-gray-900">{formatPortalDate(day.date)}</span>
                      {day.reason && <span className="text-gray-500"> — {day.reason}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Designations breakdown */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold" style={{ color: '#003366' }}>
            Detalle por Materia
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: '#003366' }}>
                  {[
                    'Materia', 'Semestre', 'Grupo', 'Horas', 'Bruto', 'Retención',
                    ...(hasAdjustments ? ['Ajuste'] : []),
                    'Neto',
                  ].map((h) => (
                    <th
                      key={h}
                      className="text-left text-white font-semibold text-xs uppercase tracking-wider px-4 py-3"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!billing.designations.length ? (
                  <tr>
                    <td colSpan={hasAdjustments ? 8 : 7} className="text-center py-8 text-gray-400">
                      Sin designaciones este mes
                    </td>
                  </tr>
                ) : (
                  billing.designations.map((d, i) => (
                    <tr
                      key={i}
                      className={`border-b last:border-0 ${i % 2 === 1 ? 'bg-gray-50' : 'bg-white'}`}
                    >
                      <td className="px-4 py-3 font-medium text-gray-800">{d.subject}</td>
                      <td className="px-4 py-3 text-gray-600">{d.semester}</td>
                      <td className="px-4 py-3 text-gray-600">
                        <Badge className="bg-blue-100 text-blue-700 border-blue-200 font-mono">
                          {d.group}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-gray-700 font-semibold">{d.hours}h</td>
                      <td className="px-4 py-3 text-gray-700">{formatBs(d.gross_payment)}</td>
                      <td className="px-4 py-3 text-red-700">- {formatBs(d.retention_amount)}</td>
                      {hasAdjustments && (
                        <td className="px-4 py-3 text-yellow-700">
                          {d.has_admin_override
                            ? `${d.admin_adjustment >= 0 ? '+' : '-'} ${formatBs(Math.abs(d.admin_adjustment))}`
                            : '—'}
                        </td>
                      )}
                      <td className="px-4 py-3 font-semibold" style={{ color: '#003366' }}>
                        {formatBs(d.net_payment)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
              {billing.designations.length > 0 && (
                <tfoot>
                  <tr className="border-t-2 border-gray-200 bg-gray-50">
                    <td colSpan={3} className="px-4 py-3 text-right font-semibold text-gray-600">
                      TOTAL
                    </td>
                    <td className="px-4 py-3 font-bold text-gray-800">
                      {billing.total_hours}h
                    </td>
                    <td className="px-4 py-3 font-bold text-gray-800">{formatBs(billing.gross_payment)}</td>
                    <td className="px-4 py-3 font-bold text-red-700">- {formatBs(billing.retention_amount)}</td>
                    {hasAdjustments && (
                      <td className="px-4 py-3 font-bold text-yellow-700">
                        {`${billing.admin_adjustment >= 0 ? '+' : '-'} ${formatBs(Math.abs(billing.admin_adjustment))}`}
                      </td>
                    )}
                    <td className="px-4 py-3 font-bold text-lg" style={{ color: '#003366' }}>
                      {formatBs(displayPayment)}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Note if adjusted */}
      {billing.has_admin_override && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 flex items-start gap-3">
          <AlertCircle size={16} className="text-yellow-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-yellow-800 font-medium text-sm">Pago ajustado por administración</p>
            <p className="text-yellow-600 text-xs mt-0.5">
              El ajuste administrativo de {formatBs(billing.admin_adjustment)} deja un neto final de {formatBs(billing.net_payment)}.
              Para más información contactá al área de planillas.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

function BillingUnavailableNotice({ billing }: { billing: BillingUnavailableInfo }) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-8 text-center">
      <Receipt size={40} className="text-blue-400 mx-auto mb-3" />
      <p className="text-blue-700 font-medium">Facturación publicada sin detalle disponible</p>
      <p className="text-blue-600 text-sm mt-1">{billing.unavailable_reason}</p>
    </div>
  )
}

export function BillingPage() {
  const { data: combined, isLoading, error } = useCurrentBilling()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    const httpStatus = (error as { response?: { status?: number } })?.response?.status
    if (httpStatus === 404) {
      return (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-8 text-center max-w-md mx-auto mt-12">
          <Clock size={40} className="text-yellow-400 mx-auto mb-3" />
          <p className="text-yellow-700 font-medium">Facturación aún no publicada</p>
          <p className="text-yellow-500 text-sm mt-1">
            El administrador aún no ha publicado los montos a facturar para este mes.
            Serás notificado cuando estén disponibles.
          </p>
        </div>
      )
    }
    if (httpStatus === 400) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center max-w-md mx-auto mt-12">
          <AlertCircle size={40} className="text-red-400 mx-auto mb-3" />
          <p className="text-red-600 font-medium">Tu cuenta no está vinculada a un docente</p>
          <p className="text-red-400 text-sm mt-1">
            Contactá al administrador para que vincule tu cuenta con tu registro de docente.
          </p>
        </div>
      )
    }
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center max-w-md mx-auto mt-12">
        <AlertCircle size={40} className="text-red-400 mx-auto mb-3" />
        <p className="text-red-600 font-medium">No hay información de facturación disponible</p>
      </div>
    )
  }

  if (!combined) return null

  const { regular, practice } = combined
  const hasBoth = Boolean(regular && practice)

  return (
    <div className="space-y-8 max-w-3xl">
      {regular && (
        <div>
          {hasBoth && (
            <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-3">
              Teóricas
            </h2>
          )}
          {'data_status' in regular
            ? <BillingUnavailableNotice billing={regular} />
            : <BillingCard billing={regular} />}
        </div>
      )}

      {practice && (
        <div>
          {hasBoth && (
            <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-3">
              Prácticas Internas
            </h2>
          )}
          {'data_status' in practice
            ? <BillingUnavailableNotice billing={practice} />
            : <BillingCard billing={practice} />}
        </div>
      )}
    </div>
  )
}
