import { Outlet } from 'react-router-dom'
import { Header } from './Header'
import { AppSidebar } from './Sidebar'
import { SidebarProvider } from '@/components/ui/sidebar'

// The sidebar state is persisted by the coss sidebar in the `sidebar_state` cookie.
function readSidebarOpen(): boolean {
  const match = document.cookie.match(/(?:^|;\s*)sidebar_state=(true|false)/)
  return match ? match[1] === 'true' : true
}

export function Layout() {
  return (
    <SidebarProvider defaultOpen={readSidebarOpen()}>
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col bg-muted/40">
        <Header />
        <main className="min-w-0 overflow-x-clip p-3 sm:p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </SidebarProvider>
  )
}
