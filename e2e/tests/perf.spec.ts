import { expect, test, type Page } from '@playwright/test'
import { login } from './helpers'

// Budget (BUILD_PROMPT section 8): the board loads in < 1.5 s with 60 active cases on a
// mid-range phone over 4G. Pixel 5 viewport, CPU slowed 4x, WebPageTest "4G" network profile.
const FOUR_G = { latency: 170, downloadThroughput: (9 * 1024 * 1024) / 8, uploadThroughput: (9 * 1024 * 1024) / 8 }
// 1.5 s is the product budget. Shared CI runners are slower and noisier than a laptop, so CI sets
// PERF_BUDGET_MS higher; the measured values are always printed.
const BUDGET_MS = Number(process.env.PERF_BUDGET_MS ?? 1500)

async function throttle(page: Page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Network.enable')
  await cdp.send('Network.emulateNetworkConditions', { offline: false, ...FOUR_G })
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
  return cdp
}

async function timeBoard(page: Page): Promise<number> {
  const started = Date.now()
  await page.goto('/')
  await expect(page.locator('tbody tr[data-row-case], tbody tr').nth(60)).toBeVisible({ timeout: 10_000 })
  return Date.now() - started
}

test('the board with 60 active cases loads within 1.5 s on a throttled mid-range phone', async ({ page, browser }) => {
  await login(page, 'nurse1') // log in at full speed, then throttle
  const board = await page.request.get('/api/v1/board')
  const body = await board.json()
  expect(body.rows).toHaveLength(60)
  await page.close()

  const context = await browser.newContext({ ...test.info().project.use, storageState: undefined })
  const second = await context.newPage()
  await login(second, 'nurse1')

  // Repeat visit: app shell already cached by the service worker / HTTP cache
  await second.goto('/')
  await expect(second.locator('tbody tr').nth(60)).toBeVisible()
  await throttle(second)
  const warm = await timeBoard(second)
  console.log(`warm board load: ${warm} ms`)
  expect(warm).toBeLessThan(BUDGET_MS)

  // First visit of the day on a fresh browser profile: nothing cached, only the session cookie
  const cold = await context.browser()!.newContext({ ...test.info().project.use })
  const coldPage = await cold.newPage()
  await login(coldPage, 'nurse1')
  const cdp = await coldPage.context().newCDPSession(coldPage)
  await cdp.send('Network.enable')
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true })
  await cdp.send('Network.emulateNetworkConditions', { offline: false, ...FOUR_G })
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
  const first = await timeBoard(coldPage)
  console.log(`cold board load: ${first} ms`)
  expect(first).toBeLessThan(BUDGET_MS)
  await cold.close()
  await context.close()
})
