import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  icon: LucideIcon
  title: string
  value: string | number
  subtitle?: string
  color: string
}

export function StatCard({ icon: Icon, title, value, subtitle, color }: StatCardProps) {
  // Convert hex to rgba for light background
  const hexToRgba = (hex: string, alpha: number) => {
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    return `rgba(${r}, ${g}, ${b}, ${alpha})`
  }

  return (
    <div
      className="bg-white rounded-lg shadow-sm p-5 flex items-center gap-4 border-l-4"
      style={{ borderLeftColor: color }}
    >
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: hexToRgba(color, 0.12) }}
      >
        <Icon size={22} style={{ color }} />
      </div>
      <div className="min-w-0">
        <p className="text-gray-500 text-sm font-medium truncate">{title}</p>
        <p className="text-2xl font-bold text-gray-800 leading-tight">{value}</p>
        {subtitle && (
          <p className="text-gray-400 text-xs mt-0.5 truncate">{subtitle}</p>
        )}
      </div>
    </div>
  )
}
