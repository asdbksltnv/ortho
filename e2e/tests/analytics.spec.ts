import { expect, test } from '@playwright/test'
import { login, PASSWORD } from './helpers'
import fs from 'node:fs'

test('KPI page: tiles, blocking items, overrides, aggregate-only CSV export', async ({ page }) => {
  await login(page, 'head1')
  await page.getByRole('link', { name: 'Показатели' }).click()
  await expect(page.getByRole('heading', { name: 'Показатели отделения' })).toBeVisible()
  await expect(page.getByText('Случаев за период')).toBeVisible()
  await expect(page.getByText('Медиана «поступление → готов»')).toBeVisible()
  await expect(page.getByRole('heading', { name: /Что чаще всего мешает готовности/ })).toBeVisible()
  await expect(page.locator('li', { hasText: 'Документы' }).first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Не были готовы накануне операции (к 18:00)' })).toBeVisible()

  const download = page.waitForEvent('download')
  await page.getByRole('link', { name: /Скачать CSV/ }).click()
  const file = await download
  expect(file.suggestedFilename()).toMatch(/^kpi_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}\.csv$/)
  const text = fs.readFileSync((await file.path())!, 'utf8')
  expect(text.split(/\r?\n/)[0]).toBe('metric,key,value')
  expect(text).toContain('cases_total')
  expect(text).not.toMatch(/Тестов|Образцов|Пал\.|DEMO-|И\. А\./)
})

test('the head nurse sees KPIs; doctors and nurses do not', async ({ page }) => {
  await login(page, 'headnurse1')
  await expect(page.getByRole('link', { name: 'Показатели' })).toBeVisible()
  await page.getByRole('button', { name: 'Выйти' }).click()
  await login(page, 'doctor1')
  await expect(page.getByRole('link', { name: 'Показатели' })).toHaveCount(0)
  await page.goto('/kpi')
  await expect(page).toHaveURL(/\/$/) // redirected away
})

test('QR label: initials, bed and a QR code, no name or record number; scanning needs a login', async ({ page, browser }) => {
  await login(page, 'doctor1')
  const href = (await page.locator('tbody a').first().getAttribute('href'))!
  await page.goto(`${href}/label`)
  const label = page.getByTestId('label')
  await expect(label.getByRole('img', { name: 'QR' })).toBeVisible()
  const text = (await label.textContent()) ?? ''
  expect(text).toMatch(/[А-Я]\. [А-Я]\./)
  expect(text).toMatch(/Пал\. \d+, к\. \d+/)
  expect(text).not.toMatch(/Тестов|Образцов|Примеров|Условный|Пробный|Макетов|DEMO-/)

  // what a scan does: open /case/<uuid> without a session -> login -> back to the case
  const anon = await browser.newContext()
  const phone = await anon.newPage()
  await phone.goto(href)
  await expect(phone).toHaveURL(/\/login\?next=/)
  await phone.getByLabel('Логин').fill('nurse1')
  await phone.getByLabel('Пароль').fill(PASSWORD)
  await phone.getByRole('button', { name: 'Войти' }).click()
  await expect(phone).toHaveURL(new RegExp(`${href}$`))
  await expect(phone.getByRole('heading', { level: 1 })).toBeVisible()
  await anon.close()
})

test('login redirect never leaves the site', async ({ page }) => {
  await page.goto('/login?next=//evil.example.com')
  await page.getByLabel('Логин').fill('nurse1')
  await page.getByLabel('Пароль').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти' }).click()
  await expect(page.getByRole('button', { name: 'Выйти' })).toBeVisible()
  expect(new URL(page.url()).hostname).toBe('127.0.0.1')
})

test('audit viewer filters by action and shows who did it', async ({ page }) => {
  await login(page, 'head1')
  await page.getByRole('link', { name: 'Журнал действий' }).click()
  await page.getByLabel('Действие').selectOption('login')
  await expect(page.locator('tbody tr').first()).toContainText('login')
  await expect(page.locator('tbody tr').first()).toContainText('Демо Заведующий')
})
