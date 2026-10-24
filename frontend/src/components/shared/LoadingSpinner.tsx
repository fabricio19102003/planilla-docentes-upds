import { cn } from '@/lib/utils'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  label?: string
}

export function LoadingSpinner({ size = 'md', className = '', label = 'Cargando' }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'size-5 border-2',
    md: 'size-8 border-2',
    lg: 'size-12 border-[3px]',
  }

  return (
    <div
      role="status"
      className={cn(
        'animate-spin rounded-full border-muted border-t-primary motion-reduce:animate-none',
        sizeClasses[size],
        className,
      )}
    >
      <span className="sr-only">{label}</span>
    </div>
  )
}

export function LoadingPage() {
  return (
    <div className="flex items-center justify-center py-20">
      <LoadingSpinner size="lg" />
    </div>
  )
}
