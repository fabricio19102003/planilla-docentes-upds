interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  label?: string
}

export function LoadingSpinner({ size = 'md', className = '', label = 'Cargando' }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-5 h-5 border-2',
    md: 'w-8 h-8 border-2',
    lg: 'w-12 h-12 border-3',
  }

  return (
    <div
      role="status"
      className={[
        'rounded-full animate-spin border-gray-200 motion-reduce:animate-none',
        sizeClasses[size],
        className,
      ].join(' ')}
      style={{ borderTopColor: '#0066CC' }}
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
