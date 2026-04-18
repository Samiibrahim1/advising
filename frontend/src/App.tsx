import type { ReactElement } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'

import { AppFrame } from './components/AppFrame'
import { MajorProvider } from './lib/MajorContext'
import { useCurrentUser } from './lib/hooks'
import { LoginPage } from './pages/LoginPage'
import { HubPage } from './pages/HubPage'
import { AdminOverviewPage } from './pages/admin/AdminOverviewPage'
import { AuditLogPage } from './pages/admin/AuditLogPage'
import { BackupsPage } from './pages/admin/BackupsPage'
import { MajorsPage } from './pages/admin/MajorsPage'
import { TemplatesPage } from './pages/admin/TemplatesPage'
import { UsersPage } from './pages/admin/UsersPage'
import { DashboardPage } from './pages/adviser/DashboardPage'
import { AdviserSettingsPage } from './pages/adviser/AdviserSettingsPage'
import { InsightsPage } from './pages/adviser/InsightsPage'
import { WorkspacePage } from './pages/adviser/WorkspacePage'
import { UploadPage } from './pages/progress/UploadPage'
import { ConfigurePage } from './pages/progress/ConfigurePage'
import { ReportsPage } from './pages/progress/ReportsPage'
import { StudentProgressPage } from './pages/progress/StudentProgressPage'

function RequireRole({ role, children }: { role: 'admin' | 'adviser'; children: ReactElement }) {
  const currentUser = useCurrentUser()
  if (!currentUser.data) return <LoginPage />
  if (currentUser.data.role !== role) {
    return <Navigate to={currentUser.data.role === 'admin' ? '/admin' : '/hub'} replace />
  }
  return children
}

function AdminLayout() {
  const { data: user } = useCurrentUser()
  if (!user) return null
  return (
    <AppFrame
      title="Admin Control"
      subtitle="Users, majors, templates, backups, and audit log."
      user={user}
      items={[
        { to: '/admin', label: 'Overview' },
        { to: '/admin/users', label: 'Users' },
        { to: '/admin/majors', label: 'Majors' },
        { to: '/admin/templates', label: 'Templates' },
        { to: '/admin/backups', label: 'Backups' },
        { to: '/admin/audit', label: 'Audit Log' },
      ]}
    >
      <Outlet />
    </AppFrame>
  )
}

function AdviserLayout() {
  const { data: user } = useCurrentUser()
  if (!user) return null
  return (
    <MajorProvider>
      <AppFrame
        title="Adviser Workspace"
        subtitle="Dashboard, advising flows, and insight tooling for assigned majors."
        user={user}
        items={[
          { to: '/hub', label: 'Home' },
          { to: '/adviser', label: 'Dashboard' },
          { to: '/adviser/workspace', label: 'Workspace' },
          { to: '/adviser/insights', label: 'Insights' },
          { to: '/adviser/settings', label: 'Settings' },
        ]}
      >
        <Outlet />
      </AppFrame>
    </MajorProvider>
  )
}

function ProgressLayout() {
  const { data: user } = useCurrentUser()
  if (!user) return null
  return (
    <MajorProvider>
      <AppFrame
        title="Academic Progress"
        subtitle="Upload progress reports, configure courses, and track completion."
        user={user}
        items={[
          { to: '/hub', label: 'Home' },
          { to: '/progress/upload', label: 'Upload' },
          { to: '/progress/configure', label: 'Configure' },
          { to: '/progress/reports', label: 'Reports' },
          { to: '/progress/students', label: 'Students' },
        ]}
      >
        <Outlet />
      </AppFrame>
    </MajorProvider>
  )
}

export default function App() {
  const token = window.localStorage.getItem('advising_v2_token')
  const currentUser = useCurrentUser()

  if (!token) return <LoginPage />
  if (currentUser.isLoading) return <div className="loading-screen">Loading…</div>
  if (currentUser.isError || !currentUser.data) return <LoginPage />

  return (
    <Routes>
      <Route
        path="/"
        element={<Navigate to={currentUser.data.role === 'admin' ? '/admin' : '/hub'} replace />}
      />
      <Route path="/hub" element={<RequireRole role="adviser"><HubPage /></RequireRole>} />
      <Route path="/admin" element={<RequireRole role="admin"><AdminLayout /></RequireRole>}>
        <Route index element={<AdminOverviewPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="majors" element={<MajorsPage />} />
        <Route path="templates" element={<TemplatesPage />} />
        <Route path="backups" element={<BackupsPage />} />
        <Route path="audit" element={<AuditLogPage />} />
      </Route>
      <Route path="/adviser" element={<RequireRole role="adviser"><AdviserLayout /></RequireRole>}>
        <Route index element={<DashboardPage />} />
        <Route path="workspace" element={<WorkspacePage />} />
        <Route path="insights" element={<InsightsPage />} />
        <Route path="settings" element={<AdviserSettingsPage />} />
      </Route>
      <Route path="/progress" element={<RequireRole role="adviser"><ProgressLayout /></RequireRole>}>
        <Route index element={<Navigate to="/progress/reports" replace />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="configure" element={<ConfigurePage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="students" element={<StudentProgressPage />} />
      </Route>
    </Routes>
  )
}
