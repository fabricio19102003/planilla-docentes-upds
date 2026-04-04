import { useCurrentBilling } from '@/api/hooks/useAuth'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Receipt, Clock, DollarSign, AlertCircle } from 'lucide-react'

function formatBs(value: number) {
  return `Bs ${value.toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function BillingPage() {
  const { data: billing, isLoading, error } = useCurrentBilling()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-8 h-8 border-2 border-[#003366]/30 border-t-[#003366] rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    const is400 = (error as { response?: { status?: number } })?.response?.status === 400
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-8 text-center max-w-md mx-auto mt-12">
        <AlertCircle size={40} className="text-red-400 mx-auto mb-3" />
        <p className="text-red-600 font-medium">
          {is400
            ? 'Tu cuenta no está vinculada a un docente'
            : 'No hay información de facturación disponible'}
        </p>
        <p className="text-red-400 text-sm mt-1">
          {is400
            ? 'Contactá al administrador para que vincule tu cuenta con tu registro de docente.'
            : 'Es posible que la planilla del mes actual aún no haya sido generada.'}
        </p>
      </div>
    )
  }

  if (!billing) return null

  const displayPayment = billing.adjusted_payment ?? billing.total_payment

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Main billing card */}
      <div
        className="rounded-2xl p-8 text-white relative overflow-hidden"
        style={{
          background: 'linear-gradient(135deg, #003366 0%, #0066CC 60%, #4DA8DA 100%)',
        }}
      >
        {/* Decorative circle */}
        <div
          className="absolute -right-16 -top-16 w-56 h-56 rounded-full opacity-10"
          style={{ backgroundColor: '#ffffff' }}
        />

        <div className="flex items-start justify-between relative">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Receipt size={18} className="text-white/70" />
              <p className="text-white/70 text-sm font-medium uppercase tracking-wider">
                Facturación — {billing.month_name} {billing.year}
              </p>
            </div>
            <p className="text-5xl font-black tracking-tight mt-4">
              {formatBs(displayPayment)}
            </p>
            {billing.adjusted_payment !== null && (
              <div className="mt-2 flex items-center gap-2">
                <Badge className="bg-yellow-400/20 text-yellow-200 border-yellow-300/30 text-xs">
                  Ajustado
                </Badge>
                <span className="text-white/50 text-sm line-through">
                  {formatBs(billing.total_payment)}
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
                  {['Materia', 'Grupo', 'Horas', 'Pago'].map((h) => (
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
                    <td colSpan={4} className="text-center py-8 text-gray-400">
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
                      <td className="px-4 py-3 text-gray-600">
                        <Badge className="bg-blue-100 text-blue-700 border-blue-200 font-mono">
                          {d.group}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-gray-700 font-semibold">{d.hours}h</td>
                      <td className="px-4 py-3 font-semibold" style={{ color: '#003366' }}>
                        {formatBs(d.payment)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
              {billing.designations.length > 0 && (
                <tfoot>
                  <tr className="border-t-2 border-gray-200 bg-gray-50">
                    <td colSpan={2} className="px-4 py-3 text-right font-semibold text-gray-600">
                      TOTAL
                    </td>
                    <td className="px-4 py-3 font-bold text-gray-800">
                      {billing.total_hours}h
                    </td>
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
      {billing.adjusted_payment !== null && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 flex items-start gap-3">
          <AlertCircle size={16} className="text-yellow-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-yellow-800 font-medium text-sm">Pago ajustado por administración</p>
            <p className="text-yellow-600 text-xs mt-0.5">
              El monto de {formatBs(billing.total_payment)} fue ajustado a {formatBs(billing.adjusted_payment)}.
              Para más información contactá al área de planillas.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
