# E2E tests

[Playwright](https://playwright.dev/) smoke tests that drive a real Chromium
browser against the deployed Sportstracker site. The same tests run on CI
(via `.github/workflows/e2e.yml`) and locally.

## Prerequisites

- Node 20+
- A test user that already exists on whichever environment you're targeting.
  On production this is the user the GitHub `E2E_USERNAME` / `E2E_PASSWORD`
  secrets point at; locally you can use any account you've registered.

## Running locally

```bash
cd e2e
npm ci
npx playwright install chromium

# Point the tests at a running Sportstracker (default is http://localhost:8000).
export BASE_URL=http://localhost:8000
export E2E_USERNAME=your-test-user
export E2E_PASSWORD=your-test-password

npm test
```

`npm run test:headed` runs Chromium in a visible window so you can watch the
flow. `npm run report` opens the HTML report from the last run.

## What's covered

The single `tests/smoke.spec.js` file runs three checks sequentially against
the same user, in the spirit of "smoke + key writes":

1. **Login** — submits the username/password form and asserts we land on
   `/agenda/`.
2. **Body stats** — visits `/bodystats/`, saves today's weight if today
   isn't logged yet, and asserts today's row shows up in the history table.
3. **Attendance toggle** — finds the first `.attendance-check` button on
   `/agenda/`, clicks it, and asserts its modifier class changed (the AJAX
   handler swaps `attendance-check--pending` / `--present` / `--absent`).
   Skips if the test user has no trainings on the agenda this week.

The third test relies on the test user belonging to a crew with at least one
upcoming training. If you're setting up the production E2E user, register
them, add them to a crew (e.g. `E2E Test Crew`), and schedule a recurring
training in that crew so the agenda is never empty.

## How CI runs this

`.github/workflows/deploy.yml` dispatches `e2e.yml` after every successful
deploy. `e2e.yml` reads three repository secrets:

| Secret | Purpose |
|---|---|
| `PRODUCTION_URL` | Full URL of the deployed app, e.g. `https://sportstracker.example.org` |
| `E2E_USERNAME` | Username of the fixed test user on production |
| `E2E_PASSWORD` | Password of that user |

Reports and traces are uploaded as workflow artifacts (`playwright-report`,
`playwright-test-results`) and kept for 7 days, so you can download them
from the failed run page on GitHub.
