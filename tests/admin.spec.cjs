const { test, expect } = require('@playwright/test');

test.describe('Admin UI Features', () => {
    test.beforeEach(async ({ page }) => {
        // Login as admin before each test
        await page.goto('/');
        await page.click('button:has-text("Staff Login")');
        await expect(page.locator('text="Sign in to continue"')).toBeVisible();
        await page.fill('input[type="text"]', 'admin');
        await page.fill('input[type="password"]', 'changeme');
        await page.click('button:has-text("Sign in")');
        await expect(page.locator('button:has-text("User Management")')).toBeVisible({ timeout: 10000 });
    });

    test('Admin user can see User Management tab', async ({ page }) => {
        // Admin should see User Management tab
        const userManagementTab = page.locator('button:has-text("User Management")');
        await expect(userManagementTab).toBeVisible();

        // The "Search In" radio (criminal vs UI-body) was removed in Phase 1
        // scope. The search form should now show only the input controls.
        await page.locator('button:has-text("Search")').first().click();
        await expect(page.getByText("Search In")).not.toBeVisible();
    });

    test('Admin user can access admin users table', async ({ page }) => {
        await page.click('button:has-text("User Management")');
        await expect(page.locator('[data-testid="admin-users-table"]')).toBeVisible({ timeout: 10000 });
    });

    test('Admin user can see audit log', async ({ page }) => {
        await page.click('button:has-text("Audit Log")');
        await expect(page.locator('[data-testid="audit-log-table"]')).toBeVisible({ timeout: 10000 });
    });
});

test.describe('Regular User Admin Access', () => {
    test('Regular user cannot see User Management tab', async ({ page }) => {
        await page.goto('/');
        await page.click('button:has-text("Staff Login")');
        await expect(page.locator('text="Sign in to continue"')).toBeVisible();
        await page.fill('input[type="text"]', 'regularUser');
        await page.fill('input[type="password"]', 'userPass123');
        await page.click('button:has-text("Sign in")');
        await expect(page.locator('text="Logout"')).toBeVisible({ timeout: 10000 });
        
        // Regular user should NOT see User Management tab
        const userManagementTab = page.locator('button:has-text("User Management")');
        await expect(userManagementTab).not.toBeVisible();
    });
});