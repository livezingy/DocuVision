const { test, expect } = require('@playwright/test');

test('queue e2e scaffold runs', async ({ page }) => {
	await page.setContent('<html><body><div id="app">DocuVision</div></body></html>');
	await expect(page.locator('#app')).toHaveText('DocuVision');
});
