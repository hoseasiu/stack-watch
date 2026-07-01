const fs = require("fs");
const path = require("path");

const SIGNALS_DIR = path.join(__dirname, "..", "..", "data", "signals");
const MAX_DAYS = 7;

module.exports = () => {
  if (!fs.existsSync(SIGNALS_DIR)) return [];

  const files = fs
    .readdirSync(SIGNALS_DIR)
    .filter((f) => f.endsWith(".jsonl"))
    .sort()
    .slice(-MAX_DAYS);

  const entries = [];
  for (const file of files) {
    const lines = fs
      .readFileSync(path.join(SIGNALS_DIR, file), "utf8")
      .split("\n")
      .filter((l) => l.trim().length > 0);
    for (const line of lines) entries.push(JSON.parse(line));
  }

  return entries.sort((a, b) => (a.ts < b.ts ? 1 : -1));
};
