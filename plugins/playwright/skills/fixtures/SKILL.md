---
name: fixtures
description: Playwright Fixture & Seed Engineering. Build reusable test fixtures, the seed test used by the official agents (seed.spec.ts), authentication state caching (storageState), and network API mocking.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

# Playwright Fixtures & Seed Engineering

The **Fixtures Skill** manages reusable test environments, authentication caching (`storageState`), and backend mocking, eliminating repetitive boilerplate from test specs.

---

## 🌱 0. The seed test uses these fixtures

The official agents start every plan, generated test, and heal from `seed.spec.ts` (created by `playwright:init`). If tests need login or custom fixtures, the seed must import the same `test`:

```typescript
// seed.spec.ts
import { test, expect } from './fixtures/base-test';

test.describe('Test group', () => {
  test('seed', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });
});
```

Keep credentials in env vars (`TEST_USER_EMAIL`, `TEST_USER_PASSWORD`), never in test files.

---

## 🔐 1. Authentication State Caching (`storageState`)

Never log in via UI forms in every single test. Save auth tokens once and reuse them across all test workers:

### Setup Project in `playwright.config.ts`
```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  projects: [
    // Global setup: runs before all tests to generate auth state
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
    },
    // Main tests using cached authentication
    {
      name: 'authenticated-chrome',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'playwright/.auth/user.json',
      },
      dependencies: ['setup'],
    },
  ],
});
```

### Auth Setup Script (`tests/auth.setup.ts`)
```typescript
import { test as setup, expect } from '@playwright/test';

const authFile = 'playwright/.auth/user.json';

setup('authenticate', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill(process.env.TEST_USER_EMAIL!);
  await page.getByLabel('Password').fill(process.env.TEST_USER_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

  // Save session cookies & local storage
  await page.context().storageState({ path: authFile });
});
```

---

## 🧩 2. Custom Fixtures with `test.extend`

Create domain-specific test fixtures (e.g. `todoPage`, `adminContext`):

```typescript
// fixtures/base-test.ts
import { test as base } from '@playwright/test';
import { DashboardPage } from '../pages/dashboard.page';

type CustomFixtures = {
  dashboardPage: DashboardPage;
};

export const test = base.extend<CustomFixtures>({
  dashboardPage: async ({ page }, use) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();
    await use(dashboard);
  },
});

export { expect } from '@playwright/test';
```

---

## 🌐 3. Network Mocking & API Interception

Intercept network calls with `page.route` to test edge cases without relying on staging backend states:

```typescript
test('displays error toast when API fails with 500', async ({ page }) => {
  // Mock API route
  await page.route('**/api/v1/user/profile', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Internal Server Error' }),
    });
  });

  await page.goto('/settings');
  await expect(page.getByRole('alert')).toContainText('Failed to load profile');
});
```
