import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface HomeCardProps {
  icon: LucideIcon
  title: string
  description?: ReactNode
  /** Shown next to the title (for example a status badge). */
  badge?: ReactNode
  /** Position in the grid: each card fades in a little after the previous one. */
  index?: number
  className?: string
  children?: ReactNode
}

/** Summary card of the student Inicio: icon chip, lift on hover, press feedback and a staggered fade-in. */
export function HomeCard({ icon: Icon, title, description, badge, index = 0, className, children }: HomeCardProps) {
  const reduceMotion = useReducedMotion()
  return (
    <motion.div
      className={cn('group min-w-0', className)}
      // Reduced motion lands on the same end state without moving.
      initial={reduceMotion ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.07, ease: [0.22, 1, 0.36, 1] }}
    >
      <Card interactive className="h-full active:scale-[0.985] motion-reduce:active:scale-100">
        <CardHeader>
          <CardTitle render={<h2 />} className="flex flex-wrap items-center gap-2.5 text-base">
            <span
              aria-hidden="true"
              className="grid size-9 shrink-0 place-items-center rounded-xl bg-student-accent-soft text-student-accent-text transition-transform duration-300 ease-out group-hover:-translate-y-0.5 group-hover:-rotate-6 motion-reduce:transition-none motion-reduce:group-hover:translate-y-0 motion-reduce:group-hover:rotate-0"
            >
              <Icon className="size-5" />
            </span>
            {title}
            {badge}
          </CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        {children && <CardContent className="space-y-3 text-sm">{children}</CardContent>}
      </Card>
    </motion.div>
  )
}
