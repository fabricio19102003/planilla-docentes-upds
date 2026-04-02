import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from './components/layout/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { UploadPage } from './pages/UploadPage'
import { AttendancePage } from './pages/AttendancePage'
import { ObservationsPage } from './pages/ObservationsPage'
import { PlanillaPage } from './pages/PlanillaPage'
import { TeachersPage } from './pages/TeachersPage'
import { TeacherDetailPage } from './pages/TeacherDetailPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="upload" element={<UploadPage />} />
            <Route path="attendance" element={<AttendancePage />} />
            <Route path="observations" element={<ObservationsPage />} />
            <Route path="planilla" element={<PlanillaPage />} />
            <Route path="teachers" element={<TeachersPage />} />
            <Route path="teachers/:ci" element={<TeacherDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
