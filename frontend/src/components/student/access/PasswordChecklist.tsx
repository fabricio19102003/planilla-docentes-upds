import { Check } from 'lucide-react'

import type { PasswordRule } from './student-access'

/** Rules of the new password; each one ticks (pop + color) the moment it is satisfied. */
export function PasswordChecklist({ rules }: { rules: PasswordRule[] }) {
  const done = rules.filter((rule) => rule.passes).length
  return (
    <div className="sa-rules-wrap">
      <ul className="sa-rules" aria-label="Requisitos de la contraseña">
        {rules.map((rule) => (
          <li key={rule.label} className="sa-rule" data-ok={rule.passes}>
            <span aria-hidden="true" className="sa-rule-tick"><Check /></span>
            <span className="sa-rule-label">{rule.label}</span>
            <span className="sp-sr-only">{rule.passes ? ': cumplido' : ': pendiente'}</span>
          </li>
        ))}
      </ul>
      <p className="sp-sr-only" aria-live="polite">{done} de {rules.length} requisitos cumplidos</p>
    </div>
  )
}
