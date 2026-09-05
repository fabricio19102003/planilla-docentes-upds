import type { AppSettings, AppSettingsUpdate } from '@/api/types'

export const MONEY_INPUT_MIN = 0.01
export const MONEY_INPUT_STEP = 0.01

export interface SettingsFormState {
  active_academic_period: string
  company_name: string
  company_nit: string
  hourly_rate: string
  practice_hourly_rate: string
  docente_can_edit_profile: boolean
  docente_can_edit_photo: boolean
}

export function toSettingsFormState(settings: AppSettings): SettingsFormState {
  return {
    active_academic_period: settings.active_academic_period,
    company_name: settings.company_name,
    company_nit: settings.company_nit,
    hourly_rate: String(settings.hourly_rate),
    practice_hourly_rate: String(settings.practice_hourly_rate),
    docente_can_edit_profile: settings.docente_can_edit_profile,
    docente_can_edit_photo: settings.docente_can_edit_photo,
  }
}

/** Build the minimal update payload containing only fields that changed. */
export function buildSettingsPayload(
  form: SettingsFormState,
  server: AppSettings,
): AppSettingsUpdate {
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

  const practiceRateStr = form.practice_hourly_rate.trim()
  if (practiceRateStr) {
    const practiceRate = Number(practiceRateStr)
    if (!Number.isNaN(practiceRate) && practiceRate !== server.practice_hourly_rate) {
      payload.practice_hourly_rate = practiceRate
    }
  }

  if (form.docente_can_edit_profile !== server.docente_can_edit_profile) {
    payload.docente_can_edit_profile = form.docente_can_edit_profile
  }

  if (form.docente_can_edit_photo !== server.docente_can_edit_photo) {
    payload.docente_can_edit_photo = form.docente_can_edit_photo
  }

  return payload
}
