import { useEffect, useState } from 'react'
import { Settings, Save, Loader2, Info, AlertCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAppSettings, useUpdateAppSettings } from '@/api/hooks/useAppSettings'
import type { AppSettings, AppSettingsUpdate } from '@/api/types'

interface FormState {
  active_academic_period: string
  company_name: string
  company_nit: string
  hourly_rate: string // keep as string to allow empty input; parsed on save
}

function toFormState(s: AppSettings): FormState {
  return {
    active_academic_period: s.active_academic_period,
    company_name: s.company_name,
    company_nit: s.company_nit,
    hourly_rate: String(s.hourly_rate),
  }
}

/**
 * Build the minimal update payload containing only fields that changed.
 * Returning an empty object means the user pressed Save with no edits.
 */
function buildPayload(form: FormState, server: AppSettings): AppSettingsUpdate {
  const payload: AppSettingsUpdate = {}

  const period = form.active_academic_period.trim()
  if (period && period !== server.active_academic_period) {
    payload.active_academic_period = period
  }

  const name = form.company_name.trim()
  if (name && name !== server.company_name) {
    payload.company_name = name
  }

  const nit = form.company_nit.trim()
  if (nit && nit !== server.company_nit) {
    payload.company_nit = nit
  }

  const rateStr = form.hourly_rate.trim()
  if (rateStr) {
    const rate = Number(rateStr)
    if (!Number.isNaN(rate) && rate !== server.hourly_rate) {
      payload.hourly_rate = rate
    }
  }

  return payload
}

export function SettingsPage() {
  const { data: settings, isLoading, isError, error } = useAppSettings()
  const updateMutation = useUpdateAppSettings()

  const [form, setForm] = useState<FormState | null>(null)
  const [savedMessage, setSavedMessage] = useState<string | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)

  // Sync form state when server data arrives (initial load) or after a save.
  useEffect(() => {
    if (settings) {
      setForm(toFormState(settings))
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
        setValidationError('La tarifa por hora debe ser un número mayor a 0.')
        return
      }
      if (rate > 10000) {
        setValidationError('La tarifa por hora no puede ser mayor a 10.000 Bs.')
        return
      }
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

    const payload = buildPayload(form, settings)
    if (Object.keys(payload).length === 0) {
      setValidationError('No hay cambios para guardar.')
      return
    }

    updateMutation.mutate(payload, {
      onSuccess: (data) => {
        setForm(toFormState(data))
        setSavedMessage('Configuración guardada correctamente.')
      },
    })
  }

  // ─── Render ────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <div
        className="card-3d-static overflow-hidden"
        style={{ borderTop: '4px solid #003366' }}
      >
        <div
          className="px-6 py-5"
          style={{
            backgroundImage:
              'linear-gradient(135deg, #003366 0%, #004d99 50%, #0066CC 100%)',
          }}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
              <Settings size={22} className="text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Configuración del Sistema</h2>
              <p className="text-sm text-blue-200 mt-0.5">
                Valores de negocio usados en planillas, contratos y reportes
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Info Card */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-5 py-4 flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0 mt-0.5">
            <Info size={16} className="text-blue-600" />
          </div>
          <p className="text-sm text-gray-600">
            Estos valores se guardan en la base de datos y reemplazan la configuración
            anterior por variables de entorno. Los cambios se aplican inmediatamente
            a nuevas planillas, reportes y contratos generados desde el sistema.
          </p>
        </div>
      </div>

      {/* Form Card */}
      <div className="card-3d-static overflow-hidden">
        <div className="px-6 py-5 border-b border-gray-100">
          <h3 className="text-base font-semibold" style={{ color: '#003366' }}>
            Valores Editables
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Modificá solo los campos que necesités actualizar
          </p>
        </div>

        {isLoading || !form ? (
          <div className="flex justify-center py-14">
            <Loader2 size={24} className="animate-spin text-[#003366]" />
          </div>
        ) : isError ? (
          <div className="px-6 py-8 text-sm text-red-700">
            <div className="flex items-start gap-2">
              <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
              <span>
                No se pudo cargar la configuración.
                {error instanceof Error ? ` (${error.message})` : ''}
              </span>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="px-6 py-5 space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Active Academic Period */}
              <div className="space-y-1.5">
                <Label htmlFor="active_academic_period">Período Académico Activo</Label>
                <Input
                  id="active_academic_period"
                  placeholder="I/2026"
                  value={form.active_academic_period}
                  onChange={(e) =>
                    setForm({ ...form, active_academic_period: e.target.value })
                  }
                  disabled={updateMutation.isPending}
                />
                <p className="text-xs text-gray-500">
                  Ej: <span className="font-mono">I/2026</span>,{' '}
                  <span className="font-mono">II/2025</span>. Filtra las designaciones
                  activas.
                </p>
              </div>

              {/* Hourly Rate */}
              <div className="space-y-1.5">
                <Label htmlFor="hourly_rate">Tarifa por Hora (Bs)</Label>
                <Input
                  id="hourly_rate"
                  type="number"
                  min={0.01}
                  max={10000}
                  step={0.5}
                  placeholder="70"
                  value={form.hourly_rate}
                  onChange={(e) => setForm({ ...form, hourly_rate: e.target.value })}
                  disabled={updateMutation.isPending}
                />
                <p className="text-xs text-gray-500">
                  Monto por hora académica usado en el cálculo de planillas.
                </p>
              </div>

              {/* Company Name */}
              <div className="space-y-1.5">
                <Label htmlFor="company_name">Nombre de Empresa</Label>
                <Input
                  id="company_name"
                  placeholder="UNIPANDO S.R.L."
                  value={form.company_name}
                  onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                  disabled={updateMutation.isPending}
                />
                <p className="text-xs text-gray-500">
                  Se muestra en el encabezado de la planilla de salarios.
                </p>
              </div>

              {/* Company NIT */}
              <div className="space-y-1.5">
                <Label htmlFor="company_nit">NIT de Empresa</Label>
                <Input
                  id="company_nit"
                  placeholder="456850023"
                  value={form.company_nit}
                  onChange={(e) => setForm({ ...form, company_nit: e.target.value })}
                  disabled={updateMutation.isPending}
                />
                <p className="text-xs text-gray-500">
                  NIT de la empresa mostrado en la planilla de salarios.
                </p>
              </div>
            </div>

            {/* Validation error */}
            {validationError && (
              <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-sm text-amber-800 flex items-start gap-2">
                <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
                <span>{validationError}</span>
              </div>
            )}

            {/* Server error */}
            {updateMutation.isError && (
              <div className="p-3 bg-red-50 rounded-lg border border-red-200 text-sm text-red-700 flex items-start gap-2">
                <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
                <span>
                  No se pudo guardar la configuración.
                  {updateMutation.error instanceof Error
                    ? ` (${updateMutation.error.message})`
                    : ''}
                </span>
              </div>
            )}

            {/* Success */}
            {savedMessage && !updateMutation.isError && (
              <div className="p-3 bg-green-50 rounded-lg border border-green-200 text-sm text-green-700 flex items-start gap-2">
                <span>✅</span>
                <span>{savedMessage}</span>
              </div>
            )}

            <div className="pt-2 flex items-center gap-3">
              <Button
                type="submit"
                disabled={updateMutation.isPending}
                className="gap-2"
                style={{ backgroundColor: '#003366' }}
              >
                {updateMutation.isPending ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Guardando...
                  </>
                ) : (
                  <>
                    <Save size={16} />
                    Guardar Cambios
                  </>
                )}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
