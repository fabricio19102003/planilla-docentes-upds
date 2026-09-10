import { useState, type FormEvent } from 'react'

import { useOptOutWhatsAppPreference, useSaveWhatsAppPreference, useWhatsAppPreference } from '@/api/hooks/useTeachers'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

function errorMessage(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail ?? 'No se pudo actualizar la preferencia de WhatsApp. Intentá nuevamente.'
}

export function WhatsAppConsentCard({ ci }: { ci: string }) {
  const preference = useWhatsAppPreference(ci)
  const savePreference = useSaveWhatsAppPreference()
  const optOut = useOptOutWhatsAppPreference()
  const [phoneE164, setPhoneE164] = useState('')
  const [consentEvidenceReference, setConsentEvidenceReference] = useState('')
  const [consentSource, setConsentSource] = useState<'written_record' | 'verbal_record' | 'other_documented'>('written_record')
  const [consentedAt, setConsentedAt] = useState('')
  const [optOutEvidenceReference, setOptOutEvidenceReference] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const busy = savePreference.isPending || optOut.isPending
  const current = preference.data
  const fieldError = error ? 'whatsapp-consent-error' : undefined

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setMessage('')
    setError('')
    try {
      await savePreference.mutateAsync({
        ci,
        data: {
          phone_e164: phoneE164,
          is_verified: true,
          consent_evidence_reference: consentEvidenceReference,
          consent_source: consentSource,
          consented_at: new Date(consentedAt).toISOString(),
        },
      })
      setPhoneE164('')
      setConsentEvidenceReference('')
      setConsentedAt('')
      savePreference.reset()
      setMessage('La preferencia de WhatsApp fue actualizada.')
    } catch (requestError) {
      setError(errorMessage(requestError))
    }
  }

  const registerOptOut = async () => {
    setMessage('')
    setError('')
    if (!window.confirm('¿Confirmás registrar la baja de WhatsApp para este docente?')) return
    try {
      await optOut.mutateAsync({ ci, data: { opt_out_evidence_reference: optOutEvidenceReference } })
      setOptOutEvidenceReference('')
      optOut.reset()
      setMessage('La baja de WhatsApp fue registrada.')
    } catch (requestError) {
      setError(errorMessage(requestError))
    }
  }

  return (
    <section aria-label="Preferencia de WhatsApp">
      <Card>
        <CardHeader>
          <CardTitle className="text-base" style={{ color: '#003366' }}>Preferencia de WhatsApp</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4" aria-busy={preference.isLoading || busy}>
          {preference.isLoading ? <p role="status">Cargando preferencia…</p> : preference.error ? (
            <p role="alert" aria-live="assertive" className="text-sm text-red-600">No se pudo cargar la preferencia de WhatsApp.</p>
          ) : (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Badge variant={current?.is_verified ? 'default' : 'secondary'}>{current?.is_verified ? 'Número verificado' : 'Número sin verificar'}</Badge>
              <Badge variant={current?.eligible ? 'default' : 'destructive'}>{current?.eligible ? 'Habilitado para envíos' : 'No habilitado para envíos'}</Badge>
              <Badge variant={current?.opted_out ? 'destructive' : 'secondary'}>{current?.opted_out ? 'Baja registrada' : 'Sin baja registrada'}</Badge>
              <span>{current?.phone_masked ?? 'Sin preferencia registrada'}</span>
              {current && <span>Revisión de consentimiento: {current.consent_revision}</span>}
              {current?.consent_source && <span>Fuente: {current.consent_source === 'written_record' ? 'Registro escrito' : current.consent_source === 'verbal_record' ? 'Registro verbal' : 'Otro documento'}</span>}
              {current?.consented_at && <span>Fecha de consentimiento: {new Date(current.consented_at).toLocaleString('es-BO')}</span>}
            </div>
          )}
          {message && <p role="status" aria-live="polite" className="text-sm text-green-700">{message}</p>}
          {error && <p role="alert" aria-live="assertive" className="text-sm text-red-600">{error}</p>}

          <form className="grid gap-3 md:grid-cols-2" onSubmit={(event) => void save(event)}>
            <div className="space-y-1">
              <Label htmlFor="whatsapp-phone">Número de WhatsApp en formato internacional</Label>
              <Input id="whatsapp-phone" value={phoneE164} onChange={(event) => setPhoneE164(event.target.value)} placeholder="+59170000000" required aria-invalid={Boolean(error)} aria-describedby={fieldError ? `whatsapp-phone-help ${fieldError}` : 'whatsapp-phone-help'} />
              <p id="whatsapp-phone-help" className="text-xs text-gray-500">Se guarda solo mediante el registro protegido; aquí se mostrará enmascarado.</p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="whatsapp-consent-evidence">Referencia de evidencia de consentimiento</Label>
              <Input id="whatsapp-consent-evidence" value={consentEvidenceReference} onChange={(event) => setConsentEvidenceReference(event.target.value)} required aria-invalid={Boolean(error)} aria-describedby={fieldError} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="whatsapp-consent-source">Fuente del consentimiento</Label>
              <select id="whatsapp-consent-source" value={consentSource} onChange={(event) => setConsentSource(event.target.value as typeof consentSource)} aria-invalid={Boolean(error)} aria-describedby={fieldError} className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm">
                <option value="written_record">Registro escrito</option>
                <option value="verbal_record">Registro verbal</option>
                <option value="other_documented">Otro documento</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="whatsapp-consented-at">Fecha y hora del consentimiento</Label>
              <Input id="whatsapp-consented-at" type="datetime-local" value={consentedAt} onChange={(event) => setConsentedAt(event.target.value)} required aria-invalid={Boolean(error)} aria-describedby={fieldError} />
            </div>
            {error && <p id="whatsapp-consent-error" className="sr-only">{error}</p>}
            <div className="md:col-span-2"><Button type="submit" disabled={busy}>{savePreference.isPending ? 'Guardando…' : 'Guardar consentimiento'}</Button></div>
          </form>

          {current?.exists && !current.opted_out && (
            <div className="border-t pt-4">
              <Label htmlFor="whatsapp-opt-out-evidence">Referencia de evidencia de baja</Label>
              <div className="mt-1 flex flex-wrap gap-2">
                <Input id="whatsapp-opt-out-evidence" value={optOutEvidenceReference} onChange={(event) => setOptOutEvidenceReference(event.target.value)} required aria-invalid={Boolean(error)} aria-describedby={fieldError} />
                <Button type="button" variant="outline" disabled={busy || !optOutEvidenceReference} onClick={() => void registerOptOut()}>{optOut.isPending ? 'Registrando…' : 'Registrar baja'}</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
