import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import type { Role } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { DemoBanner } from '../components/DemoBanner'
import { NotificationsBell } from '../components/NotificationsBell'
import { canCreateCase, canReadAudit, isClinical } from '../lib/permissions'

interface NavItem {
  to: string
  label: string
  icon: string
  end?: boolean
}

function navItems(role: Role, t: (k: string) => string): NavItem[] {
  const items: NavItem[] = []
  if (isClinical(role)) {
    items.push({ to: '/', label: t('nav.board'), icon: '▦', end: true })
    items.push({ to: '/tasks', label: t('nav.tasks'), icon: '☑' })
    if (role === 'doctor' || role === 'head_of_department')
      items.push({ to: '/round', label: t('nav.round'), icon: '⟳' })
  }
  if (canCreateCase(role)) items.push({ to: '/case/new', label: t('nav.newCase'), icon: '＋' })
  if (role === 'admin') {
    items.push({ to: '/admin/users', label: t('nav.users'), icon: '👤' })
    items.push({ to: '/admin/wards', label: t('nav.wards'), icon: '▤' })
  }
  if (role === 'head_of_department' || role === 'head_nurse')
    items.push({ to: '/kpi', label: t('nav.kpi'), icon: '📊' })
  if (canReadAudit(role)) items.push({ to: '/audit', label: t('nav.audit'), icon: '🗎' })
  return items
}

// Pages with their own fixed action bar at the bottom: no tab bar there.
const OWN_BOTTOM_BAR = [/\/intake$/, /\/postop$/]

export function Layout() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  if (!user) {
    return (
      <div className="min-h-screen bg-slate-50 text-slate-900">
        <DemoBanner />
        <Outlet />
      </div>
    )
  }
  const items = navItems(user.role, t)
  const primary = items.slice(0, 4)
  const showTabs = !OWN_BOTTOM_BAR.some((re) => re.test(location.pathname))
  const desktopLink = ({ isActive }: { isActive: boolean }) =>
    `whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium ${isActive ? 'bg-white/15 text-white' : 'text-teal-50 hover:bg-white/10'}`

  return (
    <div className={`min-h-screen bg-slate-50 text-slate-900 ${showTabs ? 'pb-20 md:pb-0' : ''}`}>
      <DemoBanner />
      <header className="sticky top-0 z-30 bg-teal-900 shadow">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-2 px-3">
          <NavLink
            to={isClinical(user.role) ? '/' : '/admin/users'}
            className="mr-2 text-lg font-bold text-white"
          >
            {t('app.name')}
          </NavLink>
          <nav className="hidden flex-1 gap-1 md:flex" aria-label="Основная навигация">
            {items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={desktopLink}>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <span className="flex-1 md:hidden" />
          {isClinical(user.role) && <NotificationsBell />}
          <NavLink
            to="/profile"
            className={(s) => `${desktopLink(s)} hidden max-w-[14rem] truncate lg:inline-block`}
            title={t('nav.profile')}
          >
            {user.full_name}
          </NavLink>
          <button
            type="button"
            onClick={() => void logout()}
            className="min-h-11 rounded-md border border-white/40 px-3 text-sm text-white hover:bg-white/10"
          >
            {t('common.logout')}
          </button>
        </div>
      </header>

      <Outlet />

      {showTabs && (
        <nav
          aria-label="Разделы"
          className="fixed inset-x-0 bottom-0 z-30 grid border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] shadow-[0_-2px_8px_rgba(0,0,0,0.06)] md:hidden"
          style={{ gridTemplateColumns: `repeat(${primary.length + 1}, minmax(0, 1fr))` }}
        >
          {primary.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px] font-medium ${isActive ? 'text-teal-800' : 'text-slate-600'}`
              }
            >
              <span aria-hidden className="text-lg leading-none">
                {item.icon}
              </span>
              <span className="truncate px-1">{item.label}</span>
            </NavLink>
          ))}
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-expanded={menuOpen}
            className="flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px] font-medium text-slate-600"
          >
            <span aria-hidden className="text-lg leading-none">
              ☰
            </span>
            {t('nav.more')}
          </button>
        </nav>
      )}

      {menuOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={t('nav.more')}
          className="fixed inset-0 z-40 flex items-end bg-black/40 md:hidden"
          onClick={(e) => e.target === e.currentTarget && setMenuOpen(false)}
        >
          <div className="w-full rounded-t-2xl bg-white p-3 pb-6 shadow-xl">
            <p className="px-2 pb-2 text-sm text-slate-600">
              {user.full_name} · {t(`roles.${user.role}`)}
            </p>
            <ul className="grid gap-1">
              {[...items, { to: '/profile', label: t('nav.profile'), icon: '⚙' }].map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    onClick={() => setMenuOpen(false)}
                    className="flex min-h-12 items-center gap-3 rounded-lg px-3 text-base hover:bg-slate-100"
                  >
                    <span aria-hidden className="w-6 text-center">
                      {item.icon}
                    </span>
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() => setMenuOpen(false)}
              className="mt-2 min-h-12 w-full rounded-lg border border-slate-300"
            >
              {t('common.close')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
