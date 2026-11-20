import { readFile, mkdir, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
const root = new URL("../../", import.meta.url);
const read = async (p) => JSON.parse(await readFile(new URL(p, root), "utf8"));
const vocabulary = await read("vocabulary.json");
const provenance = await read("provenance.json");
const manifest = await read("data/raw/manifest.json");
const byId = new Map(provenance.map((p) => [p.ID, p]));
if (
  !vocabulary.length ||
  new Set(vocabulary.map((w) => w.ID)).size !== vocabulary.length
)
  throw new Error("Invalid vocabulary IDs");
const words = vocabulary.map(({ Source, ...word }) => {
  const p = byId.get(word.ID);
  if (!p) throw new Error("Missing provenance: " + word.ID);
  return {
    ...word,
    grade: p.Official_Grade,
    homonym: p.Homonym_Number,
    officialWord: p.Official_Word,
    originNote: p.Official_Note,
    source: Source,
    search: [word.Korean, word.Hanja, word.Chinese, word.English]
      .join(" ")
      .normalize("NFKC")
      .toLowerCase(),
  };
});
const payload = {
  schemaVersion: 1,
  updatedAt: manifest.snapshot_recorded_utc,
  hash: createHash("sha256").update(JSON.stringify(vocabulary)).digest("hex"),
  total: words.length,
  words,
};
const destination = new URL("../public/data/", import.meta.url);
await mkdir(destination, { recursive: true });
await writeFile(
  new URL("vocabulary.json", destination),
  JSON.stringify(payload),
);
console.log(
  `Prepared ${words.length} entries from existing database (no network requests).`,
);
