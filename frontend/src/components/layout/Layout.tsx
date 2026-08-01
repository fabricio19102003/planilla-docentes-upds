import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useSidebar } from '@/context/SidebarContext'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'

export function Layout() {
  const { collapsed, mobileOpen, setMobileOpen } = useSidebar()

  useEffect(() => {
    const desktopQuery = window.matchMedia('(min-width: 768px)')
    const closeDrawerOnDesktop = (event: MediaQueryListEvent) => {
      if (event.matches) setMobileOpen(false)
    }

    desktopQuery.addEventListener('change', closeDrawerOnDesktop)
    return () => desktopQuery.removeEventListener('change', closeDrawerOnDesktop)
  }, [setMobileOpen])

  return (
    <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
      <div className="min-h-screen bg-gray-50">
        <div className="hidden md:block">
          <Sidebar />
        </div>
        <div
          className={`min-w-0 transition-[margin-left] duration-200 ease-in-out ${collapsed ? 'md:ml-[68px]' : 'md:ml-64'}`}
        >
          <Header />
          <main className="min-w-0 overflow-x-clip p-3 sm:p-4 md:p-6">
            <Outlet />
          </main>
        </div>
      </div>
      <SheetContent
        side="left"
        className="w-64 gap-0 border-0 bg-transparent p-0 text-white md:hidden"
      >
        <SheetTitle className="sr-only">Navegación principal</SheetTitle>
        <Sidebar mobile />
      </SheetContent>
    </Sheet>
  )
}
