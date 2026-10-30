import { useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, Save } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardPanel, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import type { AppSettings } from '@/api/types'
import { useUpdateAppSettings } from '@/api/hooks/useAppSettings'
import {
  buildComitentePayload,
  COMITENTE_FIELDS,
  toComitenteForm,
  validateComitenteForm,
  type ComitenteForm,
} from '@/lib/contractComitenteForm'

/** Comitente data written into every contract (representative, power of attorney, notary, city). */
export function ContractComitenteCard({ settings }: { settings: AppSettings }) {
  const updateMutation = useUpdateAppSettings()
  const [form, setForm] = useState<ComitenteForm>(() => toComitenteForm(settings))
  const [message, setMessage] = useState<{ tone: 'warning' | 'success'; text: string } | null>(null)

  useEffect(() => {
    setForm(toComitenteForm(settings))
  }, [settings])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    setMessage(null)
    const error = validateComitenteForm(form)
    if (error) {
      setMessage({ tone: 'warning', text: error })
      return
    }
    const payload = buildComitentePayload(form, settings)
    if (Object.keys(payload).length === 0) {
      setMessage({ tone: 'warning', text: 'No hay cambios para guardar.' })
      return
    }
    updateMutation.mutate(payload, {
      onSuccess: () => setMessage({
        tone: 'success',
        text: 'Datos del comitente guardados. Los contratos que emitas desde ahora los usarán.',
      }),
    })
  }

  return (
    <Card render={<section aria-labelledby="contract-comitente-heading" />}>
      <CardHeader className="border-b">
        <CardTitle id="contract-comitente-heading" className="text-base">Datos del Comitente en Contratos</CardTitle>
        <CardDescription>
          Representante legal, poder notarial y ciudad de firma de la cláusula PRIMERA. Al cambiarlos, cada
          docente recibe un contrato nuevo completo la próxima vez que lo emitas; los anteriores no se modifican.
        </CardDescription>
      </CardHeader>
      <CardPanel>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {COMITENTE_FIELDS.map((item) => (
              <Field key={item.key}>
                <FieldLabel htmlFor={item.key}>{item.label}</FieldLabel>
                <Input
                  id={item.key}
                  type={item.type ?? 'text'}
                  required
                  maxLength={200}
                  value={form[item.key]}
                  onChange={(e) => setForm({ ...form, [item.key]: e.target.value })}
                />
                <FieldDescription>{item.description}</FieldDescription>
              </Field>
            ))}
          </div>

          {message && (
            <Alert variant={message.tone} role={message.tone === 'warning' ? 'alert' : 'status'}>
              {message.tone === 'warning' ? <AlertCircle aria-hidden="true" /> : <CheckCircle2 aria-hidden="true" />}
              <AlertDescription>{message.text}</AlertDescription>
            </Alert>
          )}
          {updateMutation.isError && (
            <Alert variant="error" role="alert">
              <AlertCircle aria-hidden="true" />
              <AlertDescription>No se pudieron guardar los datos del comitente.</AlertDescription>
            </Alert>
          )}

          <Button type="submit" loading={updateMutation.isPending}>
            <Save aria-hidden="true" />
            Guardar datos del comitente
          </Button>
        </form>
      </CardPanel>
    </Card>
  )
}
