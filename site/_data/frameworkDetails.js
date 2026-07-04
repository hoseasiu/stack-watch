const fs = require("fs");
const path = require("path");

const FRAMEWORKS_DIR = path.join(__dirname, "..", "..", "data", "frameworks");

function monthlyCounts(signalHistory) {
  const counts = {};
  for (const h of signalHistory || []) {
    const month = (h.date || "").slice(0, 7);
    if (!month) continue;
    counts[month] = (counts[month] || 0) + 1;
  }
  const months = Object.entries(counts)
    .map(([month, count]) => ({ month, count }))
    .sort((a, b) => (a.month < b.month ? -1 : 1));
  const max = months.reduce((m, x) => Math.max(m, x.count), 0);
  return { months, max };
}

module.exports = () => {
  if (!fs.existsSync(FRAMEWORKS_DIR)) return [];

  return fs
    .readdirSync(FRAMEWORKS_DIR)
    .filter((f) => f.endsWith(".json"))
    .map((f) => JSON.parse(fs.readFileSync(path.join(FRAMEWORKS_DIR, f), "utf8")))
    .map((fw) => {
      const { months, max } = monthlyCounts(fw.signal_history);
      return { ...fw, monthly: months, monthly_max: max };
    })
    .sort((a, b) => b.org_count - a.org_count);
};
