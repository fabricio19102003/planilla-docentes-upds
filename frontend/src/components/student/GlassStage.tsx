import type { CSSProperties, ReactNode } from 'react'

import { cn } from '@/lib/utils'
import { glassVars, type Wallpaper } from './student-helpers'

interface GlassStageProps {
  wallpaper?: Wallpaper
  /** Backdrop blur in px (4-40). */
  blur?: number
  /** Glass opacity in % (4-40). */
  opacity?: number
  /** Reflection strength in % (0-60). */
  shine?: number
  /** Give it a size (for example `h-56`): the wallpaper fills the stage. */
  className?: string
  children: ReactNode
}

/** R5/R6 · Animated gradient wallpaper on which `GlassCard` and `GlassSwitch` read as glass. */
export function GlassStage({ wallpaper = 'aurora', blur = 20, opacity = 12, shine = 25, className, children }: GlassStageProps) {
  return (
    <div
      className={cn('sp-glass-stage lg-font', wallpaper === 'light' && 'lg-light', className)}
      data-wallpaper={wallpaper}
      style={glassVars(wallpaper, blur, opacity, shine) as CSSProperties}
    >
      <div className="sp-glass-wall" aria-hidden="true">
        <div className="sp-glass-blobs">
          <div className="sp-glass-blob" />
          <div className="sp-glass-blob" />
          <div className="sp-glass-blob" />
        </div>
        <div className="sp-glass-grain" />
        <div className="sp-glass-scrim" />
      </div>
      <div className="sp-glass-fg">{children}</div>
    </div>
  )
}
