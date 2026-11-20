import type { ReactNode } from 'react'

import { Input } from '@/components/ui/input'

interface AccessInputProps {
  id: string
  value: string
  onChange: (value: string) => void
  placeholder: string
  /** Lucide icon drawn inside the field, before the text. */
  icon: ReactNode
  type?: 'text' | 'password'
  disabled?: boolean
  invalid?: boolean
  autoComplete?: string
  /** Control placed at the end of the field (the eye toggle). */
  trailing?: ReactNode
}

/** 48px field of the student access pages: leading icon, 600-weight text and an optional trailing control. */
export function AccessInput({ id, value, onChange, placeholder, icon, type = 'text', disabled, invalid, autoComplete, trailing }: AccessInputProps) {
  return (
    <div className="sa-input">
      <span aria-hidden="true" className="sa-input-icon">{icon}</span>
      <Input
        id={id} type={type} value={value} placeholder={placeholder} disabled={disabled} aria-invalid={invalid}
        autoComplete={autoComplete} onChange={(event) => onChange(event.target.value)}
        className="rounded-2xl"
        inputClassName={trailing ? 'h-12 pl-12 pr-14 text-base font-semibold leading-[3rem] sm:h-12 sm:text-base sm:leading-[3rem]' : 'h-12 pl-12 text-base font-semibold leading-[3rem] sm:h-12 sm:text-base sm:leading-[3rem]'}
      />
      {trailing}
    </div>
  )
}
