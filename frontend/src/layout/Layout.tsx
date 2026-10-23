import { useTranslation } from 'react-i18next'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { DemoBanner } from '../components/DemoBanner'
import { NotificationsBell } from '../components/NotificationsBell'
import { canCreateCase, canReadAudit, isClinical } from '../lib/permissions'

const link = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded px-3 py-2 text-sm font-medium ${
    isActive ? 'bg-teal-800 text-white' : 'text-teal-50 hover:bg-teal-700'
  }`

export function Layout() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <DemoBanner />
      {user && (
        <header className="bg-teal-900">
          <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-2 px-3 py-2">
            <span className="mr-auto text-lg font-bold text-white sm:mr-2">{t('app.name')}</span>
            <nav
              className="order-last flex w-full gap-1 overflow-x-auto sm:order-none sm:w-auto sm:flex-1"
              aria-label="Основная навигация"
            >
              {isClinical(user.role) && (
                <NavLink to="/" end className={link}>
                  {t('nav.board')}
                </NavLink>
              )}
              {isClinical(user.role) && (
                <>
                  <NavLink to="/tasks" className={link}>
                    {t('nav.tasks')}
                  </NavLink>
                  {(user.role === 'doctor' || user.role === 'head_of_department') && (
                    <NavLink to="/round" className={link}>
                      {t('nav.round')}
                    </NavLink>
                  )}
                </>
              )}
              {canCreateCase(user.role) && (
                <NavLink to="/case/new" className={link}>
                  {t('nav.newCase')}
                </NavLink>
              )}
              {user.role === 'admin' && (
                <>
                  <NavLink to="/admin/users" className={link}>
                    {t('nav.users')}
                  </NavLink>
                  <NavLink to="/admin/wards" className={link}>
                    {t('nav.wards')}
                  </NavLink>
                </>
              )}
              {canReadAudit(user.role) && (
                <NavLink to="/audit" className={link}>
                  {t('nav.audit')}
                </NavLink>
              )}
            </nav>
            {isClinical(user.role) && <NotificationsBell />}
            <NavLink
              to="/profile"
              className={(s) => `${link(s)} max-w-[9rem] truncate sm:max-w-none`}
            >
              {user.full_name} · {t(`roles.${user.role}`)}
            </NavLink>
            <button
              type="button"
              onClick={() => void logout()}
              className="min-h-11 rounded border border-teal-200 px-3 text-sm text-white hover:bg-teal-800"
            >
              {t('common.logout')}
            </button>
          </div>
        </header>
      )}
      <Outlet />
    </div>
  )
}
