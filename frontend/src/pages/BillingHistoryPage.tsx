import { useState } from 'react'
import { useBillingHistory } from '@/api/hooks/useAuth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { cn } from '@/lib/utils'
import { TrendingUp, Receipt, Clock, ChevronDown, ChevronRight, AlertCircle, Inbox } from 'lucide-react'
import type { BillingHistoryInfo } from '@/api/types'
import { invoiceInstruction } from '@/lib/billingInvoice'

function formatBs(value: number) {
  return `Bs ${value.toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const DETAIL_HEADINGS_NUMERIC = new Set(['Horas', 'Bruto', 'Retención', 'Ajuste', 'Neto'])

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
  const instruction = isAvailable ? invoiceInstruction(billing) : null
  const detailId = `billing-detail-${billing.year}-${billing.month}-${billing.planilla_type ?? 'regular'}`

  return (
    <>
      <tr className={cn('border-b transition-colors', isAvailable ? 'hover:bg-muted/40' : 'bg-warning/4')}>
        <td className="px-4 py-3 font-medium text-foreground">
          {isAvailable ? (
            <button
              type="button"
              onClick={onToggle}
              aria-expanded={isExpanded}
              aria-controls={detailId}
              className="flex items-center gap-2 rounded px-1 py-0.5 text-left transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              {isExpanded ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
              <span>{billing.month_name}</span>
              <span className="sr-only">{isExpanded ? 'Ocultar detalle' : 'Mostrar detalle'}</span>
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <AlertCircle size={14} className="text-warning-foreground" aria-hidden="true" />
              {billing.month_name}
            </div>
          )}
        </td>
        <td className="px-4 py-3 tabular-nums text-muted-foreground">{billing.year}</td>
        <td className="px-4 py-3">
          {isPractice ? (
            <Badge variant="success">Prácticas</Badge>
          ) : (
            <Badge variant="info">Teóricas</Badge>
          )}
        </td>
        <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-foreground">
          {isAvailable && billing.total_hours !== null ? `${billing.total_hours}h` : '—'}
        </td>
        <td className="px-4 py-3 text-right font-semibold tabular-nums text-foreground">
          {isAvailable && billing.net_payment !== null ? formatBs(billing.net_payment) : 'Dato no disponible'}
          {billing.has_admin_override && (
            <StatusBadge tone="warning" className="ml-2 align-middle">Ajustado</StatusBadge>
          )}
          {instruction && (
            <span className="block text-xs font-normal text-muted-foreground">{instruction.headline}</span>
          )}
        </td>
        <td className="px-4 py-3 text-xs text-muted-foreground">
          {isAvailable
            ? `${billing.designations.length} materia${billing.designations.length !== 1 ? 's' : ''}`
            : 'Histórico incompleto'}
        </td>
      </tr>

      {!isAvailable && (
        <tr className="border-b bg-warning/4">
          <td colSpan={6} className="px-10 py-3 text-sm text-warning-foreground">
            {billing.unavailable_reason ?? 'El detalle histórico no está disponible.'}
          </td>
        </tr>
      )}

      {isAvailable && isExpanded && (
        <tr id={detailId} className="border-b bg-muted/30">
          <td colSpan={6} className="px-6 py-4">
            <div className="mb-4 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div><span className="text-muted-foreground">Bruto:</span> <strong className="whitespace-nowrap tabular-nums">{formatBs(billing.gross_payment ?? 0)}</strong></div>
              {(billing.retention_amount ?? 0) > 0 && (
                <div><span className="text-muted-foreground">RC-IVA / retención:</span> <strong className="whitespace-nowrap tabular-nums text-destructive-foreground">- {formatBs(billing.retention_amount ?? 0)}</strong></div>
              )}
              {billing.has_admin_override && (
                <div><span className="text-muted-foreground">Ajuste administrativo:</span> <strong className="whitespace-nowrap tabular-nums text-warning-foreground">{formatBs(billing.admin_adjustment ?? 0)}</strong></div>
              )}
              <div><span className="text-muted-foreground">Total a cobrar:</span> <strong className="whitespace-nowrap tabular-nums text-foreground">{formatBs(billing.net_payment ?? 0)}</strong></div>
            </div>
            <div className="overflow-x-auto rounded-lg border bg-card">
              <table className="w-full text-xs">
                <thead className="bg-muted/50 text-muted-foreground">
                  <tr>
                    {[
                      'Materia', 'Semestre', 'Grupo', 'Horas', 'Bruto', 'Retención',
                      ...(billing.has_admin_override ? ['Ajuste'] : []),
                      'Neto',
                    ].map((heading) => (
                      <th
                        key={heading}
                        className={cn('whitespace-nowrap px-3 py-2 font-medium', DETAIL_HEADINGS_NUMERIC.has(heading) ? 'text-right' : 'text-left')}
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {billing.designations.map((designation, index) => (
                    <tr key={designation.source_key ?? `${designation.subject}-${designation.semester}-${designation.group}-${index}`} className="border-t">
                      <td className="px-3 py-2 font-medium">{designation.subject}</td>
                      <td className="px-3 py-2">{designation.semester}</td>
                      <td className="px-3 py-2">{designation.group}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{designation.hours}h</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{formatBs(designation.gross_payment)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-destructive-foreground">- {formatBs(designation.retention_amount)}</td>
                      {billing.has_admin_override && (
                        <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-warning-foreground">
                          {designation.has_admin_override ? formatBs(designation.admin_adjustment) : '—'}
                        </td>
                      )}
                      <td className="whitespace-nowrap px-3 py-2 text-right font-semibold tabular-nums">{formatBs(designation.net_payment)}</td>
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

function BillingMonthCard({
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
  const instruction = isAvailable ? invoiceInstruction(billing) : null
  const detailId = `billing-detail-${billing.year}-${billing.month}-${billing.planilla_type ?? 'regular'}-mobile`

  const typeBadge = isPractice ? (
    <Badge variant="success">Prácticas</Badge>
  ) : (
    <Badge variant="info">Teóricas</Badge>
  )

  return (
    <Card render={<article />} className={cn('p-4', !isAvailable && 'border-warning/32 bg-warning/4')}>
      <div className="flex items-start justify-between gap-3">
        {isAvailable ? (
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={isExpanded}
            aria-controls={detailId}
            className="flex items-center gap-2 rounded px-1 py-0.5 text-left font-medium text-foreground transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            {isExpanded ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
            <span>{billing.month_name} {billing.year}</span>
            <span className="sr-only">{isExpanded ? 'Ocultar detalle' : 'Mostrar detalle'}</span>
          </button>
        ) : (
          <div className="flex items-center gap-2 font-medium text-foreground">
            <AlertCircle size={14} className="text-warning-foreground" aria-hidden="true" />
            {billing.month_name} {billing.year}
          </div>
        )}
        <div className="shrink-0">{typeBadge}</div>
      </div>

      {isAvailable ? (
        <div className="mt-3">
          <p className="text-xs text-muted-foreground">
            <span className="font-semibold tabular-nums text-foreground">
              {billing.total_hours !== null ? `${billing.total_hours}h` : '—'}
            </span>
            {' · '}
            {billing.designations.length} materia{billing.designations.length !== 1 ? 's' : ''}
          </p>
          {instruction && (
            <p className="mt-2 text-xs font-normal text-muted-foreground">{instruction.headline}</p>
          )}
          <p className="break-words text-xl font-semibold tabular-nums text-foreground">
            {billing.net_payment !== null ? formatBs(billing.net_payment) : 'Dato no disponible'}
            {billing.has_admin_override && (
              <StatusBadge tone="warning" className="ml-2 align-middle">Ajustado</StatusBadge>
            )}
          </p>
        </div>
      ) : (
        <div className="mt-3 text-sm text-warning-foreground">
          <p className="font-medium">Histórico incompleto</p>
          <p className="mt-1">{billing.unavailable_reason ?? 'El detalle histórico no está disponible.'}</p>
        </div>
      )}

      {isAvailable && isExpanded && (
        <div id={detailId} className="mt-4 space-y-3 border-t pt-4">
          <dl className="space-y-1.5 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Bruto</dt>
              <dd className="text-right font-semibold tabular-nums">{formatBs(billing.gross_payment ?? 0)}</dd>
            </div>
            {(billing.retention_amount ?? 0) > 0 && (
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Retención</dt>
                <dd className="text-right font-semibold tabular-nums text-destructive-foreground">- {formatBs(billing.retention_amount ?? 0)}</dd>
              </div>
            )}
            {billing.has_admin_override && (
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Ajuste</dt>
                <dd className="text-right font-semibold tabular-nums text-warning-foreground">{formatBs(billing.admin_adjustment ?? 0)}</dd>
              </div>
            )}
            <div className="flex justify-between gap-4 border-t pt-1.5">
              <dt className="font-semibold text-muted-foreground">Total a cobrar</dt>
              <dd className="text-right font-semibold tabular-nums text-foreground">{formatBs(billing.net_payment ?? 0)}</dd>
            </div>
          </dl>
          {billing.designations.map((designation, index) => (
            <div
              key={designation.source_key ?? `${designation.subject}-${designation.semester}-${designation.group}-${index}`}
              className="rounded-lg bg-muted/40 p-3 text-sm"
            >
              <p className="break-words font-medium text-foreground">{designation.subject}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Semestre {designation.semester} · Grupo {designation.group} ·{' '}
                <span className="font-semibold tabular-nums text-foreground">{designation.hours}h</span>
              </p>
              <dl className="mt-2 space-y-1">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Bruto</dt>
                  <dd className="text-right tabular-nums">{formatBs(designation.gross_payment)}</dd>
                </div>
                {designation.retention_amount > 0 && (
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">Retención</dt>
                    <dd className="text-right tabular-nums text-destructive-foreground">- {formatBs(designation.retention_amount)}</dd>
                  </div>
                )}
                {designation.has_admin_override && (
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">Ajuste</dt>
                    <dd className="text-right tabular-nums text-warning-foreground">{formatBs(designation.admin_adjustment)}</dd>
                  </div>
                )}
                <div className="flex justify-between gap-4 border-t pt-1">
                  <dt className="font-semibold text-muted-foreground">Neto</dt>
                  <dd className="text-right font-semibold tabular-nums text-foreground">{formatBs(designation.net_payment)}</dd>
                </div>
              </dl>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function HistorySkeleton() {
  return (
    <div role="status" aria-busy="true" className="space-y-4">
      <span className="sr-only">Cargando historial</span>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-64 w-full rounded-2xl" />
    </div>
  )
}

export function BillingHistoryPage() {
  const { data: history, isLoading, error } = useBillingHistory()
  const [expandedMonth, setExpandedMonth] = useState<string | null>(null)

  const toggleExpand = (key: string) => {
    setExpandedMonth((prev) => (prev === key ? null : key))
  }

  const header = (
    <PageHeader
      title="Histórico de pagos"
      description="Todos los meses publicados, con su total a cobrar."
    />
  )

  if (isLoading) {
    return (
      <div className="max-w-4xl">
        {header}
        <HistorySkeleton />
      </div>
    )
  }

  if (error || !history) {
    const is400 = (error as { response?: { status?: number } })?.response?.status === 400
    return (
      <div className="max-w-4xl">
        {header}
        <Alert variant="error">
          <AlertCircle aria-hidden="true" />
          <AlertTitle>
            {is400
              ? 'Tu cuenta no está vinculada a un docente'
              : 'No se pudo cargar el historial'}
          </AlertTitle>
          {is400 && (
            <AlertDescription>
              Contactá al administrador para que vincule tu cuenta con tu registro de docente.
            </AlertDescription>
          )}
        </Alert>
      </div>
    )
  }

  const availableHistory = history.filter((billing) => billing.data_status === 'available')
  const totalPayment = availableHistory.reduce((sum, billing) => sum + (billing.net_payment ?? 0), 0)
  const totalHours = availableHistory.reduce((sum, billing) => sum + (billing.total_hours ?? 0), 0)

  return (
    <div className="max-w-4xl">
      {header}
      <div className="space-y-4 sm:space-y-6">
        {/* Summary stats */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <StatCard
            icon={Receipt}
            title="Meses Registrados"
            value={history.length}
            subtitle="en el historial"
            tone="primary"
          />
          <StatCard
            icon={Clock}
            title="Total de Horas"
            value={`${totalHours}h`}
            subtitle="horas académicas"
            tone="info"
          />
          <StatCard
            icon={TrendingUp}
            title="Total Acumulado"
            value={formatBs(totalPayment)}
            subtitle="suma de los meses publicados"
            tone="success"
            className="sm:col-span-2 xl:col-span-1"
          />
        </div>

        {/* History: cards below sm (every month amount visible), table from sm up */}
        {!history.length ? (
          <Card>
            <EmptyState
              icon={Inbox}
              title="No hay meses publicados en tu historial de facturación"
            />
          </Card>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">Activá el botón del mes para ver el detalle</p>
            <div data-testid="history-mobile-list" className="space-y-3 sm:hidden">
              {history.map((billing) => {
                const key = `${billing.planilla_type ?? 'regular'}-${billing.year}-${billing.month}`
                return (
                  <BillingMonthCard
                    key={key}
                    billing={billing}
                    isExpanded={expandedMonth === key}
                    onToggle={() => toggleExpand(key)}
                  />
                )
              })}
            </div>
            <Card className="hidden sm:block gap-0 overflow-hidden">
              <CardHeader className="border-b pb-4">
                <CardTitle className="text-base">Historial de Facturación</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="min-w-[720px] w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/40">
                        {['Mes', 'Año', 'Tipo', 'Horas', 'Total a cobrar', 'Materias'].map((h) => (
                          <th
                            key={h}
                            className={cn(
                              'whitespace-nowrap px-4 py-3 text-xs font-medium uppercase tracking-wider text-muted-foreground',
                              h === 'Horas' || h === 'Total a cobrar' ? 'text-right' : 'text-left',
                            )}
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((billing) => {
                        const key = `${billing.planilla_type ?? 'regular'}-${billing.year}-${billing.month}`
                        return (
                          <BillingRow
                            key={key}
                            billing={billing}
                            isExpanded={expandedMonth === key}
                            onToggle={() => toggleExpand(key)}
                          />
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}
