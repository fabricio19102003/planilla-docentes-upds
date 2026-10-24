import { Link } from 'react-router-dom'
import { useCurrentBilling } from '@/api/hooks/useAuth'
import { invoiceInstruction, RETENTION_LETTER_PATH } from '@/lib/billingInvoice'
import { cn } from '@/lib/utils'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/shared/EmptyState'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { TONE_CHIP } from '@/components/shared/tones'
import { Receipt, Clock, DollarSign, AlertCircle, Calendar, CalendarOff, BookOpen } from 'lucide-react'
import type { BillingDesignation, BillingInfo, BillingUnavailableInfo } from '@/api/types'

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

function formatAdjustment(value: number) {
  return `${value >= 0 ? '+' : '-'} ${formatBs(Math.abs(value))}`
}

const NUMERIC_HEADINGS = new Set(['Horas', 'Bruto', 'Retención', 'Ajuste', 'Neto'])

function DesignationMobileCard({ designation }: { designation: BillingDesignation }) {
  return (
    <Card render={<article />} className="p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 break-words font-medium text-foreground">{designation.subject}</p>
        <Badge variant="outline" className="shrink-0 font-mono">
          {designation.group}
        </Badge>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Semestre {designation.semester} · <span className="font-semibold tabular-nums text-foreground">{designation.hours}h</span>
      </p>
      <dl className="mt-3 space-y-1.5 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Bruto</dt>
          <dd className="text-right tabular-nums text-foreground">{formatBs(designation.gross_payment)}</dd>
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
            <dd className="text-right tabular-nums text-warning-foreground">{formatAdjustment(designation.admin_adjustment)}</dd>
          </div>
        )}
        <div className="flex justify-between gap-4 border-t pt-1.5">
          <dt className="font-semibold text-muted-foreground">Neto</dt>
          <dd className="text-right font-semibold tabular-nums text-foreground">{formatBs(designation.net_payment)}</dd>
        </div>
      </dl>
    </Card>
  )
}

