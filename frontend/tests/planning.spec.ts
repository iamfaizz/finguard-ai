import {test, expect} from '@playwright/test';

test('forecast and goal lifecycle', async ({page}) => {
    test.setTimeout(120000);
    await page.goto('/register');
    await page.getByLabel('Email').fill(`planning-${Date.now()}@example.test`);
    await page.getByLabel('Password').fill('DemoPass123!');
    await page.getByRole('button', {name:'Register'}).click();

    await expect(page.getByRole('heading', {name:'Financial overview'})).toBeVisible();

    const rows = Array.from({length:12}, (_,i) =>
        `2026-11-${String(i+1).padStart(2,'0')}T12:00:00,150,Store,debit,5000,Phone-A,Delhi`
    );

    await page.getByLabel('Upload transaction CSV').setInputFiles({
        name:'planning.csv',
        mimeType:'text/csv',
        buffer:Buffer.from(
            'timestamp,amount,merchant,txn_type,balance,device,location\n'
            + rows.join('\n')
        )
    });

    await page.getByRole('button', {name:'Upload',exact:true}).click();
    await expect(page.getByRole('status')).toContainText('12 imported');

    await expect(async () => {
        await page.getByRole('button', {name:'Refresh forecast'}).click();
        await expect(page.getByText('30-day estimated spending')).toBeVisible({timeout:5000});
    }).toPass({timeout:60000});
    await expect(page.getByText('30-day estimated spending')).toBeVisible({timeout:30000});

    await page.getByLabel('Goal name').fill('Emergency Fund');
    await page.getByLabel('Target amount').fill('50000');
    await page.getByLabel('Saved amount').fill('10000');

    const date = new Date();
    date.setMonth(date.getMonth()+6);
    await page.getByLabel('Target date').fill(date.toISOString().slice(0,10));

    await page.getByRole('button', {name:'Create goal'}).click();
    await expect(page.getByText('Goal saved successfully')).toBeVisible();
    await expect(page.getByText('Monthly requirement:', {exact:false})).toBeVisible();

    await page.getByRole('button', {name:'Edit goal'}).click();
    await page.getByLabel('Saved amount').fill('15000');
    await page.getByRole('button', {name:'Update goal'}).click();
    await expect(page.getByRole('button', {name:'Create goal'})).toBeVisible();

    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', {name:'Delete goal'}).click();
    await expect(page.getByText('Goal deleted')).toBeVisible();
});
