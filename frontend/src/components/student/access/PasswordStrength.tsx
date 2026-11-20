import { Meter } from '../Meter'
import { passwordStrength } from './student-access'

/** Four-segment strength meter and its word; nothing until the student starts typing. */
export function PasswordStrength({ password }: { password: string }) {
  if (!password) return null
  const { score, label, tone } = passwordStrength(password)
  return (
    <div className="sa-strength">
      <Meter value={score} max={4} segments tone={tone} label="Seguridad de la contraseña" valueText={label} />
      <p className="sa-strength-label" data-tone={tone}>{label}</p>
    </div>
  )
}
