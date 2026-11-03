import { cn } from '@/lib/utils'

export function EmptySearchIllustration({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 120" fill="none" aria-hidden="true" className={cn('h-auto', className)}>
      <ellipse cx="80" cy="108" rx="46" ry="6" className="fill-muted" />
      <circle cx="68" cy="52" r="32" className="fill-primary/15 stroke-primary" strokeWidth="4" />
      <path d="M52 42a20 20 0 0 1 14-8" className="stroke-primary/50" strokeWidth="3" strokeLinecap="round" />
      <path d="M92 76l26 26" className="stroke-primary" strokeWidth="9" strokeLinecap="round" />
      <path d="M58 58q10-8 20 0" className="stroke-tone-violet" strokeWidth="3" strokeLinecap="round" />
      <circle cx="58" cy="46" r="2.5" className="fill-tone-violet" />
      <circle cx="78" cy="46" r="2.5" className="fill-tone-violet" />
      <circle cx="132" cy="30" r="4" className="fill-tone-cyan/40" />
      <circle cx="24" cy="90" r="3" className="fill-tone-violet/35" />
    </svg>
  )
}
