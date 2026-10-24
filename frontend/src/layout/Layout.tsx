import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import type { Role } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { DemoBanner } from '../components/DemoBanner'
import { Icon, LogoMark, type IconName } from '../components/Icon'
import { NotificationsBell } from '../components/NotificationsBell'
import { canCreateCase, canReadAudit, isClinical } from '../lib/permissions'

interface NavItem {
  to: string
  label: string
  icon: IconName
  end?: boolean
}

function navItems(role: Role, t: (k: string) => string): NavItem[] {
  const items: NavItem[] = []
  if (isClinical(role)) {
    items.push({ to: '/', label: t('nav.board'), icon: 'board', end: true })
    items.push({ to: '/tasks', label: t('nav.tasks'), icon: 'tasks' })
    if (role === 'doctor' || role === 'head_of_department')
      items.push({ to: '/round', label: t('nav.round'), icon: 'round' })
  }
  if (canCreateCase(role)) items.push({ to: '/case/new', label: t('nav.newCase'), icon: 'plus' })
  if (role === 'admin') {
    items.push({ to: '/admin/users', label: t('nav.users'), icon: 'users' })
    items.push({ to: '/admin/wards', label: t('nav.wards'), icon: 'bed' })
  }
  if (role === 'head_of_department' || role === 'head_nurse')
    items.push({ to: '/kpi', label: t('nav.kpi'), icon: 'chart' })
  if (canReadAudit(role)) items.push({ to: '/audit', label: t('nav.audit'), icon: 'file' })
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
      <div className="min-h-screen text-slate-900">
        <DemoBanner />
        <Outlet />
      </div>
    )
  }
  const items = navItems(user.role, t)
  const primary = items.slice(0, 4)
  const showTabs = !OWN_BOTTOM_BAR.some((re) => re.test(location.pathname))
  const linkTone = (isActive: boolean) =>
    `gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors ${isActive ? 'bg-white text-teal-900 shadow-sm' : 'text-teal-50 hover:bg-white/10'}`
  const desktopLink = ({ isActive }: { isActive: boolean }) =>
    `inline-flex shrink-0 items-center ${linkTone(isActive)}`
  const initials = user.full_name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0] ?? '')
    .join('')
    .toUpperCase()

  return (
    <div className={`min-h-screen text-slate-900 ${showTabs ? 'pb-20 md:pb-0' : ''}`}>
      <DemoBanner />
      <header className="sticky top-0 z-30 bg-gradient-to-r from-teal-950 via-teal-900 to-teal-800 shadow-md">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-2 px-3">
          <NavLink
            to={isClinical(user.role) ? '/' : '/admin/users'}
            className="mr-2 flex items-center gap-2 text-lg font-bold tracking-tight text-white"
          >
            <LogoMark size={30} />
            {t('app.name')}
          </NavLink>
          <nav
            className="hidden min-w-0 flex-1 gap-1 overflow-x-auto [scrollbar-width:none] md:flex"
            aria-label="Основная навигация"
          >
            {items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={desktopLink}>
                <Icon name={item.icon} size={18} className="hidden shrink-0 xl:block" />
                {item.label}
              </NavLink>
            ))}
          </nav>
          <span className="flex-1 md:hidden" />
          {isClinical(user.role) && <NotificationsBell />}
          <NavLink
            to="/profile"
            className={({ isActive }) =>
              `${linkTone(isActive)} hidden max-w-[14rem] shrink-0 items-center xl:flex`
            }
            title={t('nav.profile')}
          >
            <span
              aria-hidden
              className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white ring-2 ring-white/40"
            >
              {initials}
            </span>
            <span className="truncate">{user.full_name}</span>
          </NavLink>
          <button
            type="button"
            onClick={() => void logout()}
            className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-lg border border-white/30 bg-teal-900 px-3 text-sm text-white transition-colors hover:bg-teal-800"
          >
            <Icon name="logout" size={18} />
            <span className="hidden sm:inline">{t('common.logout')}</span>
            <span className="sr-only sm:hidden">{t('common.logout')}</span>
          </button>
        </div>
      </header>

      <Outlet />

      {showTabs && (
        <nav
          aria-label="Разделы"
          className="fixed inset-x-0 bottom-0 z-30 grid border-t border-slate-200 bg-white/95 px-1 pb-[env(safe-area-inset-bottom)] shadow-[0_-4px_16px_rgba(15,23,42,0.08)] backdrop-blur md:hidden"
          style={{ gridTemplateColumns: `repeat(${primary.length + 1}, minmax(0, 1fr))` }}
        >
          {primary.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `group flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px] font-medium ${isActive ? 'text-teal-900' : 'text-slate-600'}`
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`inline-flex h-7 w-12 items-center justify-center rounded-full transition-colors ${isActive ? 'bg-teal-100' : ''}`}
                  >
                    <Icon name={item.icon} size={20} />
                  </span>
                  <span className="max-w-full truncate px-1">{item.label}</span>
                </>
              )}
            </NavLink>
          ))}
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-expanded={menuOpen}
            className="flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px] font-medium text-slate-600"
          >
            <span className="inline-flex h-7 w-12 items-center justify-center">
              <Icon name="menu" size={20} />
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
          <div className="animate-fade-up w-full rounded-t-3xl bg-white p-3 pb-6 shadow-xl">
            <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-slate-300" aria-hidden />
            <div className="flex items-center gap-3 px-2 pb-3">
              <span
                aria-hidden
                className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-teal-700 text-sm font-bold text-white"
              >
                {initials}
              </span>
              <p className="min-w-0 text-sm">
                <span className="block truncate font-semibold">{user.full_name}</span>
                <span className="text-slate-600">{t(`roles.${user.role}`)}</span>
              </p>
            </div>
            <ul className="grid gap-1">
              {[
                ...items,
                { to: '/profile', label: t('nav.profile'), icon: 'user' } satisfies NavItem,
              ].map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    onClick={() => setMenuOpen(false)}
                    className={({ isActive }) =>
                      `flex min-h-12 items-center gap-3 rounded-xl px-3 text-base ${isActive ? 'bg-teal-50 font-semibold text-teal-900' : 'hover:bg-slate-100'}`
                    }
                  >
                    <Icon name={item.icon} size={20} className="text-teal-800" />
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() => setMenuOpen(false)}
              className="mt-2 min-h-12 w-full rounded-xl border border-slate-300 font-medium"
            >
              {t('common.close')}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
