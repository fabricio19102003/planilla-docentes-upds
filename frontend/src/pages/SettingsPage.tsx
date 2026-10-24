import { useEffect, useState } from 'react'
import { Save, Info, AlertCircle, CheckCircle2, ShieldCheck } from 'lucide-react'

import { Alert, AlertAction, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardPanel, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { PageHeader } from '@/components/shared/PageHeader'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { cn } from '@/lib/utils'
import { useAppSettings, useUpdateAppSettings } from '@/api/hooks/useAppSettings'
import { describeWhatsappReasons } from '@/lib/displayFormat'
import {
  buildSettingsPayload,
  MONEY_INPUT_MIN,
  MONEY_INPUT_STEP,
  toSettingsFormState,
  type SettingsFormState,
} from '@/lib/settingsForm'

function PermissionToggle({
  id,
  checked,
  title,
  description,
  onChange,
  disabled,
}: {
  id: string
  checked: boolean
  title: string
  description: string
  onChange: (checked: boolean) => void
  disabled: boolean
}) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-describedby={`${id}-description`}
      onClick={() => onChange(!checked)}
      disabled={disabled}
      className={cn(
        'group flex w-full items-start gap-3 rounded-xl border p-4 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60',
        checked ? 'border-primary/30 bg-primary/5' : 'bg-background hover:bg-accent/50',
      )}
    >
      <span
        className={cn(
          'mt-0.5 flex h-6 w-11 shrink-0 items-center rounded-full p-0.5 transition-colors',
          checked ? 'bg-primary' : 'bg-input',
        )}
        aria-hidden="true"
      >
        <span
          className={cn(
            'size-5 rounded-full bg-background shadow-sm transition-transform',
            checked ? 'translate-x-5' : 'translate-x-0',
          )}
        />
      </span>
      <span>
        <span className="block text-sm font-semibold text-foreground">{title}</span>
        <span id={`${id}-description`} className="mt-1 block text-xs leading-5 text-muted-foreground">{description}</span>
        <StatusBadge tone={checked ? 'success' : 'warning'} className="mt-2">
          {checked ? 'Habilitado para docentes' : 'Controlado por administración'}
        </StatusBadge>
      </span>
    </button>
  )
}

