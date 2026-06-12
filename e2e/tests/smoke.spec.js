// @ts-check
const { test, expect } = require('@playwright/test');

const USERNAME = process.env.E2E_USERNAME;
const PASSWORD = process.env.E2E_PASSWORD;

test.beforeAll(() => {
  if (!USERNAME || !PASSWORD) {
    throw new Error(
      'E2E_USERNAME and E2E_PASSWORD must be set as environment variables. ' +
      'On CI these come from the GitHub Actions secrets of the same name.',
    );
  }
});

/**
 * Logs in as the fixed E2E user and waits until we land on the agenda page.
 * Reused by every test below.
 */
async function loginAsTestUser(page) {
  await page.goto('/login/');
  await page.fill('input[name="username"]', USERNAME);
  await page.fill('input[name="password"]', PASSWORD);
  await page.click('input[type="submit"][value="Log In"]');
  await expect(page).toHaveURL(/\/agenda\/?$/);
}

test('login flow lands on the agenda page', async ({ page }) => {
  await loginAsTestUser(page);
  // The agenda page renders a week selector with prev/next links.
  await expect(page.locator('body')).toContainText(/Agenda|Week of|Mon|Mo/i);
});

test('logging today\'s body stats shows the entry in the history table', async ({ page }) => {
  await loginAsTestUser(page);
  await page.goto('/bodystats/');

  // The "Log today's stats" form is only present when today has not been logged
  // yet. If a previous test run already saved one, the form is hidden — the
  // assertion at the end is the same in both branches.
  const saveButton = page.getByRole('button', { name: 'Save' });
  if (await saveButton.isVisible().catch(() => false)) {
    await page.fill('input[name="weight"]', '72.5');
    await saveButton.click();
    // Form submits and redirects back to /bodystats/.
    await expect(page).toHaveURL(/\/bodystats\/?$/);
  }

  // Today's row must now exist in the history table — date format from the
  // template is "j M Y", e.g. "12 Jun 2026".
  const today = new Date();
  const day = today.getDate();
  const month = today.toLocaleString('en-GB', { month: 'short' });
  const year = today.getFullYear();
  await expect(page.locator('table.bodystats-history')).toContainText(
    `${day} ${month} ${year}`,
  );
});

test('clicking the attendance toggle changes its state', async ({ page }) => {
  await loginAsTestUser(page);
  await page.goto('/agenda/');

  const buttons = page.locator('button.attendance-check');
  const count = await buttons.count();

  test.skip(count === 0, 'No trainings on the agenda for the test user this week');

  const button = buttons.first();
  const beforeClasses = (await button.getAttribute('class')) || '';

  await button.click();

  // toggleAttendance is AJAX — JS swaps the modifier class on success.
  // We wait until the class list no longer matches the pre-click value.
  await expect.poll(async () => {
    return (await button.getAttribute('class')) || '';
  }, { timeout: 5_000 }).not.toBe(beforeClasses);

  // Sanity check: the button still ends in one of the three known modifiers.
  const afterClasses = (await button.getAttribute('class')) || '';
  expect(afterClasses).toMatch(/attendance-check--(pending|present|absent)/);
});
