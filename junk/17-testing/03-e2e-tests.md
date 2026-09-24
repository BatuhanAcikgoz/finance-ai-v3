# 17/03 — End-to-End Tests (Playwright)

## Critical Paths

1. **Login → view dashboard → click decision detail**
2. **View alerts inbox → mark as read**
3. **Edit portfolio → see updated risk**
4. **Run backtest → view results**
5. **Settings → toggle notifications**

## Example

```typescript
// tests/e2e/dashboard.spec.ts
import { test, expect } from '@playwright/test';

test('user can view decision detail with full evidence trace', async ({ page }) => {
  await page.goto('/login');
  await page.fill('[name=email]', 'test@finance-ai-v3.local');
  await page.fill('[name=password]', 'test-pass');
  await page.click('button[type=submit]');
  
  await page.waitForURL('/');
  
  // Navigate to decisions
  await page.click('a[href="/decisions"]');
  await page.waitForSelector('table');
  
  // Click first decision
  await page.click('table tbody tr:first-child a');
  
  // Verify detail page
  await page.waitForSelector('h1:has-text("Decision Detail")');
  await expect(page.locator('text=Evidence Trace')).toBeVisible();
  await expect(page.locator('[data-testid=evidence-card]').count()).toBeGreaterThan(2);
  
  // Verify compliance audit section
  await expect(page.locator('text=Compliance Audit')).toBeVisible();
  await expect(page.locator('text=APPROVED')).toBeVisible();
});
```

## CI

- Run on every PR (smoke) + nightly (full)
- Smoke: 5 critical paths, < 5 min
- Full: all paths, < 30 min
