// Pure helpers behind the student portal redesign components (R1-R6). No React, so they run under node --test.

export const WALLPAPERS = ['aurora', 'sunset', 'ocean', 'light'] as const
export type Wallpaper = (typeof WALLPAPERS)[number]

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
const round = (value: number) => Number(value.toFixed(4))

/** Centre of tab `position` (1..N) as a percentage of the bar width: 10, 30, 50, 70, 90 for five tabs. */
export function notchPosition(position: number, count: number): number {
  return round((clamp(position, 1, Math.max(count, 1)) - 0.5) * (100 / Math.max(count, 1)))
}

/** Roving tabindex target for a key press: arrows wrap, Home/End jump, any other key returns null. */
export function nextRovingIndex(current: number, key: string, count: number): number | null {
  if (count <= 0) return null
  if (key === 'ArrowRight') return (current + 1) % count
  if (key === 'ArrowLeft') return (current - 1 + count) % count
  if (key === 'Home') return 0
  if (key === 'End') return count - 1
  return null
}

const trimSlash = (path: string) => (path.length > 1 ? path.replace(/\/+$/, '') : path)

/** Same rule as react-router's `end`: exact match, or any sub-path when `end` is false. */
export function isActivePath(to: string, pathname: string, end: boolean): boolean {
  const target = trimSlash(to)
  const current = trimSlash(pathname)
  return current === target || (!end && current.startsWith(`${target}/`))
}

/** Index of the most specific tab matching `pathname`, or -1 when none matches. */
export function pickActiveIndex(items: ReadonlyArray<{ to: string; end?: boolean }>, pathname: string): number {
  let best = -1
  items.forEach((item, index) => {
    if (!isActivePath(item.to, pathname, item.end ?? false)) return
    if (best === -1 || trimSlash(item.to).length > trimSlash(items[best].to).length) best = index
  })
  return best
}

/** Custom properties read by `.lg-glass`: blur 4-40px, glass opacity 4-40%, shine 0-60%. The light wallpaper needs a denser glass. */
export function glassVars(wallpaper: Wallpaper, blur: number, opacity: number, shine: number) {
  const alpha = clamp(opacity, 4, 40) / 100
  return {
    '--lg-blur': `${clamp(blur, 4, 40)}px`,
    '--lg-a': wallpaper === 'light' ? round(Math.min(0.6, alpha + 0.23)) : round(alpha),
    '--lg-shine': round(clamp(shine, 0, 60) / 100),
  }
}

/** Card tilt for a pointer at (px, py) in 0..1 of the card: up to 8deg each way, flat at the centre. */
export function tiltAngles(px: number, py: number) {
  const x = clamp(px, 0, 1)
  const y = clamp(py, 0, 1)
  return { rotateX: 8 - 16 * y, rotateY: -8 + 16 * x }
}

/** Spring shared by the glass card tilt, the tap feedback and the sliding pill. */
export const GLASS_SPRING = { type: 'spring', stiffness: 400, damping: 30 } as const

/** Stores the pointer position inside `element` for the reflection of `.lg-glass::after` (--x / --y). */
export function trackPointer(event: { currentTarget: HTMLElement; clientX: number; clientY: number }) {
  const rect = event.currentTarget.getBoundingClientRect()
  event.currentTarget.style.setProperty('--x', `${event.clientX - rect.left}px`)
  event.currentTarget.style.setProperty('--y', `${event.clientY - rect.top}px`)
}
