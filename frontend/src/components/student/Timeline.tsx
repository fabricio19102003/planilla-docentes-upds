import { ChevronDown, type LucideIcon } from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useId, useState, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface TimelineProps {
  className?: string
  children: ReactNode
}

/** Vertical timeline: a violet spine with one dot per item. Use TimelineItem children. */
export function Timeline({ className, children }: TimelineProps) {
  return <ol className={cn('sp-tl', className)}>{children}</ol>
}

interface TimelineItemProps {
  /** Heading block of the row (period name, subtitle). */
  title: ReactNode
  /** Right side of the row: a figure, a badge. */
  meta?: ReactNode
  tone?: 'default' | 'ok' | 'warn' | 'bad'
  /** Icon inside the dot instead of the plain bullet. */
  icon?: LucideIcon
  /** Content revealed by the row button; without it the row is static. */
  children?: ReactNode
  defaultOpen?: boolean
  /** Accessible name of the toggle when `title` is not plain text. */
  toggleLabel?: string
  className?: string
}

/** One timeline row. With children it is a button (aria-expanded / aria-controls) that collapses the content. */
export function TimelineItem({ title, meta, tone = 'default', icon: Icon, children, defaultOpen = false, toggleLabel, className }: TimelineItemProps) {
  const reduceMotion = useReducedMotion()
  const [open, setOpen] = useState(defaultOpen)
  const bodyId = useId()
  const collapsible = children != null
  const head = (
    <>
      <span className="grid min-w-0 flex-1 gap-0.5">{title}</span>
      {meta ? <span className="grid shrink-0 text-right">{meta}</span> : null}
      {collapsible ? (
        <span aria-hidden="true" className="sp-tl-chev">
          <ChevronDown />
        </span>
      ) : null}
    </>
  )

  return (
    <li className={cn('sp-tl-item', className)} data-tone={tone} data-open={collapsible ? open : undefined}>
      <span aria-hidden="true" className="sp-tl-dot">
        {Icon ? <Icon /> : null}
      </span>
      {collapsible ? (
        <button
          type="button"
          className="sp-tl-head"
          aria-expanded={open}
          aria-controls={bodyId}
          aria-label={toggleLabel}
          onClick={() => setOpen((current) => !current)}
        >
          {head}
        </button>
      ) : (
        <div className="sp-tl-head">{head}</div>
      )}
      {collapsible ? (
        <AnimatePresence initial={false}>
          {open ? (
            <motion.div
              key="body"
              id={bodyId}
              className="sp-tl-body"
              initial={{ height: reduceMotion ? 'auto' : 0, opacity: reduceMotion ? 1 : 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={reduceMotion ? { duration: 0 } : { duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="sp-tl-body-inner">{children}</div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      ) : null}
    </li>
  )
}
