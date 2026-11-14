import { useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'
import { nextRovingIndex, notchPosition, pickActiveIndex } from './student-helpers'

export interface NotchTabItem {
  to: string
  label: string
  icon: LucideIcon
  /** Match only the exact path (use it for the home tab). */
  end?: boolean
}

interface NotchTabBarProps {
  items: NotchTabItem[]
  /** Accessible name of the navigation landmark. */
  label?: string
  /** Base font size in px; the whole bar scales with it (12-24). */
  size?: number
  /** Animation speed multiplier (0.5-2). */
  speed?: number
  /** Pin the bar to the bottom of the viewport (mobile navigation). */
  fixed?: boolean
  className?: string
}

/** R1 · Bottom tab bar with notch: the active tab rises into a bubble and the bar is cut beneath it. */
export function NotchTabBar({ items, label = 'Navegación', size = 16, speed = 1, fixed = true, className }: NotchTabBarProps) {
  const { pathname } = useLocation()
  const activeIndex = pickActiveIndex(items, pathname)
  const [roving, setRoving] = useState({ base: activeIndex, index: activeIndex })
  // The tab that holds the tab stop follows the route; arrow keys move it until the route changes.
  const tabbable = roving.base === activeIndex ? roving.index : Math.max(activeIndex, 0)
  const links = useRef<Array<HTMLAnchorElement | null>>([])

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    const current = links.current.findIndex((link) => link === document.activeElement)
    if (current === -1) return
    const next = nextRovingIndex(current, event.key, items.length)
    if (next === null) return
    event.preventDefault()
    links.current[next]?.focus()
  }

  const style = {
    '--s': `${size}px`,
    '--k': speed,
    '--sp-notch-count': items.length,
    '--sp-notch-x': `${notchPosition(activeIndex + 1, items.length)}%`,
  } as CSSProperties

  return (
    <div className={cn('sp-notch-dock', fixed && 'sp-notch-dock--fixed', className)}>
      <nav className="sp-notch" aria-label={label} data-active={activeIndex === -1 ? 'none' : undefined} style={style} onKeyDown={onKeyDown}>
        <div className="sp-notch-shade" aria-hidden="true">
          <div className="sp-notch-bar" />
        </div>
        <span className="sp-notch-bubble" aria-hidden="true" />
        {items.map(({ to, label: text, icon: Icon }, index) => {
          const active = index === activeIndex
          return (
            <Link
              key={to}
              ref={(node) => {
                links.current[index] = node
              }}
              to={to}
              className="sp-notch-link"
              aria-current={active ? 'page' : undefined}
              tabIndex={index === tabbable ? 0 : -1}
              onFocus={() => setRoving({ base: activeIndex, index })}
            >
              <span className="sp-notch-icon">
                <Icon aria-hidden="true" />
              </span>
              <span className="sp-notch-text">{text}</span>
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
