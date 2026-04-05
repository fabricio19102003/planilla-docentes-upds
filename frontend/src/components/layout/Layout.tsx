import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useSidebar } from '@/context/SidebarContext'

export function Layout() {
  const { collapsed } = useSidebar()
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <div className={`flex-1 ${collapsed ? 'ml-[68px]' : 'ml-64'}`} style={{ transition: 'margin-left 200ms ease-in-out' }}>
        <Header />
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
