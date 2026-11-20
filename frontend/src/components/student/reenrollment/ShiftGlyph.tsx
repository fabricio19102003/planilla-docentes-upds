import { Moon, Sun, Sunset, type LucideIcon } from 'lucide-react'

import { shiftIconName, type ShiftIcon } from './reenrollment-view'

const ICONS: Record<ShiftIcon, LucideIcon> = { sun: Sun, sunset: Sunset, moon: Moon }

/** Sun, sunset or moon for the turno of a group (M / T / N). Decorative: the turno is always written next to it. */
export function ShiftGlyph({ shift, className }: { shift: string; className?: string }) {
  const Icon = ICONS[shiftIconName(shift)]
  return <Icon aria-hidden="true" className={className} />
}
