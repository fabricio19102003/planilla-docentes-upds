import { useState } from 'react'
import { useBillingHistory } from '@/api/hooks/useAuth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { StatCard } from '@/components/shared/StatCard'
import { TrendingUp, Receipt, Clock, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react'
import type { BillingInfo } from '@/api/types'

function formatBs(value: number) {
  return `Bs ${value.toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function BillingRow({
  billing,
  isExpanded,
  onToggle,
}: {
  billing: BillingInfo
  isExpanded: boolean
  onToggle: () => void
}) {
  const displayPayment = billing.adjusted_payment ?? billing.total_payment

  return (
    <>
      <tr
        className="border-b hover:bg-blue-50 transition-colors cursor-pointer"
        onClick={onToggle}
      >
        <td className="px-4 py-3 font-medium text-gray-800">
          <div className="flex items-center gap-2">
            {isExpanded ? (
              <ChevronDown size={14} className="text-gray-400" />
            ) : (
              <ChevronRight size={14} className="text-gray-400" />
            )}
            {billing.month_name}
          </div>
        </td>
        <td className="px-4 py-3 text-gray-600">{billing.year}</td>
        <td className="px-4 py-3 text-gray-700 font-semibold">{billing.total_hours}h</td>
        <td className="px-4 py-3 font-semibold" style={{ color: '#003366' }}>
          {formatBs(displayPayment)}
          {billing.adjusted_payment !== null && (
            <Badge className="ml-2 bg-yellow-100 text-yellow-700 border-yellow-200 text-xs">
              Ajustado
            </Badge>
          )}
        </td>
        <td className="px-4 py-3 text-gray-500 text-xs">
          {(billing.designations?.length ?? 0)} materia{(billing.designations?.length ?? 0) !== 1 ? 's' : ''}
        </td>
      </tr>

      {/* Expanded detail rows */}
      {isExpanded && (billing.designations ?? []).map((d, i) => (
        <tr
          key={i}
          className="bg-blue-50/50 border-b last:border-0"
        >
          <td className="pl-10 pr-4 py-2 text-gray-600 text-sm">{d.subject}</td>
          <td className="px-4 py-2">
            <Badge className="bg-blue-100 text-blue-700 border-blue-200 font-mono text-xs">
              {d.group}
            </Badge>
          </td>
          <td className="px-4 py-2 text-gray-500 text-sm">{d.hours}h</td>
          <td className="px-4 py-2 text-sm font-medium" style={{ color: '#0066CC' }}>
            {formatBs(d.payment)}
          </td>
          <td className="px-4 py-2" />
        </tr>
      ))}
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
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !history) {
    const is400 = (error as { response?: { status?: number } })?.response?.status === 400
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center max-w-md mx-auto mt-12">
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

  const totalPayment = history.reduce((sum, b) => sum + (b.adjusted_payment ?? b.total_payment), 0)
  const totalHours = history.reduce((sum, b) => sum + b.total_hours, 0)

  return (
    <div className="space-y-6 max-w-3xl">
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
          subtitle="facturación total"
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
            Hacé click en una fila para ver el detalle
          </p>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: '#003366' }}>
                  {['Mes', 'Año', 'Horas', 'Pago Total', 'Materias'].map((h) => (
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
                    <td colSpan={5} className="text-center py-12 text-gray-400">
                      Sin historial de facturación
                    </td>
                  </tr>
                ) : (
                  history.map((billing) => {
                    const key = `${billing.year}-${billing.month}`
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
