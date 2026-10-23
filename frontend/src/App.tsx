import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import type { Role } from './api/types'
import { useAuth } from './auth/AuthContext'
import { Layout } from './layout/Layout'
import { isClinical } from './lib/permissions'
import { BoardPage } from './pages/BoardPage'
import { LoginPage } from './pages/LoginPage'
const AuditPage = lazy(() => import('./pages/AuditPage').then((m) => ({ default: m.AuditPage })))
const CasePage = lazy(() => import('./pages/CasePage').then((m) => ({ default: m.CasePage })))
const DocumentPage = lazy(() =>
  import('./pages/DocumentPage').then((m) => ({ default: m.DocumentPage })),
)
const DocumentsPage = lazy(() =>
  import('./pages/DocumentsPage').then((m) => ({ default: m.DocumentsPage })),
)
const IntakePage = lazy(() => import('./pages/IntakePage').then((m) => ({ default: m.IntakePage })))
const NewCasePage = lazy(() =>
  import('./pages/NewCasePage').then((m) => ({ default: m.NewCasePage })),
)
const PostOpPage = lazy(() => import('./pages/PostOpPage').then((m) => ({ default: m.PostOpPage })))
const ProfilePage = lazy(() =>
  import('./pages/ProfilePage').then((m) => ({ default: m.ProfilePage })),
)
const RoundPage = lazy(() => import('./pages/RoundPage').then((m) => ({ default: m.RoundPage })))
const TasksPage = lazy(() => import('./pages/TasksPage').then((m) => ({ default: m.TasksPage })))
const KpiPage = lazy(() => import('./pages/KpiPage').then((m) => ({ default: m.KpiPage })))
const LabelPage = lazy(() => import('./pages/LabelPage').then((m) => ({ default: m.LabelPage })))
const UsersPage = lazy(() =>
  import('./pages/admin/UsersPage').then((m) => ({ default: m.UsersPage })),
)
const WardsPage = lazy(() =>
  import('./pages/admin/WardsPage').then((m) => ({ default: m.WardsPage })),
)

function Guard({ children, allow }: { children: ReactNode; allow: (role: Role) => boolean }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return null
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  if (!allow(user.role)) return <Navigate to="/" replace />
  return <>{children}</>
}

function Home() {
  const { user } = useAuth()
  if (user?.role === 'admin') return <Navigate to="/admin/users" replace />
  return <BoardPage />
}

export function App() {
  return (
    <Suspense fallback={<p className="p-4">Загрузка…</p>}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <Guard allow={() => true}>
                <Home />
              </Guard>
            }
          />
          <Route
            path="/case/new"
            element={
              <Guard allow={(r) => r === 'doctor' || r === 'head_of_department'}>
                <NewCasePage />
              </Guard>
            }
          />
          <Route
            path="/case/:id"
            element={
              <Guard allow={isClinical}>
                <CasePage />
              </Guard>
            }
          />
          <Route
            path="/case/:id/intake"
            element={
              <Guard allow={isClinical}>
                <IntakePage />
              </Guard>
            }
          />
          <Route
            path="/case/:id/documents"
            element={
              <Guard allow={isClinical}>
                <DocumentsPage />
              </Guard>
            }
          />
          <Route
            path="/case/:id/documents/:templateId"
            element={
              <Guard allow={isClinical}>
                <DocumentPage />
              </Guard>
            }
          />
          <Route
            path="/case/:id/postop"
            element={
              <Guard allow={isClinical}>
                <PostOpPage />
              </Guard>
            }
          />
          <Route
            path="/case/:id/postop/:entryId/document"
            element={
              <Guard allow={isClinical}>
                <DocumentPage />
              </Guard>
            }
          />
          <Route
            path="/tasks"
            element={
              <Guard allow={isClinical}>
                <TasksPage />
              </Guard>
            }
          />
          <Route
            path="/round"
            element={
              <Guard allow={(r) => r === 'doctor' || r === 'head_of_department'}>
                <RoundPage />
              </Guard>
            }
          />
          <Route
            path="/profile"
            element={
              <Guard allow={() => true}>
                <ProfilePage />
              </Guard>
            }
          />
          <Route
            path="/admin/users"
            element={
              <Guard allow={(r) => r === 'admin'}>
                <UsersPage />
              </Guard>
            }
          />
          <Route
            path="/admin/wards"
            element={
              <Guard allow={(r) => r === 'admin'}>
                <WardsPage />
              </Guard>
            }
          />
          <Route
            path="/audit"
            element={
              <Guard allow={(r) => r === 'admin' || r === 'head_of_department'}>
                <AuditPage />
              </Guard>
            }
          />
          <Route
            path="/case/:id/label"
            element={
              <Guard allow={isClinical}>
                <LabelPage />
              </Guard>
            }
          />
          <Route
            path="/kpi"
            element={
              <Guard allow={(r) => r === 'head_of_department' || r === 'head_nurse'}>
                <KpiPage />
              </Guard>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
