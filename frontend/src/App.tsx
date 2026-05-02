import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import { SidebarProvider } from './context/SidebarContext'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { Layout } from './components/layout/Layout'

// Pages — Admin
import { DashboardPage } from './pages/DashboardPage'
import { UploadPage } from './pages/UploadPage'
import { AttendancePage } from './pages/AttendancePage'
import { ObservationsPage } from './pages/ObservationsPage'
import { PlanillaPage } from './pages/PlanillaPage'
import { TeachersPage } from './pages/TeachersPage'
import { TeacherDetailPage } from './pages/TeacherDetailPage'
import { UsersPage } from './pages/UsersPage'
import { AdminRequestsPage } from './pages/AdminRequestsPage'
import { ReportsPage } from './pages/ReportsPage'
import { ActivityLogPage } from './pages/ActivityLogPage'
import { ContractsPage } from './pages/ContractsPage'
import { BackupPage } from './pages/BackupPage'
import { SettingsPage } from './pages/SettingsPage'
import { AttendanceAuditPage } from './pages/AttendanceAuditPage'
import { PracticeAttendancePage } from './pages/PracticeAttendancePage'
import { PracticePlanillaPage } from './pages/PracticePlanillaPage'
import { CurriculumPage } from './pages/CurriculumPage'
import { PeriodsPage } from './pages/PeriodsPage'

// Pages — Auth
import { LoginPage } from './pages/LoginPage'
import { ForceChangePasswordPage } from './pages/ForceChangePasswordPage'

// Pages — Docente portal
import { BillingPage } from './pages/BillingPage'
import { BillingHistoryPage } from './pages/BillingHistoryPage'
import { MyRequestsPage } from './pages/MyRequestsPage'
import { MyProfilePage } from './pages/MyProfilePage'
import { NotificationsPage } from './pages/NotificationsPage'
import { SchedulePage } from './pages/SchedulePage'
import { RetentionLetterPage } from './pages/RetentionLetterPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
    },
  },
})

function AppRoutes() {
  return (
    <AuthProvider>
      <SidebarProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/change-password" element={<ForceChangePasswordPage />} />

          {/* Admin routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute requiredRole="admin">
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="upload" element={<UploadPage />} />
            <Route path="attendance" element={<AttendancePage />} />
            <Route path="attendance-audit" element={<AttendanceAuditPage />} />
            <Route path="observations" element={<ObservationsPage />} />
            <Route path="planilla" element={<PlanillaPage />} />
            <Route path="teachers" element={<TeachersPage />} />
            <Route path="teachers/:ci" element={<TeacherDetailPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="requests" element={<AdminRequestsPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="contracts" element={<ContractsPage />} />
            <Route path="activity" element={<ActivityLogPage />} />
            <Route path="backup" element={<BackupPage />} />
            <Route path="practice-attendance" element={<PracticeAttendancePage />} />
            <Route path="practice-planilla" element={<PracticePlanillaPage />} />
            <Route path="curriculum" element={<CurriculumPage />} />
            <Route path="periods" element={<PeriodsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>

          {/* Docente routes */}
          <Route
            path="/portal"
            element={
              <ProtectedRoute requiredRole="docente">
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<BillingPage />} />
            <Route path="history" element={<BillingHistoryPage />} />
            <Route path="requests" element={<MyRequestsPage />} />
            <Route path="profile" element={<MyProfilePage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="schedule" element={<SchedulePage />} />
            <Route path="retention-letter" element={<RetentionLetterPage />} />
          </Route>
        </Routes>
      </SidebarProvider>
    </AuthProvider>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
