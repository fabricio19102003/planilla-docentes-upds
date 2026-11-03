import { cn } from '@/lib/utils'

export function EmptyBoxIllustration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 120" fill="none" aria-hidden="true" className={cn('h-auto', className)}>
      <ellipse cx="80" cy="106" rx="48" ry="7" className="fill-muted" />
      <path d="M32 46 80 30l48 16v38l-48 18-48-18z" className="fill-primary/15 stroke-primary" strokeWidth="3" strokeLinejoin="round" />
      <path d="M32 46 80 62l48-16M80 62v40" className="stroke-primary" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
      <path d="M56 38l48 16v14" className="stroke-primary/50" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx="124" cy="24" r="5" className="fill-tone-violet/30" />
      <circle cx="30" cy="26" r="3.5" className="fill-tone-cyan/40" />
      <path d="M138 62v10M133 67h10" className="stroke-tone-violet" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
