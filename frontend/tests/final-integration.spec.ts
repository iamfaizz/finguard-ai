import {test, expect} from '@playwright/test';

test('login, duplicate upload and advisor navigation', async ({page}) => {
  const email = `final-${Date.now()}@example.test`;
  const password = 'DemoPass123!';

  await page.goto('/register');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', {name:'Register'}).click();

  await expect(page.getByRole('heading', {
    name:'Financial overview'
  })).toBeVisible();

  await page.getByRole('button', {name:'Logout'}).click();

  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', {name:'Login', exact:true}).click();

  await expect(page.getByRole('heading', {
    name:'Financial overview'
  })).toBeVisible();

  const file = {
    name:'final.csv',
    mimeType:'text/csv',
    buffer:Buffer.from(
      'timestamp,amount,merchant,txn_type\n2026-11-01T12:00:00,150,Demo Store,debit\n'
    )
  };

  await page.getByLabel('Upload transaction CSV').setInputFiles(file);
  await page.getByRole('button', {name:'Upload',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('1 imported');

  await page.getByLabel('Upload transaction CSV').setInputFiles(file);
  await page.getByRole('button', {name:'Upload',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('1 duplicates');

  await page.getByRole('link', {name:'AI Advisor'}).click();
  await expect(page).toHaveURL(/\/advisor-chat$/);
});
