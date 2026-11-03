import { cn } from '@/lib/utils'

export function EmptyCalendarIllustration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 120" fill="none" aria-hidden="true" className={cn('h-auto', className)}>
      <ellipse cx="80" cy="108" rx="46" ry="6" className="fill-muted" />
      <rect x="28" y="22" width="104" height="82" rx="10" className="fill-card stroke-primary" strokeWidth="3" />
      <path d="M28 40a10 10 0 0 1 10-10h84a10 10 0 0 1 10 10v10H28z" className="fill-primary/20 stroke-primary" strokeWidth="3" strokeLinejoin="round" />
      <path d="M52 14v16M108 14v16" className="stroke-primary" strokeWidth="4" strokeLinecap="round" />
      <circle cx="54" cy="68" r="5" className="fill-muted" />
      <circle cx="80" cy="68" r="5" className="fill-muted" />
      <circle cx="106" cy="68" r="5" className="fill-muted" />
      <circle cx="54" cy="88" r="5" className="fill-muted" />
      <circle cx="80" cy="88" r="5" className="fill-tone-violet/40 stroke-tone-violet" strokeWidth="2.5" strokeDasharray="4 3" />
      <circle cx="140" cy="28" r="4" className="fill-tone-cyan/40" />
    </svg>
  )
}
