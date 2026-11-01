// DevTrack automation: 5 positive + 3 negative cases, mapped to test-plan-dev-tracker.md IDs.
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');

const APP = pathToFileURL(path.resolve(__dirname, '..', '..', 'dev-tracker.html')).href;
const KEY = 'devtrack.v1';

// Every test starts from an empty app (own browser context => own localStorage).
test.beforeEach(async ({ page }) => {
  await page.goto(APP);
  await page.evaluate((k) => localStorage.removeItem(k), KEY);
  await page.reload();
});

const stat = (page, label) => page.locator('.stat', { hasText: label }).locator('b');

async function addTask(page, fields) {
  await page.click('#add');
  const f = page.locator('#form');
  for (const [name, value] of Object.entries(fields)) {
    const el = f.locator(`[name="${name}"]`);
    if ((await el.evaluate((n) => n.tagName)) === 'SELECT') await el.selectOption(value);
    else await el.fill(String(value));
  }
  await f.locator('button.primary').click();
}

const storedTasks = (page) =>
  page.evaluate((k) => JSON.parse(localStorage.getItem(k) || '{"tasks":[]}').tasks, KEY);

// ---------------------------------------------------------------- POSITIVE

test('P1 [T-02/T-03] create a task: card lands in To do with its details', async ({ page }) => {
  await addTask(page, { title: 'Write API docs', project: 'api-service', type: 'Docs', priority: 'high', est: 2 });

  const todo = page.locator('.col[data-s="todo"]');
  const card = todo.locator('.card', { hasText: 'Write API docs' });
  await expect(card).toHaveCount(1);
  await expect(card).toHaveClass(/high/);
  await expect(card.locator('.tag')).toHaveText('api-service');
  await expect(card).toContainText('Docs');
  await expect(card).toContainText('⏱ 0.0/2h');
  await expect(stat(page, 'Open tasks')).toHaveText('1');
  expect(await storedTasks(page)).toHaveLength(1);
});

test('P2 [S-01/S-02] drag a card to Done: moves column, sets doneAt, updates stats and weekly summary', async ({ page }) => {
  await addTask(page, { title: 'Ship release' });

  await page.locator('.card', { hasText: 'Ship release' })
    .dragTo(page.locator('.col[data-s="done"]'));

  await expect(page.locator('.col[data-s="done"] .card', { hasText: 'Ship release' })).toHaveCount(1);
  await expect(page.locator('.col[data-s="todo"] .card')).toHaveCount(0);
  await expect(stat(page, 'Done this week')).toHaveText('1');
  await expect(stat(page, 'Open tasks')).toHaveText('0');
  await expect(page.locator('#weekly li', { hasText: 'Ship release' })).toHaveCount(1);
  const [t] = await storedTasks(page);
  expect(t.status).toBe('done');
  expect(t.doneAt).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});

test('P3 [L-01/L-07] log time: card hours, stat, Time log and project total update', async ({ page }) => {
  await addTask(page, { title: 'Fix login bug', project: 'web-app' });

  await page.locator('.card', { hasText: 'Fix login bug' }).getByRole('button', { name: '+ Time' }).click();
  await page.locator('#tform [name="hours"]').fill('1.5');
  await page.locator('#tform [name="note"]').fill('pair session');
  await page.locator('#tform button.primary').click();

  await expect(page.locator('.card', { hasText: 'Fix login bug' })).toContainText('⏱ 1.5h');
  await expect(stat(page, 'Logged this week')).toHaveText('1.5h');

  await page.click('.tabs button[data-v="time"]');
  const row = page.locator('#time tr', { hasText: 'Fix login bug' });
  await expect(row).toContainText('1.5');
  await expect(row).toContainText('pair session');
  await expect(page.locator('#time .tag')).toHaveText('web-app: 1.5h');
});

test('P4 [F-01..F-04] search, project and type filters combine (AND)', async ({ page }) => {
  await addTask(page, { title: 'Alpha login', project: 'web', type: 'Bug' });
  await addTask(page, { title: 'Alpha report', project: 'api', type: 'Feature' });
  await addTask(page, { title: 'Beta login', project: 'web', type: 'Feature' });
  const cards = page.locator('.card');
  await expect(cards).toHaveCount(3);

  await page.fill('#q', 'ALPHA'); // case-insensitive
  await expect(cards).toHaveCount(2);

  await page.selectOption('#fp', 'web');
  await expect(cards).toHaveCount(1);
  await expect(cards.first()).toContainText('Alpha login');

  await page.selectOption('#ft', 'Feature'); // Alpha + web + Feature => none
  await expect(cards).toHaveCount(0);
  await expect(page.locator('.col .empty')).toHaveCount(4);
});

