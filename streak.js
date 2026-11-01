/* Date helpers and streak calculation. Dates are local "YYYY-MM-DD" strings.
   Loaded as a plain <script> in the browser (globals) and via require() in tests. */
const iso = d => new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
const parse = s => new Date(s + "T12:00:00");
const addDays = (s, n) => { const d = parse(s); d.setDate(d.getDate() + n); return iso(d); };

/* `dates`: sorted unique dates that have an entry; `todayStr`: today as a date string.
   best = longest run of consecutive days ever. current = the latest run, still alive if it
   ends today or yesterday (so the streak doesn't read 0 before you log anything today). */
function calcStreaks(dates, todayStr) {
  let best = 0, run = 0, prev = null;
  for (const d of dates) {
    run = prev && d === addDays(prev, 1) ? run + 1 : 1;
    best = Math.max(best, run);
    prev = d;
  }
  const alive = prev === todayStr || prev === addDays(todayStr, -1);
  return { current: alive ? run : 0, best };
}

if (typeof module !== "undefined") module.exports = { iso, parse, addDays, calcStreaks };
