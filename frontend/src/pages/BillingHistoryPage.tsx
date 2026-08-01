import { useState } from 'react'
import { useBillingHistory } from '@/api/hooks/useAuth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { StatCard } from '@/components/shared/StatCard'
import { TrendingUp, Receipt, Clock, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react'
import type { BillingHistoryInfo } from '@/api/types'

function formatBs(value: number) {
  return `Bs ${value.toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function BillingRow({
  billing,
  isExpanded,
  onToggle,
}: {
  billing: BillingHistoryInfo
  isExpanded: boolean
  onToggle: () => void
}) {
  const isPractice = billing.planilla_type === 'practice'
  const isAvailable = billing.data_status === 'available'
  const detailId = `billing-detail-${billing.year}-${billing.month}-${billing.planilla_type ?? 'regular'}`

  return (
    <>
      <tr className={`border-b transition-colors ${isAvailable ? 'hover:bg-blue-50' : 'bg-amber-50/50'}`}>
        <td className="px-4 py-3 font-medium text-gray-800">
          {isAvailable ? (
            <button
              type="button"
              onClick={onToggle}
              aria-expanded={isExpanded}
              aria-controls={detailId}
              className="flex items-center gap-2 rounded px-1 py-0.5 text-left transition-colors hover:text-[#0066CC] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0066CC] focus-visible:ring-offset-2"
            >
              {isExpanded ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
              <span>{billing.month_name}</span>
              <span className="sr-only">{isExpanded ? 'Ocultar detalle' : 'Mostrar detalle'}</span>
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <AlertCircle size={14} className="text-amber-600" aria-hidden="true" />
              {billing.month_name}
            </div>
          )}
        </td>
        <td className="px-4 py-3 text-gray-600">{billing.year}</td>
        <td className="px-4 py-3">
          {isPractice ? (
            <Badge className="bg-green-100 text-green-700 border-green-200 text-xs">
              Prácticas
            </Badge>
          ) : (
            <Badge className="bg-blue-100 text-blue-700 border-blue-200 text-xs">
              Teóricas
            </Badge>
          )}
        </td>
        <td className="px-4 py-3 text-gray-700 font-semibold">
          {isAvailable && billing.total_hours !== null ? `${billing.total_hours}h` : '—'}
        </td>
        <td className="px-4 py-3 font-semibold" style={{ color: '#003366' }}>
          {isAvailable && billing.net_payment !== null ? formatBs(billing.net_payment) : 'Dato no disponible'}
          {billing.has_admin_override && (
            <Badge className="ml-2 bg-yellow-100 text-yellow-700 border-yellow-200 text-xs">
              Ajustado
            </Badge>
          )}
        </td>
        <td className="px-4 py-3 text-gray-500 text-xs">
          {isAvailable
            ? `${billing.designations.length} materia${billing.designations.length !== 1 ? 's' : ''}`
            : 'Histórico incompleto'}
        </td>
      </tr>

      {!isAvailable && (
        <tr className="border-b bg-amber-50/50">
          <td colSpan={6} className="px-10 py-3 text-sm text-amber-800">
            {billing.unavailable_reason ?? 'El detalle histórico no está disponible.'}
          </td>
        </tr>
      )}

      {isAvailable && isExpanded && (
        <tr id={detailId} className="border-b bg-blue-50/50">
          <td colSpan={6} className="px-6 py-4">
            <div className="mb-4 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div><span className="text-gray-500">Bruto:</span> <strong>{formatBs(billing.gross_payment ?? 0)}</strong></div>
              <div><span className="text-gray-500">RC-IVA / retención:</span> <strong className="text-red-700">- {formatBs(billing.retention_amount ?? 0)}</strong></div>
              {billing.has_admin_override && (
                <div><span className="text-gray-500">Ajuste administrativo:</span> <strong className="text-yellow-700">{formatBs(billing.admin_adjustment ?? 0)}</strong></div>
              )}
              <div><span className="text-gray-500">Neto final:</span> <strong style={{ color: '#003366' }}>{formatBs(billing.net_payment ?? 0)}</strong></div>
            </div>
            <div className="overflow-x-auto rounded border border-blue-100 bg-white">
              <table className="w-full text-xs">
                <thead className="bg-blue-100 text-blue-900">
                  <tr>
                    {[
                      'Materia', 'Semestre', 'Grupo', 'Horas', 'Bruto', 'Retención',
                      ...(billing.has_admin_override ? ['Ajuste'] : []),
                      'Neto',
                    ].map((heading) => (
                      <th key={heading} className="px-3 py-2 text-left font-semibold">{heading}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {billing.designations.map((designation, index) => (
                    <tr key={`${designation.subject}-${designation.semester}-${designation.group}-${index}`} className="border-t">
                      <td className="px-3 py-2 font-medium">{designation.subject}</td>
                      <td className="px-3 py-2">{designation.semester}</td>
                      <td className="px-3 py-2">{designation.group}</td>
                      <td className="px-3 py-2">{designation.hours}h</td>
                      <td className="px-3 py-2">{formatBs(designation.gross_payment)}</td>
                      <td className="px-3 py-2 text-red-700">- {formatBs(designation.retention_amount)}</td>
                      {billing.has_admin_override && (
                        <td className="px-3 py-2 text-yellow-700">
                          {designation.has_admin_override ? formatBs(designation.admin_adjustment) : '—'}
                        </td>
                      )}
                      <td className="px-3 py-2 font-semibold">{formatBs(designation.net_payment)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export function BillingHistoryPage() {
  const { data: history, isLoading, error } = useBillingHistory()
  const [expandedMonth, setExpandedMonth] = useState<string | null>(null)

  const toggleExpand = (key: string) => {
    setExpandedMonth((prev) => (prev === key ? null : key))
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin motion-reduce:animate-none" />
      </div>
    )
  }

  if (error || !history) {
    const is400 = (error as { response?: { status?: number } })?.response?.status === 400
    return (
      <div role="alert" className="bg-red-50 border border-red-200 rounded-lg p-5 text-center max-w-md mx-auto mt-12 sm:p-8">
        <AlertCircle size={40} className="text-red-400 mx-auto mb-3" />
        <p className="text-red-600 font-medium">
          {is400
            ? 'Tu cuenta no está vinculada a un docente'
            : 'No se pudo cargar el historial'}
        </p>
        {is400 && (
          <p className="text-red-400 text-sm mt-1">
            Contactá al administrador para que vincule tu cuenta con tu registro de docente.
          </p>
        )}
      </div>
    )
  }

  const availableHistory = history.filter((billing) => billing.data_status === 'available')
  const totalPayment = availableHistory.reduce((sum, billing) => sum + (billing.net_payment ?? 0), 0)
  const totalHours = availableHistory.reduce((sum, billing) => sum + (billing.total_hours ?? 0), 0)

  return (
    <div className="max-w-3xl space-y-4 sm:space-y-6">
      {/* Summary stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          icon={Receipt}
          title="Meses Registrados"
          value={history.length}
          subtitle="en el historial"
          color="#003366"
        />
        <StatCard
          icon={Clock}
          title="Total de Horas"
          value={`${totalHours}h`}
          subtitle="horas académicas"
          color="#0066CC"
        />
        <StatCard
          icon={TrendingUp}
          title="Total Acumulado"
          value={formatBs(totalPayment)}
          subtitle="solo datos conciliables"
          color="#4DA8DA"
        />
      </div>

      {/* History table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold" style={{ color: '#003366' }}>
            Historial de Facturación
          </CardTitle>
          <p className="text-xs text-gray-400 mt-0.5">
            Activá el botón del mes para ver el detalle
          </p>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="min-w-[720px] w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: '#003366' }}>
                  {['Mes', 'Año', 'Tipo', 'Horas', 'Neto Final', 'Materias'].map((h) => (
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
                {!history.length ? (
                  <tr>
                    <td colSpan={6} className="text-center py-12 text-gray-400">
                      No hay meses publicados en tu historial de facturación
                    </td>
                  </tr>
                ) : (
                  history.map((billing) => {
                    const key = `${billing.planilla_type ?? 'regular'}-${billing.year}-${billing.month}`
                    return (
                      <BillingRow
                        key={key}
                        billing={billing}
                        isExpanded={expandedMonth === key}
                        onToggle={() => toggleExpand(key)}
                      />
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
