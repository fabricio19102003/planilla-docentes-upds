import { useLocation } from 'react-router-dom'

const routeTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/upload': 'Subir Archivos',
  '/attendance': 'Asistencia',
  '/observations': 'Observaciones',
  '/planilla': 'Planilla',
  '/teachers': 'Docentes',
}

function getTitleFromPath(pathname: string): string {
  // Exact match first
  if (routeTitles[pathname]) return routeTitles[pathname]

  // Teacher detail page
  if (pathname.startsWith('/teachers/')) return 'Detalle de Docente'

  // Fallback: try prefix match
  const match = Object.keys(routeTitles)
    .filter((key) => key !== '/')
    .find((key) => pathname.startsWith(key))

  return match ? routeTitles[match] : 'UPDS Planilla'
}

export function Header() {
  const { pathname } = useLocation()
  const title = getTitleFromPath(pathname)

  return (
    <header className="bg-white shadow-sm border-b h-16 flex items-center justify-between px-6 sticky top-0 z-40">
      <h1 className="text-xl font-semibold" style={{ color: '#003366' }}>
        {title}
      </h1>
      <div className="flex items-center gap-3">
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold"
          style={{ backgroundColor: '#003366' }}
        >
          A
        </div>
        <span className="text-sm text-gray-600 font-medium">Admin</span>
      </div>
    </header>
  )
}
