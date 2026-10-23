import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { login } from './helpers'

// WCAG 2.1 AA audit of every screen with axe-core (BUILD_PROMPT section 8).
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

async function audit(page: Page, name: string) {
  await page.waitForLoadState('networkidle')
  const result = await new AxeBuilder({ page }).withTags(TAGS).analyze()
  const summary = result.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes.slice(0, 3).map((n) => n.target.join(' ')),
  }))
  expect(summary, `${name}: ${JSON.stringify(summary, null, 1)}`).toEqual([])
}

async function api(page: Page, method: string, path: string, body?: unknown) {
  return page.evaluate(
    async ({ method, path, body }) => {
      const csrf = document.cookie.match(/csrf_token=([^;]+)/)?.[1] ?? ''
      const r = await fetch(`/api/v1${path}`, {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      return r.json()
    },
    { method, path, body },
  )
}

test('login page', async ({ page }) => {
  await page.goto('/login')
  await audit(page, 'login')
})

test('doctor screens', async ({ page }) => {
  await login(page, 'doctor1')
  await page.waitForSelector('tbody tr')
  await audit(page, 'board')

  const caseUrl = await page.locator('tbody a').first().getAttribute('href')
  await page.goto(caseUrl!)
  await page.getByRole('heading', { level: 1 }).waitFor()
  await audit(page, 'case page')
  await page.goto(`${caseUrl}/intake`)
  await page.getByTestId('sync-status').waitFor()
  await audit(page, 'intake form')
  await page.goto(`${caseUrl}/documents`)
  await page.getByRole('heading', { name: 'Документы ЭМК' }).waitFor()
  await audit(page, 'documents list')
  await page.goto(`${caseUrl}/label`)
  await page.getByTestId('label').waitFor()
  await audit(page, 'qr label')
  await page.goto('/case/new')
  await page.getByRole('heading', { name: 'Новый пациент' }).waitFor()
  await audit(page, 'new case')
  await page.goto('/tasks')
  await page.getByRole('heading', { name: 'Мои задачи' }).waitFor()
  await audit(page, 'tasks')
  await page.goto('/round')
  await page.getByRole('button', { name: 'Начать обход' }).click()
  await page.getByRole('heading', { level: 1 }).waitFor()
  await audit(page, 'round mode')
  await page.goto('/profile')
  await page.getByRole('heading', { name: 'Профиль' }).waitFor()
  await audit(page, 'profile')
})

test('post-op and copy-cell screens', async ({ page }) => {
  await login(page, 'head1')
  await page.waitForSelector('tbody tr')
  const row = page.locator('tbody tr', { hasText: 'Послеоперационный период' }).first()
  const href = (await row.locator('a').first().getAttribute('href'))!
  const id = href.split('/').pop()!
  const created = await api(page, 'POST', `/cases/${id}/postop`, {
    data: { vitals: { bp: '120/80', pulse: 70, rr: 16, spo2: 98, temp: 36.6 }, pain_vas: 2, wound: { dressing: 'сухая', discharge: 'нет' } },
  })
  await api(page, 'POST', `/cases/${id}/postop/${created.id}/document/generate`)
  await page.goto(`/case/${id}/postop`)
  await page.getByRole('heading', { name: 'Динамика' }).waitFor()
  await audit(page, 'post-op page')
  await page.goto(`/case/${id}/postop/${created.id}/document`)
  await page.locator('li[data-key="bp"]').waitFor()
  await audit(page, 'T6 document (locked draft)')
})

test('head, admin and nurse screens', async ({ page }) => {
  await login(page, 'head1')
  await page.goto('/kpi')
  await page.getByRole('heading', { name: 'Показатели отделения' }).waitFor()
  await audit(page, 'kpi')
  await page.goto('/audit')
  await page.getByRole('heading', { name: 'Журнал действий' }).waitFor()
  await audit(page, 'audit viewer')
  await page.getByRole('button', { name: 'Выйти' }).click()

  await login(page, 'admin1')
  await page.getByRole('heading', { name: 'Пользователи' }).first().waitFor()
  await audit(page, 'admin users')
  await page.goto('/admin/wards')
  await page.getByRole('heading', { name: 'Палаты и койки' }).waitFor()
  await audit(page, 'admin wards')
})

test('checklist editor dialog', async ({ page }) => {
  await login(page, 'nurse1')
  await page.waitForSelector('tbody tr')
  await page.getByRole('button', { name: /^HBsAg.*: / }).first().click()
  await page.getByRole('dialog').waitFor()
  await audit(page, 'checklist editor')
})

test('board floor-plan view', async ({ page }) => {
  await login(page, 'nurse1')
  await page.getByRole('radio', { name: 'План этажа' }).click()
  await page.locator('[data-room="Пал. 1001"]').waitFor()
  await audit(page, 'floor plan')
})
