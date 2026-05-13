const { test, expect } = require('@playwright/test');

test.describe('New Case Creation', () => {
    test.beforeEach(async ({ page }) => {
        // Login before each test
        await page.goto('/');
        await page.click('button:has-text("Staff Login")');
        await expect(page.locator('text="Sign in to continue"')).toBeVisible();
        await page.fill('input[type="text"]', 'regularUser');
        await page.fill('input[type="password"]', 'userPass123');
        await page.click('button:has-text("Sign in")');
        await expect(page.locator('text="Logout"')).toBeVisible({ timeout: 10000 });
    });

    test('User can navigate to New Case tab', async ({ page }) => {
        await page.click('button:has-text("UI Body")');
        // Verify we're on the new case page (step indicator should be visible)
        await expect(page.getByText('1. Photos (multi-angle)')).toBeVisible();
    });

    test('New Case form shows image capture controls', async ({ page }) => {
        await page.click('button:has-text("UI Body")');
        // Check that the face frontal capture control is visible
        await expect(page.getByText('Face frontal')).toBeVisible();
        await expect(page.getByText('Capture').first()).toBeVisible();
        await expect(page.getByText('Upload').first()).toBeVisible();
    });

    test('New Case shows face condition options', async ({ page }) => {
        await page.click('button:has-text("UI Body")');
        // Check face condition buttons are visible
        await expect(page.getByRole('button', { name: 'normal' })).toBeVisible();
        await expect(page.getByRole('button', { name: 'partial' })).toBeVisible();
        await expect(page.getByRole('button', { name: 'bloated' })).toBeVisible();
        await expect(page.getByRole('button', { name: 'damaged' })).toBeVisible();
    });
});