export function SettingsPage() {
  const { data: settings, isLoading, isError, error, refetch } = useAppSettings()
  const updateMutation = useUpdateAppSettings()

  const [form, setForm] = useState<SettingsFormState | null>(null)
  const [savedMessage, setSavedMessage] = useState<string | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)

  // Sync form state when server data arrives (initial load) or after a save.
  useEffect(() => {
    if (settings) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Settings form is intentionally hydrated from server data.
      setForm(toSettingsFormState(settings))
    }
  }, [settings])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSavedMessage(null)
    setValidationError(null)
    if (!form || !settings) return

    // Basic client-side validation — server also validates via pydantic.
    const rateStr = form.hourly_rate.trim()
    if (rateStr) {
      const rate = Number(rateStr)
      if (Number.isNaN(rate) || rate <= 0) {
        setValidationError('La tarifa por hora (teoría) debe ser un número mayor a 0.')
        return
      }
      if (rate > 10000) {
        setValidationError('La tarifa por hora (teoría) no puede ser mayor a 10.000 Bs.')
        return
      }
    }

    const practiceRateStr = form.practice_hourly_rate.trim()
    if (practiceRateStr) {
      const practiceRate = Number(practiceRateStr)
      if (Number.isNaN(practiceRate) || practiceRate <= 0) {
        setValidationError('La tarifa por hora (prácticas) debe ser un número mayor a 0.')
        return
      }
      if (practiceRate > 10000) {
        setValidationError('La tarifa por hora (prácticas) no puede ser mayor a 10.000 Bs.')
        return
      }
    }

    const hourLength = Number(form.academic_hour_minutes.trim())
    if (!Number.isInteger(hourLength) || hourLength < 5 || hourLength > 120) {
      setValidationError('La duración de la hora académica debe ser un número entero entre 5 y 120 minutos.')
      return
    }

    if (!form.active_academic_period.trim()) {
      setValidationError('El período académico no puede estar vacío.')
      return
    }
    if (!form.company_name.trim()) {
      setValidationError('El nombre de la empresa no puede estar vacío.')
      return
    }
    if (!form.company_nit.trim()) {
      setValidationError('El NIT de la empresa no puede estar vacío.')
      return
    }

    const payload = buildSettingsPayload(form, settings)
    if (Object.keys(payload).length === 0) {
      setValidationError('No hay cambios para guardar.')
      return
    }

    updateMutation.mutate(payload, {
      onSuccess: (data) => {
        setForm(toSettingsFormState(data))
        setSavedMessage('Configuración guardada correctamente.')
      },
    })
  }

  // ─── Render ────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      <PageHeader
        title="Configuración del Sistema"
        description="Valores de negocio usados en planillas, contratos y reportes"
      />

      {/* Info */}
      <Alert variant="info">
        <Info aria-hidden="true" />
        <AlertDescription>
          Estos valores se guardan en la base de datos y reemplazan la configuración
          anterior por variables de entorno. Los cambios se aplican inmediatamente
          a nuevas planillas, reportes y contratos generados desde el sistema.
        </AlertDescription>
      </Alert>

      {/* Form Card */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-base">Valores Editables</CardTitle>
          <CardDescription>Modificá solo los campos que necesités actualizar</CardDescription>
        </CardHeader>

        {isLoading ? (
          <CardPanel role="status" aria-live="polite" aria-label="Cargando configuración" className="space-y-5">
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              {Array.from({ length: 6 }, (_, i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-8 w-full" />
                </div>
              ))}
            </div>
          </CardPanel>
        ) : isError ? (
          <CardPanel>
            <Alert variant="error">
              <AlertCircle aria-hidden="true" />
              <AlertDescription>
                No se pudo cargar la configuración.
                {error instanceof Error ? ` (${error.message})` : ''}
              </AlertDescription>
              <AlertAction>
                <Button variant="outline" size="sm" onClick={() => void refetch()}>
                  Reintentar
                </Button>
              </AlertAction>
            </Alert>
          </CardPanel>
        ) : !form || !settings ? (
          <CardPanel role="status" aria-live="polite" aria-label="Cargando configuración">
            <Skeleton className="h-40 w-full" />
          </CardPanel>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6 p-6">
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              {/* Active Academic Period */}
              <Field>
                <FieldLabel htmlFor="active_academic_period">Período Académico Activo</FieldLabel>
                <Input
                  id="active_academic_period"
                  placeholder="I/2026"
                  value={form.active_academic_period}
                  onChange={(e) =>
                    setForm({ ...form, active_academic_period: e.target.value })
                  }
                  disabled={updateMutation.isPending}
                />
                <FieldDescription>
                  Ej: <span className="font-mono">I/2026</span>,{' '}
                  <span className="font-mono">II/2025</span>. Filtra las designaciones
                  activas.
                </FieldDescription>
              </Field>

              {/* Hourly Rate - Theory */}
              <Field>
                <FieldLabel htmlFor="hourly_rate">Tarifa por Hora — Teoría (Bs)</FieldLabel>
                <Input
                  id="hourly_rate"
                  type="number"
                  min={MONEY_INPUT_MIN}
                  max={10000}
                  step={MONEY_INPUT_STEP}
                  placeholder="70"
                  value={form.hourly_rate}
                  onChange={(e) => setForm({ ...form, hourly_rate: e.target.value })}
                  disabled={updateMutation.isPending}
                  inputClassName="tabular-nums"
                />
                <FieldDescription>Monto por hora académica para docentes de teoría.</FieldDescription>
              </Field>

              {/* Hourly Rate - Practice */}
              <Field>
                <FieldLabel htmlFor="practice_hourly_rate">Tarifa por Hora — Prácticas (Bs)</FieldLabel>
                <Input
                  id="practice_hourly_rate"
                  type="number"
                  min={MONEY_INPUT_MIN}
                  max={10000}
                  step={MONEY_INPUT_STEP}
                  placeholder="50"
                  value={form.practice_hourly_rate}
                  onChange={(e) => setForm({ ...form, practice_hourly_rate: e.target.value })}
                  disabled={updateMutation.isPending}
                  inputClassName="tabular-nums"
                />
                <FieldDescription>
                  Monto por hora académica para docentes asistenciales (prácticas internas).
                </FieldDescription>
              </Field>

              {/* Academic hour length */}
              <Field>
                <FieldLabel htmlFor="academic_hour_minutes">Duración de la hora académica (minutos)</FieldLabel>
                <Input
                  id="academic_hour_minutes"
                  type="number"
                  min={5}
                  max={120}
                  step={1}
                  placeholder="45"
                  value={form.academic_hour_minutes}
                  onChange={(e) => setForm({ ...form, academic_hour_minutes: e.target.value })}
                  disabled={updateMutation.isPending}
                  inputClassName="tabular-nums"
                />
                <FieldDescription>
                  Se usa para precargar las horas académicas de cada bloque nuevo (duración ÷ este valor). Las horas de cada bloque se pueden corregir a mano; los bloques existentes no cambian.
                </FieldDescription>
              </Field>

              {/* Company Name */}
              <Field>
                <FieldLabel htmlFor="company_name">Nombre de Empresa</FieldLabel>
                <Input
                  id="company_name"
                  placeholder="UNIPANDO S.R.L."
                  value={form.company_name}
                  onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                  disabled={updateMutation.isPending}
                />
                <FieldDescription>Se muestra en el encabezado de la planilla de salarios.</FieldDescription>
              </Field>

              {/* Company NIT */}
              <Field>
                <FieldLabel htmlFor="company_nit">NIT de Empresa</FieldLabel>
                <Input
                  id="company_nit"
                  placeholder="456850023"
                  value={form.company_nit}
                  onChange={(e) => setForm({ ...form, company_nit: e.target.value })}
                  disabled={updateMutation.isPending}
                />
                <FieldDescription>NIT de la empresa mostrado en la planilla de salarios.</FieldDescription>
              </Field>
            </div>

            <section aria-labelledby="settings-permissions-heading" className="border-t pt-6">
              <div className="mb-4 flex items-start gap-3">
                <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                  <ShieldCheck size={17} className="text-primary" aria-hidden="true" />
                </div>
                <div>
                  <h4 id="settings-permissions-heading" className="text-sm font-semibold text-foreground">Permisos de Mi Perfil docente</h4>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    Definí qué puede autogestionar un docente desde su portal. El backend mantiene el bloqueo aunque alguien intente llamar la API directamente.
                  </p>
                </div>
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                <PermissionToggle
                  id="docente-can-edit-profile"
                  checked={form.docente_can_edit_profile}
                  title="Editar datos personales y bancarios"
                  description="Permite actualizar email, teléfono, datos académicos y cuenta bancaria desde Mi Perfil. Si está apagado, la ficha queda visible en modo lectura."
                  onChange={(checked) => setForm({ ...form, docente_can_edit_profile: checked })}
                  disabled={updateMutation.isPending}
                />
                <PermissionToggle
                  id="docente-can-edit-photo"
                  checked={form.docente_can_edit_photo}
                  title="Subir o eliminar foto propia"
                  description="Permite que el docente cambie su avatar institucional. Los administradores siempre pueden gestionar la foto desde el detalle del docente."
                  onChange={(checked) => setForm({ ...form, docente_can_edit_photo: checked })}
                  disabled={updateMutation.isPending}
                />
              </div>
            </section>

            <section aria-labelledby="settings-whatsapp-heading" className="border-t pt-6">
              <div className="mb-3">
                <h4 id="settings-whatsapp-heading" className="text-sm font-semibold text-foreground">Entrega de facturación por WhatsApp</h4>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Este control solo solicita envíos nuevos. La infraestructura, el worker y la aprobación del proveedor deben estar disponibles.
                </p>
              </div>
              <PermissionToggle
                id="whatsapp-billing-delivery"
                checked={form.whatsapp_billing_requested_enabled}
                title="Permitir nuevos envíos por WhatsApp oficial"
                description={
                  settings.whatsapp_billing_delivery.effective_enabled
                    ? 'Disponible para generar vistas previas y confirmar nuevos lotes.'
                    : settings.whatsapp_billing_delivery.blocking_reasons.length > 0
                      ? `No disponible: ${describeWhatsappReasons(settings.whatsapp_billing_delivery.blocking_reasons)}.`
                      : 'La entrega está desactivada por administración.'
                }
                onChange={(checked) => setForm({ ...form, whatsapp_billing_requested_enabled: checked })}
                disabled={
                  updateMutation.isPending
                  || (!settings.whatsapp_billing_delivery.can_enable && !form.whatsapp_billing_requested_enabled)
                }
              />
              <p className="mt-3 text-xs font-medium text-foreground" aria-live="polite">
                Estado efectivo: {settings.whatsapp_billing_delivery.effective_enabled ? 'disponible' : 'no disponible'}.
              </p>
            </section>

            {/* Validation error */}
            {validationError && (
              <Alert variant="warning" role="alert">
                <AlertCircle aria-hidden="true" />
                <AlertDescription>{validationError}</AlertDescription>
              </Alert>
            )}

            {/* Server error */}
            {updateMutation.isError && (
              <Alert variant="error" role="alert">
                <AlertCircle aria-hidden="true" />
                <AlertDescription>
                  No se pudo guardar la configuración.
                  {updateMutation.error instanceof Error
                    ? ` (${updateMutation.error.message})`
                    : ''}
                </AlertDescription>
              </Alert>
            )}

            {/* Success */}
            {savedMessage && !updateMutation.isError && (
              <Alert variant="success" role="status">
                <CheckCircle2 aria-hidden="true" />
                <AlertDescription>{savedMessage}</AlertDescription>
              </Alert>
            )}

            <div className="flex items-center gap-3 pt-2">
              <Button type="submit" loading={updateMutation.isPending}>
                {updateMutation.isPending ? (
                  'Guardando...'
                ) : (
                  <>
                    <Save aria-hidden="true" />
                    Guardar Cambios
                  </>
                )}
              </Button>
            </div>
          </form>
        )}
      </Card>
    </div>
  )
}
