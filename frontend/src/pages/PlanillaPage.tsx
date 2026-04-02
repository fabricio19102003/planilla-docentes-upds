import { useState } from 'react'
import { FileSpreadsheet, Download, Loader2, CheckCircle } from 'lucide-react'
import { useGeneratePlanilla, usePlanillaHistory } from '@/api/hooks/usePlanilla'
import { DataTable } from '@/components/shared/DataTable'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { PlanillaGenerateResponse, PlanillaOutput } from '@/api/types'
import type { Column } from '@/components/shared/DataTable'

const MONTH_NAMES: Record<number, string> = {
  1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
  5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
  9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`
}

const historyColumns: Column<PlanillaOutput>[] = [
  {
    key: 'month',
    header: 'Período',
    render: (item) => `${MONTH_NAMES[item.month]} ${item.year}`,
  },
  {
    key: 'generated_at',
    header: 'Generado el',
    render: (item) => formatDate(item.generated_at),
  },
  { key: 'total_teachers', header: 'Docentes' },
  {
    key: 'total_hours',
    header: 'Horas Totales',
    render: (item) => `${item.total_hours}h`,
  },
  {
    key: 'total_payment',
    header: 'Monto Total',
    render: (item) => `Bs ${parseFloat(item.total_payment).toFixed(2)}`,
  },
  {
    key: 'status',
    header: 'Estado',
    render: (item) => (
      <Badge
        className={
          item.status === 'GENERATED'
            ? 'bg-green-100 text-green-700'
            : 'bg-blue-100 text-blue-700'
        }
      >
        {item.status === 'GENERATED' ? 'Generada' : item.status}
      </Badge>
    ),
  },
  {
    key: 'id',
    header: 'Descargar',
    render: (item) =>
      item.file_path ? (
        <a
          href={`/api/planilla/${item.id}/download`}
          className="inline-flex items-center gap-1 text-[#0066CC] hover:underline text-sm font-medium"
          onClick={(e) => e.stopPropagation()}
        >
          <Download size={14} />
          Excel
        </a>
      ) : (
        <span className="text-gray-400 text-sm">No disponible</span>
      ),
  },
]

export function PlanillaPage() {
  const currentYear = new Date().getFullYear()
  const currentMonth = new Date().getMonth() + 1

  const [month, setMonth] = useState<number>(currentMonth)
  const [year, setYear] = useState<number>(currentYear)
  const [lastResult, setLastResult] = useState<PlanillaGenerateResponse | null>(null)

  const generatePlanilla = useGeneratePlanilla()
  const { data: history, isLoading: historyLoading } = usePlanillaHistory()

  const handleGenerate = () => {
    setLastResult(null)
    generatePlanilla.mutate(
      { month, year, payment_overrides: {} },
      {
        onSuccess: (data) => setLastResult(data),
      },
    )
  }

  return (
    <div className="space-y-6">
      {/* Generator Card */}
      <Card>
        <CardHeader>
          <CardTitle style={{ color: '#003366' }}>Generar Planilla de Pagos</CardTitle>
          <CardDescription>
            Seleccioná el período y generá la planilla de haberes docentes
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Mes</label>
              <select
                value={month}
                onChange={(e) => setMonth(Number(e.target.value))}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] min-w-[130px]"
              >
                {Object.entries(MONTH_NAMES).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Año</label>
              <input
                type="number"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                min={2020}
                max={2030}
                className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC] w-24"
              />
            </div>

            <Button
              onClick={handleGenerate}
              disabled={generatePlanilla.isPending}
              className="h-10"
              style={{ backgroundColor: '#003366' }}
            >
              {generatePlanilla.isPending ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Generando...
                </>
              ) : (
                <>
                  <FileSpreadsheet size={16} className="mr-2" />
                  Generar Planilla
                </>
              )}
            </Button>
          </div>

          {generatePlanilla.isError && (
            <div className="mt-4 p-3 bg-red-50 rounded-lg border border-red-200">
              <p className="text-sm text-red-600">
                Error al generar la planilla. Verificá que la asistencia esté procesada para el período seleccionado.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Result Card */}
      {lastResult && (
        <Card className="border-l-4" style={{ borderLeftColor: '#16a34a' }}>
          <CardContent className="py-5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <CheckCircle size={24} className="text-green-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-green-700">
                    ¡Planilla generada exitosamente!
                  </p>
                  <p className="text-sm text-gray-600 mt-1">
                    {MONTH_NAMES[lastResult.month]} {lastResult.year} · {lastResult.total_teachers} docentes · {lastResult.total_hours}h totales
                  </p>
                  <p className="text-lg font-bold mt-2" style={{ color: '#003366' }}>
                    Total: Bs {parseFloat(lastResult.total_payment).toFixed(2)}
                  </p>
                  {lastResult.warnings.length > 0 && (
                    <p className="text-xs text-yellow-600 mt-1">
                      {lastResult.warnings.length} advertencia(s) durante la generación
                    </p>
                  )}
                </div>
              </div>
              {lastResult.file_path && (
                <a href={`/api/planilla/${lastResult.planilla_id}/download`}>
                  <Button
                    variant="outline"
                    className="border-[#0066CC] text-[#0066CC] hover:bg-blue-50 gap-2"
                  >
                    <Download size={16} />
                    Descargar Excel
                  </Button>
                </a>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* History */}
      <Card>
        <CardHeader>
          <CardTitle style={{ color: '#003366' }}>Historial de Planillas</CardTitle>
        </CardHeader>
        <CardContent>
          {historyLoading ? (
            <LoadingPage />
          ) : (
            <DataTable
              columns={historyColumns}
              data={history ?? []}
              emptyMessage="No hay planillas generadas aún"
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