function BillingCard({ billing }: { billing: BillingInfo }) {
  const isPractice = billing.planilla_type === 'practice'
  const instruction = invoiceInstruction(billing)
  const displayPayment = instruction?.amount ?? billing.net_payment
  const hasAdjustments = billing.has_admin_override
  const hasBillingPeriod = Boolean(billing.start_date && billing.end_date)
  const hasExcludedDays = Boolean(billing.excluded_days?.length)

  return (
    <div className="space-y-4">
      {/* Main billing hero card */}
      <Card className="p-4 sm:p-8">
        <div className="flex flex-col items-start justify-between gap-4 sm:flex-row">
          <div className="min-w-0">
            <div className="mb-2 flex items-center gap-2">
              <span className={cn('flex size-8 shrink-0 items-center justify-center rounded-lg', TONE_CHIP[isPractice ? 'success' : 'primary'])}>
                {isPractice ? <BookOpen size={16} aria-hidden="true" /> : <Receipt size={16} aria-hidden="true" />}
              </span>
              <p className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
                {isPractice ? 'Prácticas Internas' : 'Teóricas'} — {billing.month_name} {billing.year}
              </p>
            </div>
            {hasBillingPeriod && billing.start_date && billing.end_date && (
              <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Calendar size={14} className="shrink-0" aria-hidden="true" />
                <span>
                  Corte: {formatPortalDate(billing.start_date)} al {formatPortalDate(billing.end_date)}
                </span>
              </p>
            )}
            {instruction && (
              <p className="mt-3 text-sm font-semibold text-foreground">{instruction.headline}</p>
            )}
            <p className="mt-1 break-words text-3xl font-semibold tracking-tight tabular-nums text-foreground sm:text-5xl">
              {formatBs(displayPayment)}
            </p>
            {instruction && (
              <p className="mt-2 text-sm text-muted-foreground">
                {instruction.note}
                {instruction.kind === 'retention_letter' && (
                  <>
                    {' '}
                    <Link to={RETENTION_LETTER_PATH} className="font-semibold text-primary underline underline-offset-4">
                      Generar carta de retención
                    </Link>
                  </>
                )}
              </p>
            )}
            {billing.has_admin_override && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <StatusBadge tone="warning">Ajustado</StatusBadge>
                <span className="text-sm tabular-nums text-muted-foreground line-through">
                  Base luego de retención: {formatBs(billing.gross_payment - billing.retention_amount)}
                </span>
              </div>
            )}
          </div>
          <div className="rounded-xl bg-muted/60 p-4 text-center sm:min-w-[7rem]">
            <p className="text-3xl font-semibold tabular-nums text-foreground">{billing.total_hours}</p>
            <p className="mt-1 text-xs text-muted-foreground">horas académicas</p>
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-3 border-t pt-5 text-sm text-muted-foreground sm:flex-row sm:items-center sm:gap-5">
          <div className="flex items-center gap-1.5">
            <DollarSign size={14} aria-hidden="true" />
            <span>
              Tarifa: <span className="font-semibold tabular-nums text-foreground">{formatBs(billing.rate_per_hour)}</span>/hora académica
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <Clock size={14} aria-hidden="true" />
            <span>
              {billing.designations.length} materia{billing.designations.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader className="p-4 pb-0 sm:p-6 sm:pb-0">
          <CardTitle className="text-base">Cómo se calcula tu pago</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 p-4 text-sm sm:p-6">
          <div className="flex justify-between gap-4"><span>Bruto</span><strong className="tabular-nums">{formatBs(billing.gross_payment)}</strong></div>
          {billing.retention_amount > 0 && (
            <div className="flex justify-between gap-4 text-destructive-foreground">
              <span>RC-IVA / retención ({(billing.retention_rate * 100).toFixed(0)}%)</span>
              <strong className="tabular-nums">- {formatBs(billing.retention_amount)}</strong>
            </div>
          )}
          {billing.has_admin_override && (
            <div className="flex justify-between gap-4 text-warning-foreground">
              <span>Ajuste administrativo</span>
              <strong className="tabular-nums">{billing.admin_adjustment >= 0 ? '+ ' : '- '}{formatBs(Math.abs(billing.admin_adjustment))}</strong>
            </div>
          )}
          <div className="flex justify-between gap-4 border-t pt-2 text-base text-foreground">
            <span className="font-semibold">Total a cobrar</span><strong className="tabular-nums">{formatBs(billing.net_payment)}</strong>
          </div>
        </CardContent>
      </Card>

      {hasExcludedDays && (
        <Card>
          <CardHeader className="p-4 pb-0 sm:p-6 sm:pb-0">
            <CardTitle className="text-base">Contexto de planilla</CardTitle>
          </CardHeader>
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center gap-3 pb-3">
              <div className={cn('flex size-10 shrink-0 items-center justify-center rounded-full', TONE_CHIP.neutral)}>
                <CalendarOff size={18} aria-hidden="true" />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">Días no trabajados</p>
                <p className="text-xs text-muted-foreground">Aplican a tus materias o semestre asignado.</p>
              </div>
            </div>
            <ul className="divide-y border-t">
              {billing.excluded_days?.map((day) => (
                <li key={day.date} className="py-3 text-sm text-foreground">
                  <span className="font-medium tabular-nums">{formatPortalDate(day.date)}</span>
                  {day.reason && <span className="text-muted-foreground"> — {day.reason}</span>}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Designations breakdown: cards below sm so every amount stays visible, a table from sm up */}
      <section aria-labelledby={`designations-${billing.planilla_type}-heading`} className="space-y-3">
        <h3 id={`designations-${billing.planilla_type}-heading`} className="text-base font-semibold text-foreground">
          Detalle por Materia
        </h3>
        <div data-testid="designation-mobile-list" className="space-y-3 sm:hidden">
          {!billing.designations.length ? (
            <p className="py-4 text-center text-muted-foreground">Sin designaciones este mes</p>
          ) : (
            <>
              {billing.designations.map((d, i) => (
                <DesignationMobileCard
                  key={d.source_key ?? `${d.subject}-${d.group}-${d.semester}-${i}`}
                  designation={d}
                />
              ))}
              <Card
                render={<article />}
                data-testid="billing-mobile-totals"
                className="bg-muted/40 p-4"
              >
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Total</p>
                <dl className="mt-2 space-y-1.5 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">Horas</dt>
                    <dd className="text-right font-semibold tabular-nums text-foreground">{billing.total_hours}h</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">Bruto</dt>
                    <dd className="text-right font-semibold tabular-nums text-foreground">{formatBs(billing.gross_payment)}</dd>
                  </div>
                  {billing.retention_amount > 0 && (
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Retención</dt>
                      <dd className="text-right font-semibold tabular-nums text-destructive-foreground">- {formatBs(billing.retention_amount)}</dd>
                    </div>
                  )}
                  {hasAdjustments && (
                    <div className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">Ajuste</dt>
                      <dd className="text-right font-semibold tabular-nums text-warning-foreground">{formatAdjustment(billing.admin_adjustment)}</dd>
                    </div>
                  )}
                  <div className="flex justify-between gap-4 border-t pt-1.5">
                    <dt className="font-semibold text-muted-foreground">Neto</dt>
                    <dd className="text-right text-lg font-semibold tabular-nums text-foreground">{formatBs(displayPayment)}</dd>
                  </div>
                </dl>
              </Card>
            </>
          )}
        </div>
        <Card className="hidden sm:block gap-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-[760px] w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  {[
                    'Materia', 'Semestre', 'Grupo', 'Horas', 'Bruto', 'Retención',
                    ...(hasAdjustments ? ['Ajuste'] : []),
                    'Neto',
                  ].map((h) => (
                    <th
                      key={h}
                      className={cn(
                        'whitespace-nowrap px-4 py-3 text-xs font-medium uppercase tracking-wider text-muted-foreground',
                        NUMERIC_HEADINGS.has(h) ? 'text-right' : 'text-left',
                      )}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {!billing.designations.length ? (
                  <tr>
                    <td colSpan={hasAdjustments ? 8 : 7} className="py-8 text-center text-muted-foreground">
                      Sin designaciones este mes
                    </td>
                  </tr>
                ) : (
                  billing.designations.map((d, i) => (
                    <tr
                      key={d.source_key ?? `${d.subject}-${d.group}-${d.semester}-${i}`}
                      className="border-b transition-colors last:border-0 hover:bg-muted/40"
                    >
                      <td className="px-4 py-3 font-medium text-foreground">{d.subject}</td>
                      <td className="px-4 py-3 text-muted-foreground">{d.semester}</td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className="font-mono">
                          {d.group}
                        </Badge>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-foreground">{d.hours}h</td>
                      <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-foreground">{formatBs(d.gross_payment)}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-destructive-foreground">- {formatBs(d.retention_amount)}</td>
                      {hasAdjustments && (
                        <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-warning-foreground">
                          {d.has_admin_override
                            ? `${d.admin_adjustment >= 0 ? '+' : '-'} ${formatBs(Math.abs(d.admin_adjustment))}`
                            : '—'}
                        </td>
                      )}
                      <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-foreground">
                        {formatBs(d.net_payment)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
              {billing.designations.length > 0 && (
                <tfoot>
                  <tr className="border-t-2 bg-muted/40">
                    <td colSpan={3} className="whitespace-nowrap px-4 py-3 text-right font-semibold text-muted-foreground">
                      TOTAL
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-foreground">
                      {billing.total_hours}h
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-foreground">{formatBs(billing.gross_payment)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-destructive-foreground">- {formatBs(billing.retention_amount)}</td>
                    {hasAdjustments && (
                      <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-warning-foreground">
                        {`${billing.admin_adjustment >= 0 ? '+' : '-'} ${formatBs(Math.abs(billing.admin_adjustment))}`}
                      </td>
                    )}
                    <td className="whitespace-nowrap px-4 py-3 text-right text-lg font-semibold tabular-nums text-foreground">
                      {formatBs(displayPayment)}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </Card>
      </section>

      {/* Note if adjusted */}
      {billing.has_admin_override && (
        <Alert variant="warning">
          <AlertCircle aria-hidden="true" />
          <AlertTitle>Pago ajustado por administración</AlertTitle>
          <AlertDescription>
            El ajuste administrativo de {formatBs(billing.admin_adjustment)} deja un total a cobrar de {formatBs(billing.net_payment)}.
            Para más información contactá al área de planillas.
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

function BillingUnavailableNotice({ billing }: { billing: BillingUnavailableInfo }) {
  return (
    <Alert variant="info">
      <Receipt aria-hidden="true" />
      <AlertTitle>Facturación publicada sin detalle disponible</AlertTitle>
      <AlertDescription>{billing.unavailable_reason}</AlertDescription>
    </Alert>
  )
}

function BillingSkeleton() {
  return (
    <div role="status" aria-busy="true" className="space-y-4">
      <span className="sr-only">Cargando facturación</span>
      <Card className="space-y-4 p-4 sm:p-8">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-10 w-56 sm:h-14" />
        <Skeleton className="h-4 w-full max-w-sm" />
      </Card>
      <Skeleton className="h-36 w-full rounded-2xl" />
      <Skeleton className="h-48 w-full rounded-2xl" />
    </div>
  )
}

export function BillingPage() {
  const { data: combined, isLoading, error } = useCurrentBilling()

  const published = combined?.regular ?? combined?.practice ?? null
  const period = published ? `${published.month_name} ${published.year}` : null
  const header = (
    <PageHeader
      title={period ? `Pago — ${period}` : 'Mi pago'}
      description="Lo que te corresponde cobrar este mes y cómo se calcula."
    />
  )

  if (isLoading) {
    return (
      <div className="max-w-3xl">
        {header}
        <BillingSkeleton />
      </div>
    )
  }

  if (error) {
    const httpStatus = (error as { response?: { status?: number } })?.response?.status
    if (httpStatus === 404) {
      return (
        <div className="max-w-3xl">
          {header}
          <Card>
            <EmptyState
              icon={Clock}
              title="Facturación aún no publicada"
              description="El administrador aún no ha publicado los montos a facturar para este mes. Serás notificado cuando estén disponibles."
            />
          </Card>
        </div>
      )
    }
    if (httpStatus === 400) {
      return (
        <div className="max-w-3xl">
          {header}
          <Alert variant="error">
            <AlertCircle aria-hidden="true" />
            <AlertTitle>Tu cuenta no está vinculada a un docente</AlertTitle>
            <AlertDescription>
              Contactá al administrador para que vincule tu cuenta con tu registro de docente.
            </AlertDescription>
          </Alert>
        </div>
      )
    }
    return (
      <div className="max-w-3xl">
        {header}
        <Alert variant="error">
          <AlertCircle aria-hidden="true" />
          <AlertTitle>No hay información de facturación disponible</AlertTitle>
        </Alert>
      </div>
    )
  }

  if (!combined) return null

  const { regular, practice } = combined
  const hasBoth = Boolean(regular && practice)

  return (
    <div className="max-w-3xl">
      {header}
      <div className="space-y-5 sm:space-y-8">
        {regular && (
          <div>
            {hasBoth && (
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-widest text-muted-foreground">
                Teóricas
              </h3>
            )}
            {'data_status' in regular
              ? <BillingUnavailableNotice billing={regular} />
              : <BillingCard billing={regular} />}
          </div>
        )}

        {practice && (
          <div>
            {hasBoth && (
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-widest text-muted-foreground">
                Prácticas Internas
              </h3>
            )}
            {'data_status' in practice
              ? <BillingUnavailableNotice billing={practice} />
              : <BillingCard billing={practice} />}
          </div>
        )}
      </div>
    </div>
  )
}
