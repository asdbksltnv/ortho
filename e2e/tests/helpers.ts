import { expect, type Page } from '@playwright/test'

export const PASSWORD = 'E2e!Passw0rd12'

export async function login(page: Page, login: string) {
  await page.goto('/login')
  await page.getByLabel('Логин').fill(login)
  await page.getByLabel('Пароль').fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти' }).click()
  await expect(page.getByRole('button', { name: 'Выйти' })).toBeVisible()
}
