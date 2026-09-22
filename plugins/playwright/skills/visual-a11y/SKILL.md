---
name: visual-a11y
description: Playwright Visual & Accessibility Auditing. Automates pixel-perfect visual regression testing (toHaveScreenshot), accessibility compliance (Axe-core), and responsive viewport verification.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

# Playwright Visual & Accessibility Auditing

The **Visual & A11y Skill** automates visual regression testing and WCAG accessibility audits using Playwright's native screenshot engine and Axe-core.

---

## 📸 1. Visual Regression Testing

Verify UI layouts, themes, and CSS rendering without writing hundreds of manual element assertions:

```typescript
import { test, expect } from '@playwright/test';

test('landing page visual snapshot matches baseline', async ({ page }) => {
  await page.goto('/');

  // Wait for the page's own "ready" signal, not networkidle (discouraged by Playwright)
  await expect(page.getByRole('main')).toBeVisible();

  // Full page snapshot
  await expect(page).toHaveScreenshot('landing-page.png', {
    fullPage: true,
    maxDiffPixelRatio: 0.02, // Allow up to 2% pixel tolerance for font sub-pixel rendering
  });
});

test('component-level snapshot', async ({ page }) => {
  await page.goto('/components/pricing-card');
  const card = page.getByTestId('pricing-tier-pro');
  await expect(card).toHaveScreenshot('pricing-tier-pro.png');
});
```

- Baselines are OS/browser specific. Generate and compare them on the same platform (e.g. CI's Linux image).
- Mask changing content (dates, avatars) with `mask: [locator]` instead of raising the tolerance.

### Updating Baselines
Only after a human confirms the visual change is intended:
```bash
npx playwright test --update-snapshots
```

---

## ♿ 2. Accessibility Audits (Axe-Core)

Audit pages for WCAG 2.1 AA compliance:

### Installation
```bash
npm install -D @axe-core/playwright
```

### Automated Accessibility Test
```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('dashboard has no detectable accessibility violations', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.getByRole('main')).toBeVisible();

  const accessibilityScanResults = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .exclude('.third-party-widget') // Exclude external iframes if needed
    .analyze();

  expect(accessibilityScanResults.violations).toEqual([]);
});
```

---

## Report

- Visual: each mismatched snapshot with its diff image path under `test-results/`.
- A11y: each violation with rule id, impact, the element, the WCAG tag, and a fix.
- Never "fix" a failure by updating baselines or excluding elements without asking the user.
