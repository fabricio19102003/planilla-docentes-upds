import type { AppSettings, AppSettingsUpdate } from '@/api/types'

export type ComitenteKey =
  | 'contract_representative_name'
  | 'contract_representative_ci'
  | 'contract_power_number'
  | 'contract_power_date'
  | 'contract_notary_office'
  | 'contract_notary_name'
  | 'contract_city'

export type ComitenteForm = Record<ComitenteKey, string>

export const COMITENTE_FIELDS: { key: ComitenteKey; label: string; description: string; type?: 'date' }[] = [
  { key: 'contract_representative_name', label: 'Representante legal', description: 'Nombre completo de quien firma por el comitente.' },
  { key: 'contract_representative_ci', label: 'CI del representante', description: 'Número y departamento, por ejemplo "1750986 Pando".' },
  { key: 'contract_power_number', label: 'N.º de testimonio de poder', description: 'Por ejemplo "1818/2024".' },
  { key: 'contract_power_date', label: 'Fecha del poder', description: 'Fecha del testimonio de poder.', type: 'date' },
  { key: 'contract_notary_office', label: 'N.º de Notaría de Fe Pública', description: 'Solo el número, por ejemplo "10".' },
  { key: 'contract_notary_name', label: 'Notario', description: 'Nombre del notario a cargo.' },
  { key: 'contract_city', label: 'Ciudad de firma', description: 'Aparece antes de la fecha de firma: "Cobija, 10 de agosto de 2026."' },
]

export function toComitenteForm(settings: Pick<AppSettings, ComitenteKey>): ComitenteForm {
  return Object.fromEntries(
    COMITENTE_FIELDS.map(({ key }) => [key, settings[key]]),
  ) as ComitenteForm
}

export function validateComitenteForm(form: ComitenteForm): string | null {
  const blank = COMITENTE_FIELDS.find(({ key }) => !form[key].trim())
  return blank ? `El campo "${blank.label}" no puede estar vacío.` : null
}

/** Only trimmed fields that differ from the saved settings. */
export function buildComitentePayload(
  form: ComitenteForm,
  settings: Pick<AppSettings, ComitenteKey>,
): AppSettingsUpdate {
  const payload: AppSettingsUpdate = {}
  for (const { key } of COMITENTE_FIELDS) {
    const value = form[key].trim()
    if (value !== settings[key]) payload[key] = value
  }
  return payload
}
