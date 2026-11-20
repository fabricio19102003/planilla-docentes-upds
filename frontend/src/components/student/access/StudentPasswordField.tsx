import { Eye, EyeOff, Lock } from 'lucide-react'
import type { ReactNode } from 'react'

import { InfoTip } from '../InfoTip'
import { AccessInput } from './AccessInput'
import { eyeLabel } from './student-access'

interface StudentPasswordFieldProps {
  id: string
  value: string
  onChange: (value: string) => void
  placeholder: string
  visible: boolean
  onToggle: () => void
  /** The eye toggles several fields at once: "Mostrar contraseñas". */
  plural?: boolean
  disabled?: boolean
  invalid?: boolean
  autoComplete?: string
  icon?: ReactNode
}

/** Password field with a leading lock and an eye toggle that names its action in an InfoTip. */
export function StudentPasswordField({ id, value, onChange, placeholder, visible, onToggle, plural, disabled, invalid, autoComplete, icon }: StudentPasswordFieldProps) {
  const label = eyeLabel(visible, plural)
  return (
    <AccessInput
      id={id} value={value} onChange={onChange} placeholder={placeholder} type={visible ? 'text' : 'password'}
      disabled={disabled} invalid={invalid} autoComplete={autoComplete} icon={icon ?? <Lock />}
      trailing={(
        <InfoTip content={label} side="top">
          <button type="button" className="sa-eye" aria-label={label} aria-pressed={visible} onClick={onToggle}>
            {visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
          </button>
        </InfoTip>
      )}
    />
  )
}
