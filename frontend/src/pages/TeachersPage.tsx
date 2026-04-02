import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Users } from 'lucide-react'
import { useTeachers } from '@/api/hooks/useTeachers'
import { DataTable } from '@/components/shared/DataTable'
import { LoadingPage } from '@/components/shared/LoadingSpinner'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Teacher } from '@/api/types'
import type { Column } from '@/components/shared/DataTable'

export function TeachersPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { data, isLoading } = useTeachers({
    search: debouncedSearch || undefined,
    page,
    perPage: 15,
  })

  const totalPages = data ? Math.ceil(data.total / 15) : 1

  const handleSearchChange = (value: string) => {
    setSearch(value)
    setPage(1)
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    searchTimeout.current = setTimeout(() => {
      setDebouncedSearch(value)
    }, 300)
  }

  const columns: Column<Teacher>[] = [
    {
      key: 'full_name',
      header: 'Nombre Completo',
      render: (item) => (
        <span className="font-medium text-gray-800">{item.full_name}</span>
      ),
    },
    { key: 'ci', header: 'C.I.' },
    {
      key: 'email',
      header: 'Correo',
      render: (item) => item.email ?? '—',
    },
    {
      key: 'profession',
      header: 'Profesión',
      render: (item) => item.profession ?? '—',
    },
    {
      key: 'external_permanent',
      header: 'Tipo',
      render: (item) => {
        if (!item.external_permanent) return '—'
        return item.external_permanent === 'EXTERNO' ? 'Externo' : 'Permanente'
      },
    },
    {
      key: 'ci',
      header: 'Detalle',
      render: (item) => (
        <button
          onClick={() => navigate(`/teachers/${item.ci}`)}
          className="text-[#0066CC] hover:underline text-sm font-medium"
        >
          Ver más →
        </button>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      {/* Search */}
      <Card>
        <CardContent className="py-4">
          <div className="relative max-w-md">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar por nombre o C.I."
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-[#0066CC]"
            />
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle style={{ color: '#003366' }}>Listado de Docentes</CardTitle>
            {data && (
              <span className="text-sm text-gray-500">
                {data.total} docente{data.total !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <LoadingPage />
          ) : !data?.items.length ? (
            <div className="py-16 text-center">
              <Users size={40} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-400 font-medium">
                {debouncedSearch
                  ? `No se encontraron docentes para "${debouncedSearch}"`
                  : 'No hay docentes registrados aún'}
              </p>
            </div>
          ) : (
            <DataTable
              columns={columns}
              data={data.items}
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
              emptyMessage="No se encontraron docentes"
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
