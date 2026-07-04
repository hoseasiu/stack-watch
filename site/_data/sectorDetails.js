const fs = require("fs");
const path = require("path");

const SECTORS_DIR = path.join(__dirname, "..", "..", "data", "sectors");

module.exports = () => {
  if (!fs.existsSync(SECTORS_DIR)) return [];

  return fs
    .readdirSync(SECTORS_DIR)
    .filter((f) => f.endsWith(".json"))
    .map((f) => JSON.parse(fs.readFileSync(path.join(SECTORS_DIR, f), "utf8")))
    .sort((a, b) => b.org_count - a.org_count);
};
