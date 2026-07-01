const fs = require("fs");
const path = require("path");

const ORGS_DIR = path.join(__dirname, "..", "..", "data", "orgs");

module.exports = () => {
  if (!fs.existsSync(ORGS_DIR)) return [];

  return fs
    .readdirSync(ORGS_DIR)
    .filter((f) => f.endsWith(".json") && !f.startsWith("_"))
    .map((f) => JSON.parse(fs.readFileSync(path.join(ORGS_DIR, f), "utf8")))
    .sort((a, b) => (a.last_updated < b.last_updated ? 1 : -1));
};
