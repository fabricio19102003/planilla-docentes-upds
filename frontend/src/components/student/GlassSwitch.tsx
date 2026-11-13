import { useId, useRef, type KeyboardEvent } from 'react'
import type { LucideIcon } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'

import { cn } from '@/lib/utils'
import { GLASS_SPRING, nextRovingIndex, trackPointer } from './student-helpers'

export interface GlassSwitchOption<T extends string> {
  value: T
  label: string
  icon: LucideIcon
  /** Id of the panel this tab controls. */
  controls?: string
}

interface GlassSwitchProps<T extends string> {
  options: GlassSwitchOption<T>[]
  value: T
  onChange: (value: T) => void
  /** Accessible name of the tab list. */
  label: string
  /** Prefix of the tab ids (`<id>-<value>`), so panels can point back with aria-labelledby. */
  id?: string
  className?: string
}

// The pill stretches 15% while it slides to the next tab.
const STRETCH = { scaleX: [1, 1.15, 1] }

/** R6 · Glass tab bar used as a segmented switch: a sliding, stretching pill marks the selected view. Place it on a `GlassStage`. */
export function GlassSwitch<T extends string>({ options, value, onChange, label, id, className }: GlassSwitchProps<T>) {
  const reduceMotion = useReducedMotion()
  const generated = useId()
  const prefix = id ?? generated
  const tabs = useRef<Array<HTMLButtonElement | null>>([])

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    const current = tabs.current.findIndex((tab) => tab === document.activeElement)
    if (current === -1) return
    const next = nextRovingIndex(current, event.key, options.length)
    if (next === null) return
    event.preventDefault()
    tabs.current[next]?.focus()
    onChange(options[next].value)
  }

  return (
    <div
      className={cn('sp-glass-switch lg-glass', className)}
      role="tablist"
      aria-label={label}
      onMouseMove={trackPointer}
      onKeyDown={onKeyDown}
    >
      {options.map(({ value: optionValue, label: text, icon: Icon, controls }, index) => {
        const selected = optionValue === value
        return (
          <motion.button
            key={optionValue}
            ref={(node) => {
              tabs.current[index] = node
            }}
            id={`${prefix}-${optionValue}`}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={controls}
            tabIndex={selected ? 0 : -1}
            className="sp-glass-switch-tab lg-text"
            onClick={() => onChange(optionValue)}
            whileTap={reduceMotion ? undefined : { scale: 0.92 }}
            transition={GLASS_SPRING}
          >
            {selected && (
              // The key changes on every selection so the pill replays its stretch.
              <motion.span
                key={`pill-${optionValue}`}
                layoutId={`${prefix}-pill`}
                className="sp-glass-switch-pill"
                aria-hidden="true"
                initial={{ scaleX: 1 }}
                animate={reduceMotion ? { scaleX: 1 } : STRETCH}
                transition={
                  reduceMotion
                    ? { duration: 0 }
                    : { layout: GLASS_SPRING, scaleX: { duration: 0.45, ease: [0.25, 0.1, 0.25, 1] } }
                }
              />
            )}
            <Icon className="sp-glass-switch-icon" aria-hidden="true" />
            <span className="sp-glass-switch-label">{text}</span>
          </motion.button>
        )
      })}
    </div>
  )
}
