import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  icon: LucideIcon
  title: string
  value: string | number
  subtitle?: string
  color: string
  gradient?: string
}

const GRADIENT_MAP: Record<string, string> = {
  '#003366': 'gradient-stat-navy',
  '#0066CC': 'gradient-stat-blue',
  '#4DA8DA': 'gradient-stat-blue',
  '#16a34a': 'gradient-stat-green',
  '#d97706': 'gradient-stat-yellow',
  '#dc2626': 'gradient-stat-red',
  '#ea580c': 'gradient-stat-orange',
  '#1d4ed8': 'gradient-stat-blue',    // Admin blue
  '#15803d': 'gradient-stat-green',   // Docente green
}

export function StatCard({ icon: Icon, title, value, subtitle, color, gradient }: StatCardProps) {
  const gradientClass = gradient ?? GRADIENT_MAP[color] ?? 'gradient-stat-blue'

  return (
    <div className="card-3d p-5 flex items-center gap-4 group">
      <div
        className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${gradientClass} shadow-lg group-hover:scale-110 transition-transform duration-300`}
      >
        <Icon size={22} className="text-white" />
      </div>
      <div className="min-w-0">
        <p className="text-gray-500 text-sm font-medium truncate">{title}</p>
        <p className="text-2xl font-bold text-gray-800 leading-tight animate-count-up">{value}</p>
        {subtitle && (
          <p className="text-gray-400 text-xs mt-0.5 truncate">{subtitle}</p>
        )}
      </div>
    </div>
  )
}
