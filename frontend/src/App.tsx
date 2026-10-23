import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import type { Role } from './api/types'
import { useAuth } from './auth/AuthContext'
import { Layout } from './layout/Layout'
import { isClinical } from './lib/permissions'
import { AuditPage } from './pages/AuditPage'
import { BoardPage } from './pages/BoardPage'
import { CasePage } from './pages/CasePage'
import { LoginPage } from './pages/LoginPage'
import { NewCasePage } from './pages/NewCasePage'
import { UsersPage } from './pages/admin/UsersPage'
import { WardsPage } from './pages/admin/WardsPage'

function Guard({ children, allow }: { children: ReactNode; allow: (role: Role) => boolean }) {
  const { user, loading } = useAuth()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
