const fs = require("fs");
const path = require("path");

const ORGS_DIR = path.join(__dirname, "..", "..", "data", "orgs");

module.exports = () => {
  if (!fs.existsSync(ORGS_DIR)) return [];

  const orgs = fs
    .readdirSync(ORGS_DIR)
    .filter((f) => f.endsWith(".json") && !f.startsWith("_"))
    .map((f) => JSON.parse(fs.readFileSync(path.join(ORGS_DIR, f), "utf8")));

  const counts = {};
  for (const org of orgs) {
    counts[org.sector] = (counts[org.sector] || 0) + 1;
  }

  return Object.entries(counts)
    .map(([sector, count]) => ({ sector, count }))
    .sort((a, b) => b.count - a.count);
};
