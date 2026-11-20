// Pure helpers behind the student Login and Cambiar contraseña pages. No React, so they run under node --test.

export interface PasswordRule {
  label: string
  passes: boolean
}

export type StrengthTone = 'default' | 'bad' | 'warn' | 'ok'

/** The rules the portal has always asked for, in display order. */
export function passwordRules(next: string, confirm: string): PasswordRule[] {
  return [
    { label: 'Al menos 8 caracteres', passes: next.length >= 8 },
    { label: 'Una mayúscula', passes: /[A-Z]/.test(next) },
    { label: 'Una minúscula', passes: /[a-z]/.test(next) },
    { label: 'Un número', passes: /\d/.test(next) },
    { label: 'Las dos contraseñas coinciden', passes: next !== '' && next === confirm },
  ]
}

const STRENGTH: { label: string; tone: StrengthTone }[] = [
  { label: 'Débil', tone: 'bad' },
  { label: 'Regular', tone: 'warn' },
  { label: 'Buena', tone: 'warn' },
  { label: 'Fuerte', tone: 'ok' },
]

/** How many of the four character rules (length, upper, lower, digit) the password meets; empty reads as no score. */
export function passwordStrength(password: string): { score: number; label: string; tone: StrengthTone } {
  if (!password) return { score: 0, label: '', tone: 'default' }
  const score = [password.length >= 8, /[A-Z]/.test(password), /[a-z]/.test(password), /\d/.test(password)].filter(Boolean).length
  // A password that meets none of the rules is still "Débil".
  return { score, ...STRENGTH[Math.max(score, 1) - 1] }
}

/** Accessible name and tip of the eye button; `plural` when it toggles several fields at once. */
export function eyeLabel(visible: boolean, plural = false): string {
  return `${visible ? 'Ocultar' : 'Mostrar'} ${plural ? 'contraseñas' : 'contraseña'}`
}
