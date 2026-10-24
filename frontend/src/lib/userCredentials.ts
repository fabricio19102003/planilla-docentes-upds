// Mirrors backend/app/schemas/auth.py password validators.
export const PASSWORD_RULES: { label: string; test: (value: string) => boolean }[] = [
  { label: 'Al menos 8 caracteres', test: (v) => v.length >= 8 },
  { label: 'Al menos una mayúscula', test: (v) => /[A-ZÁÉÍÓÚÑ]/.test(v) },
  { label: 'Al menos una minúscula', test: (v) => /[a-záéíóúñ]/.test(v) },
  { label: 'Al menos un número', test: (v) => /\d/.test(v) },
]

export function passwordIssues(value: string): string[] {
  return PASSWORD_RULES.filter((rule) => !rule.test(value)).map((rule) => rule.label)
}

type ValidationItem = { msg?: unknown }

// FastAPI returns `detail` as a string for HTTPException and as a list of
// validation items for 422 responses; both must render as plain text.
export function apiErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item: ValidationItem) => (typeof item?.msg === 'string' ? item.msg.replace(/^Value error, /, '') : ''))
      .filter(Boolean)
    if (messages.length) return messages.join(' · ')
  }
  return fallback
}
