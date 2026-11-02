import { useState } from 'react'

import { useIntensiveSettings, useSaveIntensiveSettings } from '@/api/hooks/useIntensiveCourses'
import { ConfirmAlertDialog } from '@/components/shared/ConfirmAlertDialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  settingsFormFrom,
  settingsPayload,
  settingsProblem,
  type IntensiveSettings,
  type SettingsForm,
} from '@/lib/intensiveCoursesState'
import { formatBs } from '@/lib/reenrollmentState'
import { apiErrorMessage } from '@/lib/userCredentials'

const FIELDS: { field: keyof SettingsForm; label: string; hint: string; inputMode: 'decimal' | 'numeric' }[] = [
  { field: 'theory_hourly_rate', label: 'Tarifa por hora de teoría (Bs)', hint: 'Pago al docente por hora teórica.', inputMode: 'decimal' },
  { field: 'practice_hourly_rate', label: 'Tarifa por hora de práctica (Bs)', hint: 'Pago al docente por hora práctica.', inputMode: 'decimal' },
  { field: 'margin_factor', label: 'Factor de margen', hint: '1 o más. Con 1.10 el precio cubre el pago docente más un 10 %.', inputMode: 'decimal' },
  { field: 'min_price', label: 'Precio mínimo (Bs)', hint: 'Ningún estudiante paga menos.', inputMode: 'numeric' },
  { field: 'max_price', label: 'Precio máximo (Bs)', hint: 'Ningún estudiante paga más.', inputMode: 'numeric' },
]

function rate(value: number | null): string {
  return value === null ? 'Sin configurar' : formatBs(value)
}

function SettingsFormBody({ settings, onDone }: { settings: IntensiveSettings; onDone: () => void }) {
  const [form, setForm] = useState(() => settingsFormFrom(settings))
  const [confirming, setConfirming] = useState(false)
  const save = useSaveIntensiveSettings()
  const problem = settingsProblem(form)

  return (
    <form className="space-y-4 rounded-lg border p-4" onSubmit={(event) => { event.preventDefault(); if (!problem) setConfirming(true) }}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {FIELDS.map(({ field, label, hint, inputMode }) => (
          <div key={field}>
            <Label htmlFor={`intensive-${field}`}>{label}</Label>
            <Input id={`intensive-${field}`} inputMode={inputMode} value={form[field]}
              onChange={(event) => { save.reset(); setForm((current) => ({ ...current, [field]: event.target.value })) }} />
            <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
          </div>
        ))}
      </div>
      {problem && <p className="text-sm text-muted-foreground">{problem}</p>}
      {save.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(save.error, 'No se pudieron guardar los montos.')}</AlertTitle></Alert>}
      <div className="flex gap-2">
        <Button type="submit" disabled={problem !== null || save.isPending}>Guardar montos</Button>
        <Button type="button" variant="outline" onClick={onDone}>Cancelar</Button>
      </div>
      <ConfirmAlertDialog
        summary={confirming ? {
          title: 'Guardar montos de cursos intensivos', confirmLabel: 'Guardar',
          rows: [
            { label: 'Hora de teoría', value: formatBs(settingsPayload(form).theory_hourly_rate) },
            { label: 'Hora de práctica', value: formatBs(settingsPayload(form).practice_hourly_rate) },
            { label: 'Factor de margen', value: String(settingsPayload(form).margin_factor) },
            { label: 'Precio mínimo / máximo', value: `${formatBs(settingsPayload(form).min_price)} / ${formatBs(settingsPayload(form).max_price)}` },
          ],
          consequence: 'Cambia el precio estimado de los cursos abiertos. Los cursos con inscripción cerrada conservan su precio fijo.',
        } : null}
        pending={save.isPending}
        onConfirm={() => save.mutate(settingsPayload(form), { onSuccess: onDone, onSettled: () => setConfirming(false) })}
        onCancel={() => setConfirming(false)}
      />
    </form>
  )
}

/** Intensive amounts have their own settings, independent of the payroll rates. */
export function SettingsCard() {
  const settings = useIntensiveSettings()
  const [editing, setEditing] = useState(false)
  const data = settings.data

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div>
          <CardTitle className="text-base">Montos de cursos intensivos</CardTitle>
          <CardDescription>
            El precio por estudiante es el pago al docente (horas × tarifa) por el factor de margen, dividido entre los inscritos, entre el mínimo y el máximo. Son tarifas propias, independientes de la planilla. Es informativo: no se cobra en SIPAD.
          </CardDescription>
        </div>
        {data && !editing && <Button variant="outline" onClick={() => setEditing(true)}>{data.is_configured ? 'Cambiar montos' : 'Configurar montos'}</Button>}
      </CardHeader>
      <CardContent className="space-y-3">
        {settings.isError && <Alert variant="error" role="alert"><AlertTitle>{apiErrorMessage(settings.error, 'No se pudieron cargar los montos.')}</AlertTitle></Alert>}
        {!data && !settings.isError && <p role="status" className="text-sm text-muted-foreground">Cargando montos…</p>}
        {data && !data.is_configured && (
          <Alert variant="warning">
            <AlertTitle>Sin configurar</AlertTitle>
            <AlertDescription>Mientras no definas las tarifas por hora de teoría y de práctica no se puede abrir ningún curso intensivo.</AlertDescription>
          </Alert>
        )}
        {data && editing && <SettingsFormBody settings={data} onDone={() => setEditing(false)} />}
        {data && !editing && (
          <dl className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-5">
            <div><dt className="text-muted-foreground">Hora de teoría</dt><dd className="font-medium">{data.theory_hourly_rate === null ? <Badge variant="warning" size="sm">{rate(null)}</Badge> : rate(data.theory_hourly_rate)}</dd></div>
            <div><dt className="text-muted-foreground">Hora de práctica</dt><dd className="font-medium">{data.practice_hourly_rate === null ? <Badge variant="warning" size="sm">{rate(null)}</Badge> : rate(data.practice_hourly_rate)}</dd></div>
            <div><dt className="text-muted-foreground">Factor de margen</dt><dd className="font-medium">{data.margin_factor}</dd></div>
            <div><dt className="text-muted-foreground">Precio mínimo</dt><dd className="font-medium">{formatBs(data.min_price)}</dd></div>
            <div><dt className="text-muted-foreground">Precio máximo</dt><dd className="font-medium">{formatBs(data.max_price)}</dd></div>
          </dl>
        )}
      </CardContent>
    </Card>
  )
}
