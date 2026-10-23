import { expect, test } from '@playwright/test'
import { login } from './helpers'

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })

// `last` keeps this file independent of other specs that use the first matching case.
async function openCase(page: import('@playwright/test').Page, status: string, notReady?: boolean) {
  await page.goto('/')
  const rows = page.locator('tbody tr', { hasText: status })
  const row = notReady === undefined ? rows.last() : rows.filter({ hasText: notReady ? 'Не готов' : 'Готов' }).last()
  await row.getByRole('link').first().click()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
}

test('post-op entry -> template note -> approve -> copy', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await login(page, 'head1')
  await openCase(page, 'Послеоперационный период')
  await page.getByRole('link', { name: 'Послеоперационные записи' }).click()

  // Daily bedside form
  await page.getByLabel('АД систолическое').fill('120')
  await page.getByLabel('АД диастолическое').fill('80')
  await page.getByRole('textbox', { name: 'Пульс, уд/мин', exact: true }).first().fill('74')
  await page.getByRole('textbox', { name: 'ЧДД, в/мин', exact: true }).first().fill('16')
  await page.getByRole('textbox', { name: 'SpO2, %', exact: true }).first().fill('98')
  await page.getByRole('textbox', { name: 'Температура, °C', exact: true }).first().fill('36,7')
  await page.getByRole('radiogroup', { name: 'Боль по ВАШ (0–10)' }).getByRole('radio', { name: '3', exact: true }).click()
  await page.getByRole('radiogroup', { name: 'Повязка' }).getByRole('radio', { name: 'сухая' }).click()
  await page.getByRole('button', { name: 'Сохранить запись' }).click()
  await expect(page.getByText('Запись сохранена')).toBeVisible()

  // The drafted note starts with the post-op day and is not checked yet
  const state = page.getByTestId('note-state')
  await expect(state).toContainText('Черновик')
  const general = page.locator('label', { hasText: 'Общее состояние' }).locator('textarea')
  await expect(general).toHaveValue(/^\d+-\S+ сутки после операции\./)

  // The document exists, but copying the draft fields is locked
  await page.getByRole('link', { name: 'Документ для ЭМК' }).click()
  await page.getByRole('button', { name: 'Создать документ' }).click()
  await expect(page.getByTestId('locked-general_condition')).toBeVisible()
  await expect(page.locator('li[data-key="general_condition"]').getByRole('button', { name: 'Копировать' })).toHaveCount(0)
  await page.goBack()

  // Doctor reviews (and edits) the draft and presses «Проверено»
  await page.locator('label', { hasText: 'Общее состояние' }).locator('textarea').fill('2-е сутки после операции. Жалоб нет, боль 3 по ВАШ.')
  await page.getByRole('button', { name: 'Проверено' }).click()
  await expect(state).toContainText('Проверено')

  // Now the field can be copied
  await page.getByRole('link', { name: 'Документ для ЭМК' }).click()
  const row = page.locator('li[data-key="general_condition"]')
  await expect(row.getByTestId('locked-general_condition')).toHaveCount(0)
  await row.getByRole('button', { name: 'Копировать' }).click()
  await expect(row.getByLabel('скопировано')).toBeVisible()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('2-е сутки после операции. Жалоб нет, боль 3 по ВАШ.')
  // No heart-rate field in T6
  await expect(page.locator('li[data-key="hr"]')).toHaveCount(0)
})

test('a not-ready case cannot be called to the OR; the head overrides with a reason; staff are notified', async ({
  browser,
}) => {
  const headContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const head = await headContext.newPage()
  await login(head, 'head1')
  await openCase(head, 'Одобрен к операции', true)
  await head.getByRole('button', { name: 'Вызвать в операционную' }).click()
  const dialog = head.getByRole('dialog')
  await expect(dialog).toContainText('Пациент не готов к операции')
  await expect(dialog.getByRole('button', { name: 'Подтвердить' })).toBeDisabled()
  await dialog.getByLabel('Причина').fill('Освободилась операционная')
  await dialog.getByRole('button', { name: 'Подтвердить' }).click()
  await expect(head.getByText('Текущий статус:').locator('xpath=..')).toContainText('Вызван в операционную')
  await expect(head.getByText('Вызов вне готовности:')).toBeVisible()

  // The override is visible on the board
  await head.goto('/')
  await expect(head.locator('tbody tr', { hasText: 'Освободилась операционная' })).toBeVisible()

  // The ward nurse is notified in the app (and sees no patient name)
  const nurseContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const nurse = await nurseContext.newPage()
  await login(nurse, 'nurse1')
  await expect(nurse.getByTestId('unread-count')).toBeVisible()
  await nurse.getByRole('button', { name: /Уведомления/ }).click()
  const feed = nurse.getByRole('dialog', { name: 'Уведомления' })
  await expect(feed).toContainText('вызов в операционную')
  expect(await feed.textContent()).not.toMatch(/Тестов |Образцов |Примеров |DEMO-/)
  await headContext.close()
  await nurseContext.close()
})

test('a doctor makes a quick order on a round and it lands in the nurse task list', async ({ browser }) => {
  const doctorContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const doctor = await doctorContext.newPage()
  await login(doctor, 'head1')
  await doctor.getByRole('link', { name: 'Обход' }).click()
  await doctor.getByRole('button', { name: 'Начать обход' }).click()
  await doctor.getByLabel('Исполнитель').selectOption({ label: 'Демо Медсестра Первая · Медсестра' })
  await doctor.getByRole('button', { name: 'Повторный ОАК' }).click()
  await expect(doctor.getByText('Добавлено')).toBeVisible()
  while (!(await doctor.getByRole('button', { name: 'Завершить обход' }).isVisible())) {
    await doctor.getByRole('button', { name: 'Следующий' }).click()
  }
  await doctor.getByRole('button', { name: 'Завершить обход' }).click()
  await expect(doctor.getByText('Итоги обхода')).toBeVisible()
  await expect(doctor.getByText('Назначений за обход')).toBeVisible()
  await expect(doctor.getByRole('heading', { name: 'По исполнителям' })).toBeVisible()

  const nurseContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const nurse = await nurseContext.newPage()
  await login(nurse, 'nurse1')
  await nurse.getByRole('link', { name: 'Мои задачи' }).click()
  await expect(nurse.getByText('ОАК').first()).toBeVisible()
  await nurse.getByRole('button', { name: 'Взять в работу' }).first().click()
  await expect(nurse.getByText('В работе').first()).toBeVisible()
  await doctorContext.close()
  await nurseContext.close()
})
