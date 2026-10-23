import { expect, test } from '@playwright/test'
import { login } from './helpers'

test('login -> board -> change a checklist item, and a second user sees it within 10 s', async ({
  browser,
}) => {
  const nurseContext = await browser.newContext()
  const nurse = await nurseContext.newPage()
  await login(nurse, 'nurse1')

  // The board lists initials and beds only.
  await expect(nurse.getByRole('heading', { name: 'Готовность к операции' })).toBeVisible()
  const firstRow = nurse.locator('tbody tr').nth(1)
  await expect(firstRow).toBeVisible()
  expect(await nurse.locator('tbody').textContent()).not.toMatch(/Тестов |Образцов |Примеров |DEMO-/)

  // Find a row whose «Анализы» item is not done yet, and mark it done.
  const labs = nurse.getByRole('button', { name: /^HBsAg, anti-HCV, RW, ВИЧ, ОАК, группа крови и резус: (Не начато|В процессе)/ }).first()
  await labs.click()
  const dialog = nurse.getByRole('dialog')
  await dialog.getByRole('radio', { name: /Выполнено/ }).check()
  await dialog.getByLabel('Заметка').fill('взяли кровь')
  await dialog.getByRole('button', { name: 'Сохранить' }).click()
  await expect(dialog).toBeHidden()

  // A second user (head of department) sees the change without reloading.
  const headContext = await browser.newContext()
  const head = await headContext.newPage()
  await login(head, 'head1')
  await expect(head.getByRole('button', { name: /^HBsAg.*: Выполнено/ }).first()).toBeVisible()

  // ...and a later change by the nurse reaches the already-open board by polling.
  const before = await head.getByRole('button', { name: /^HBsAg.*: Выполнено/ }).count()
  await nurse.getByRole('button', { name: /^HBsAg, anti-HCV, RW, ВИЧ, ОАК, группа крови и резус: (Не начато|В процессе)/ }).first().click()
  await nurse.getByRole('dialog').getByRole('radio', { name: /Выполнено/ }).check()
  await nurse.getByRole('dialog').getByRole('button', { name: 'Сохранить' }).click()
  await expect
    .poll(async () => head.getByRole('button', { name: /^HBsAg.*: Выполнено/ }).count(), { timeout: 10_000 })
    .toBe(before + 1)

  await nurseContext.close()
  await headContext.close()
})

test('a nurse cannot change a doctor-owned item; roles see the right navigation', async ({ page }) => {
  await login(page, 'nurse1')
  await page.getByRole('button', { name: /^Осмотр и документы \(5\):/ }).first().click()
  await expect(page.getByText('Нет прав на изменение')).toBeVisible()
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Сохранить' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Закрыть' }).click()
  await expect(page.getByRole('link', { name: 'Новый пациент' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Пользователи' })).toHaveCount(0)
})

test('demo banner is visible on every page', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('alert')).toContainText('Демо-режим: не вводите реальные данные пациентов')
  await login(page, 'doctor1')
  await expect(page.getByRole('alert').first()).toContainText('Демо-режим')
})
