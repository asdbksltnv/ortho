import { expect, test } from '@playwright/test'
import { login } from './helpers'

test('the board can be shown as the 10th-floor plan', async ({ page }) => {
  await login(page, 'nurse1')
  await page.getByRole('radio', { name: 'План этажа' }).click()
  for (const n of [1001, 1008, 1016]) {
    await expect(page.locator(`[data-room="Пал. ${n}"]`)).toBeVisible()
  }
  await expect(page.getByRole('img', { name: 'Ординаторская' })).toBeVisible()
  await page.screenshot({ path: 'test-results/floorplan.png', fullPage: true })
  await page.getByRole('link', { name: /^Пал\. 10\d\d: / }).first().click()
  await expect(page).toHaveURL(/\/case\/[0-9a-f-]{36}$/)
})