test('P5 [P-02/P-03] export then import restores all data', async ({ page }, testInfo) => {
  await addTask(page, { title: 'Persist me', project: 'core', notes: 'keep these notes' });
  await page.locator('.card', { hasText: 'Persist me' }).getByRole('button', { name: '+ Time' }).click();
  await page.locator('#tform button.primary').click(); // default 1 h today

  const [download] = await Promise.all([page.waitForEvent('download'), page.click('#exp')]);
  expect(download.suggestedFilename()).toMatch(/^devtrack-\d{4}-\d{2}-\d{2}\.json$/);
  const file = testInfo.outputPath('export.json');
  await download.saveAs(file);
  const exported = JSON.parse(fs.readFileSync(file, 'utf8'));
  expect(exported.tasks[0].logs).toHaveLength(1);

  // wipe, then import (confirm dialog must appear first)
  await page.evaluate((k) => localStorage.removeItem(k), KEY);
  await page.reload();
  await expect(page.locator('.card')).toHaveCount(0);

  page.once('dialog', async (d) => {
    expect(d.type()).toBe('confirm');
    expect(d.message()).toContain('Replace current data');
    await d.accept();
  });
  await page.setInputFiles('#file', file);

  const card = page.locator('.card', { hasText: 'Persist me' });
  await expect(card).toHaveCount(1);
  await expect(card).toContainText('⏱ 1.0h');
  await page.reload(); // persisted, not just in memory
  await expect(page.locator('.card', { hasText: 'Persist me' })).toHaveCount(1);
});

// ---------------------------------------------------------------- NEGATIVE

test('N1 [T-01] saving a task with an empty title is blocked', async ({ page }) => {
  await page.click('#add');
  await page.locator('#form button.primary').click();

  await expect(page.locator('#dlg')).toHaveJSProperty('open', true); // dialog stays open
  expect(await page.locator('#form [name="title"]').evaluate((el) => el.validity.valueMissing)).toBe(true);
  await page.locator('#cancel').click();
  await expect(page.locator('.card')).toHaveCount(0);
  expect(await storedTasks(page)).toHaveLength(0);
});

test('N2 [P-05] importing invalid files is rejected and existing data is untouched', async ({ page }, testInfo) => {
  await addTask(page, { title: 'Keep me' });

  const bad = {
    'not-json.json': 'this is {not json',
    'no-tasks.json': '{}',
    'tasks-not-array.json': '{"tasks":"x"}',
  };
  for (const [name, body] of Object.entries(bad)) {
    const f = testInfo.outputPath(name);
    fs.writeFileSync(f, body);
    const dialogs = [];
    const onDialog = async (d) => { dialogs.push(d.message()); await d.dismiss(); };
    page.on('dialog', onDialog);
    await page.setInputFiles('#file', f);
    await expect.poll(() => dialogs.length, { message: name }).toBe(1);
    page.off('dialog', onDialog);
    expect(dialogs[0]).toBe('Invalid DevTrack file.');
  }

  await expect(page.locator('.card', { hasText: 'Keep me' })).toHaveCount(1);
  expect(await storedTasks(page)).toHaveLength(1);
});

test('N3 [X-01/X-02] hostile text is rendered inert and javascript: links are not clickable', async ({ page }) => {
  const xss = '<img src=x onerror="window.__pwned=1">';
  await addTask(page, { title: xss, project: '"><b>p</b>', link: 'javascript:window.__pwned=1' });

  const card = page.locator('.card').first();
  await expect(card.locator('.t')).toHaveText(xss);          // literal text, not markup
  await expect(page.locator('.card img, .card b')).toHaveCount(0);
  await expect(card.locator('a')).toHaveCount(0);             // unsafe link not rendered
  await expect(page.locator('#fp option', { hasText: '<b>p</b>' })).toHaveCount(1); // escaped in filter too
  await page.waitForTimeout(200);                             // give any onerror a chance to fire
  expect(await page.evaluate(() => window.__pwned)).toBeUndefined();
});
