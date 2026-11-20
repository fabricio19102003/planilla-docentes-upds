import type { ReactNode } from 'react'

interface RmSectionProps {
  /** Big outlined step number. */
  step: number
  id: string
  title: string
  description?: string
  /** Renders a fieldset (radio group) instead of a section. */
  fieldset?: boolean
  disabled?: boolean
  children: ReactNode
}

/** Numbered section of the form: outlined display number + title, as in the artboard. */
export function RmSection({ step, id, title, description, fieldset = false, disabled, children }: RmSectionProps) {
  const head = (
    <div className="rm-sec-head">
      <span aria-hidden="true" className="rm-sec-num">{step}</span>
      <div>
        <h2 id={id} className="rm-sec-title">{title}</h2>
        {description && <p className="rm-sec-desc">{description}</p>}
      </div>
    </div>
  )
  if (fieldset) {
    return (
      <fieldset className="rm-sec" disabled={disabled} aria-labelledby={id}>
        {head}
        {children}
      </fieldset>
    )
  }
  return (
    <section className="rm-sec" aria-labelledby={id}>
      {head}
      {children}
    </section>
  )
}
