import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { Layout } from './components/layout/Layout'
import { ToastProvider } from './components/ui/toast'

// Pages — Admin
import { DashboardPage } from './pages/DashboardPage'
import { UploadPage } from './pages/UploadPage'
import { AttendancePage } from './pages/AttendancePage'
import { ObservationsPage } from './pages/ObservationsPage'
import { PlanillaPage } from './pages/PlanillaPage'
import { TeachersPage } from './pages/TeachersPage'
import { TeacherDetailPage } from './pages/TeacherDetailPage'
import { DesignationsPage } from './pages/DesignationsPage'
import { UsersPage } from './pages/UsersPage'
import { AdminRequestsPage } from './pages/AdminRequestsPage'
import { ReportsPage } from './pages/ReportsPage'
import { ActivityLogPage } from './pages/ActivityLogPage'
import { ContractsPage } from './pages/ContractsPage'
import { BackupPage } from './pages/BackupPage'
import { SettingsPage } from './pages/SettingsPage'
import { AttendanceAuditPage } from './pages/AttendanceAuditPage'
import { PracticeAttendancePage } from './pages/PracticeAttendancePage'
import { AcademicManagementPage } from './pages/AcademicManagementPage'
import { AcademicHistoryImportPage } from './pages/AcademicHistoryImportPage'
import { CurriculumPage } from './pages/CurriculumPage'
import { StudentDetailPage } from './pages/StudentDetailPage'
import { StudentsPage } from './pages/StudentsPage'
import { ReenrollmentPage } from './pages/ReenrollmentPage'
import { StudentChangePasswordPage } from './pages/student/StudentChangePasswordPage'
import { StudentHistoryPage } from './pages/student/StudentHistoryPage'
import { StudentHomePage } from './pages/student/StudentHomePage'
import { StudentLoginPage } from './pages/student/StudentLoginPage'
import { StudentPortalLayout } from './pages/student/StudentPortalLayout'
import { StudentReenrollmentPage } from './pages/student/StudentReenrollmentPage'
import { SchedulePlannerPage } from './pages/SchedulePlannerPage'
import { AdminChatPage } from './pages/AdminChatPage'

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
import { PortalChatPage } from './pages/PortalChatPage'

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
      <ToastProvider>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/change-password" element={<ForceChangePasswordPage />} />
          {/* Student portal: its own session (student_token), never the staff one. */}
          <Route path="/estudiante/login" element={<StudentLoginPage />} />
          <Route path="/estudiante/cambiar-clave" element={<StudentChangePasswordPage />} />
          <Route path="/estudiante" element={<StudentPortalLayout />}>
            <Route path="/estudiante" element={<StudentHomePage />} />
            <Route path="/estudiante/historial" element={<StudentHistoryPage />} />
            <Route path="/estudiante/rematricula" element={<StudentReenrollmentPage />} />
          </Route>

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
            <Route path="designations" element={<DesignationsPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="requests" element={<AdminRequestsPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="contracts" element={<ContractsPage />} />
            <Route path="activity" element={<ActivityLogPage />} />
            <Route path="backup" element={<BackupPage />} />
            <Route path="practice-attendance" element={<PracticeAttendancePage />} />
            <Route path="practice-planilla" element={<Navigate to="/planilla?tab=practicas" replace />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="academic-management" element={<AcademicManagementPage />} />
            <Route path="schedule-planner" element={<SchedulePlannerPage />} />
            <Route path="students" element={<StudentsPage />} />
            <Route path="students/:id" element={<StudentDetailPage />} />
            <Route path="reenrollment" element={<ReenrollmentPage />} />
            <Route path="curriculum" element={<CurriculumPage />} />
            <Route path="academic-history-import" element={<AcademicHistoryImportPage />} />
            <Route path="chat" element={<AdminChatPage />} />
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
            <Route path="chat" element={<PortalChatPage />} />
          </Route>
        </Routes>
      </ToastProvider>
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
