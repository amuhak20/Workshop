process.env.TZ = "Asia/Kolkata"; // before any Date is created
const test = require("node:test");
const assert = require("node:assert/strict");
const { iso, addDays, calcStreaks } = require("./streak.js");

test("runs in India time", () => {
  assert.equal(new Date(2026, 10, 2).getTimezoneOffset(), -330);
});

test("no entries", () => {
  assert.deepEqual(calcStreaks([], "2026-11-02"), { current: 0, best: 0 });
});

test("current streak ending today", () => {
  assert.deepEqual(calcStreaks(["2026-10-31", "2026-11-01", "2026-11-02"], "2026-11-02"), { current: 3, best: 3 });
});

test("streak ending yesterday is still alive", () => {
  assert.deepEqual(calcStreaks(["2026-10-30", "2026-10-31", "2026-11-01"], "2026-11-02"), { current: 3, best: 3 });
});

test("a missed day resets current but keeps best", () => {
  const dates = ["2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-30"];
  assert.deepEqual(calcStreaks(dates, "2026-11-02"), { current: 0, best: 4 });
});

test("best can be an older run than the current one", () => {
  const dates = ["2026-10-10", "2026-10-11", "2026-10-12", "2026-11-01", "2026-11-02"];
  assert.deepEqual(calcStreaks(dates, "2026-11-02"), { current: 2, best: 3 });
});

test("runs across month and year ends", () => {
  assert.deepEqual(calcStreaks(["2026-12-30", "2026-12-31", "2027-01-01"], "2027-01-01"), { current: 3, best: 3 });
});

test("addDays steps one calendar day", () => {
  assert.equal(addDays("2026-03-07", 1), "2026-03-08");
  assert.equal(addDays("2026-03-01", -1), "2026-02-28");
});

test("task logged at 00:30 India time gets the India date, not the UTC one", () => {
  const logged = new Date(2026, 10, 2, 0, 30); // 00:30 IST = 19:00 UTC on Nov 1
  assert.equal(logged.toISOString().slice(0, 10), "2026-11-01"); // the naive, wrong date
  assert.equal(iso(logged), "2026-11-02");
});

test("00:30 entry extends the streak from the previous day", () => {
  const today = iso(new Date(2026, 10, 2, 0, 30));
  assert.deepEqual(calcStreaks(["2026-11-01", today], today), { current: 2, best: 2 });
});

test("00:30 entry alone: streak is 1 and alive on that day", () => {
  const today = iso(new Date(2026, 10, 2, 0, 30));
  assert.deepEqual(calcStreaks([today], today), { current: 1, best: 1 });
});
