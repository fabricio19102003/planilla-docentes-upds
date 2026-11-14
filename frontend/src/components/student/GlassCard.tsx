import type { MouseEvent, ReactNode } from 'react'
import { motion, useMotionValue, useReducedMotion, useSpring } from 'motion/react'

import { cn } from '@/lib/utils'
import { GLASS_SPRING, tiltAngles, trackPointer } from './student-helpers'
import { useFinePointer } from './use-fine-pointer'

interface GlassCardProps {
  className?: string
  /** Set to false to keep the card flat even with a mouse. */
  tilt?: boolean
  children: ReactNode
}

/**
 * R5 · Glass card: frosted card that tilts up to 8deg towards the cursor while a reflection follows it.
 * Touch screens and reduced motion get a flat card with a static highlight.
 */
export function GlassCard({ className, tilt = true, children }: GlassCardProps) {
  const reduceMotion = useReducedMotion()
  const finePointer = useFinePointer()
  const tilting = tilt && finePointer && !reduceMotion
  const targetX = useMotionValue(0)
  const targetY = useMotionValue(0)
  const rotateX = useSpring(targetX, GLASS_SPRING)
  const rotateY = useSpring(targetY, GLASS_SPRING)

  const onMove = (event: MouseEvent<HTMLDivElement>) => {
    trackPointer(event)
    if (!tilting) return
    const rect = event.currentTarget.getBoundingClientRect()
    const angles = tiltAngles((event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height)
    targetX.set(angles.rotateX)
    targetY.set(angles.rotateY)
  }

  const onLeave = () => {
    targetX.set(0)
    targetY.set(0)
  }

  return (
    <div className="sp-glass-perspective" style={{ perspective: 1000 }}>
      <motion.div
        className={cn('sp-glass-card lg-glass lg-text', className)}
        onMouseMove={onMove}
        onMouseLeave={onLeave}
        style={tilting ? { rotateX, rotateY } : undefined}
      >
        {children}
      </motion.div>
    </div>
  )
}
