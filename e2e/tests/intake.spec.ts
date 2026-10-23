import { expect, test, type Page } from '@playwright/test'
import { login } from './helpers'

test.use({ viewport: { width: 360, height: 740 }, hasTouch: true })

const first = (page: Page, name: string) => page.getByRole('textbox', { name, exact: true }).first()

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)
}

test('doctor completes a TKA intake on a 360 px screen, generates T1 and copies every field', async ({
  page,
  context,
}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await login(page, 'doctor1')

  // New synthetic patient (no bed: all demo beds are taken)
  await page.goto('/case/new')
  await page.getByLabel('ФИО').fill('Синтетов Тест Тестович')
  await page.getByLabel('Дата рождения').fill('1960-05-17')
  await page.getByLabel('№ истории болезни').fill('E2E-0001')
  await page.getByLabel('Тип операции').selectOption({ label: 'Тотальное эндопротезирование коленного сустава' })
  await page.getByLabel('Сторона').selectOption('left')
  await page.getByRole('button', { name: 'Создать случай' }).click()
  await expect(page).toHaveURL(/\/case\/[0-9a-f-]{36}$/)
  await noHorizontalScroll(page)

  await page.getByRole('link', { name: 'Форма приёма' }).click()
  await expect(page.getByRole('heading', { name: /1\. Идентификация и план/ })).toBeVisible()
  await expect(page.getByTestId('sync-status')).toHaveAttribute('data-state', 'saved')

  // Touch targets are at least 44 px
  for (const radio of await page.getByRole('radio', { name: 'Нет' }).all()) {
    const box = await radio.boundingBox()
    if (box) expect(box.height).toBeGreaterThanOrEqual(44)
  }

  // Sections 1-9: tap and type only what T1 requires
  await first(page, 'Госпитализирован по поводу заболевания (который раз)').fill('1')
  await page.getByRole('radiogroup', { name: 'Есть аллергия?' }).getByRole('radio', { name: 'Нет' }).click()
  await page.getByRole('checkbox', { name: 'Отрицает перенесённые операции и заболевания' }).check()
  await page.getByRole('checkbox', { name: 'Постоянно лекарственные препараты не принимает' }).check()
  await page.getByRole('button', { name: 'Всё в норме' }).click()
  await page.getByLabel('АД систолическое').first().fill('120')
  await page.getByLabel('АД диастолическое').first().fill('80')
  await first(page, 'Пульс, уд/мин').fill('70')
  await first(page, 'ЧДД, в/мин').fill('16')
  await first(page, 'SpO2, %').fill('98')
  await first(page, 'Температура, °C').fill('36,6')
  await first(page, 'Вес, кг').fill('80')
  await first(page, 'Рост, см').fill('175')

  // Section 12: nutrition (BMI answered automatically), section 15: diet
  for (const question of [
    'Потеря веса за последние 3 месяца',
    'Снижение приёма пищи за последнюю неделю',
    'Стрессовый фактор / тяжесть заболевания',
  ]) {
    await page.getByRole('radiogroup', { name: question }).getByRole('radio', { name: 'Нет' }).click()
  }
  await expect(page.getByText('определяется автоматически по весу и росту')).toBeVisible()
  await first(page, 'Диета').fill('Тестовая диета')

  // Caprini is live: 65 years (2) + BMI 26.1 (1) + planned arthroplasty from the template (5)
  await expect(page.getByTestId('sync-status').locator('xpath=..')).toContainText('Caprini: 8')
  await noHorizontalScroll(page)

  await page.getByRole('button', { name: 'Завершить приём' }).click()
  await expect(page.getByTestId('sync-status')).toHaveAttribute('data-state', 'saved')

  // T1: generate, then copy every field with Enter
  await page.getByRole('link', { name: 'Документы ЭМК' }).click()
  await page.getByRole('link', { name: 'Создать документ' }).first().click()
  await page.getByRole('button', { name: 'Создать документ' }).click()
  const rows = page.locator('ol > li[data-row]')
  await expect(rows).toHaveCount(65)

  // Single field: copy button + tick
  const bp = page.locator('li[data-key="bp"]')
  await expect(bp.getByTestId('value-bp')).toHaveText('120/80')
  await bp.getByRole('button', { name: 'Копировать' }).click()
  await expect(bp.getByLabel('скопировано')).toBeVisible()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('120/80')
  expect(await page.locator('li[data-key="temp"] [data-testid="value-temp"]').textContent()).toBe('36,6')

  // Enter copies the focused field and moves to the next
  await page.locator('li[data-key="pulse"]').focus()
  await page.keyboard.press('Enter')
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe('70')
  await expect(page.locator('li[data-key="hr"]')).toBeFocused()

  // Walk the whole list with Enter, in EMR order
  await rows.first().focus()
  for (let i = 0; i < 65; i++) await page.keyboard.press('Enter')
  const progress = page.getByText(/Скопировано полей:/)
  await expect(progress).toContainText(/(\d+) \/ \1/, { timeout: 15_000 })

  // Fallback: everything as one labelled text
  await page.getByRole('button', { name: 'Скопировать всё одним текстом' }).click()
  await expect(page.getByText('Текст скопирован')).toBeVisible()
  const all = await page.evaluate(() => navigator.clipboard.readText())
  expect(all).toContain('Артериальное давление, мм рт.ст.: 120/80')
  expect(all).toContain('Температура тела, °C: 36,6')
  expect(all.indexOf('Артериальное давление')).toBeLessThan(all.indexOf('Пульс'))
})

test('the intake form keeps working offline and syncs when the connection returns', async ({ page, context }) => {
  await login(page, 'doctor1')
  await page.goto('/')
  const link = page.locator('[data-case-row] a').first()
  await link.click()
  await page.getByRole('link', { name: 'Форма приёма' }).click()
  await expect(page.getByTestId('sync-status')).toHaveAttribute('data-state', 'saved')

  await context.setOffline(true)
  await page.getByRole('radiogroup', { name: 'Есть аллергия?' }).getByRole('radio', { name: 'Нет' }).click()
  await expect(page.getByTestId('sync-status')).toHaveAttribute('data-state', /offline|dirty/)
  await page.getByRole('button', { name: 'Сохранить' }).click()
  await expect(page.getByTestId('sync-status')).toHaveAttribute('data-state', 'offline')

  await context.setOffline(false)
  await expect(page.getByTestId('sync-status')).toHaveAttribute('data-state', 'saved', { timeout: 20_000 })
  await page.reload()
  await expect(
    page.getByRole('radiogroup', { name: 'Есть аллергия?' }).getByRole('radio', { name: 'Нет' }),
  ).toHaveAttribute('aria-checked', 'true')
})
