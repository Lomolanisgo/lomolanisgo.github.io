import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import {
  createSearch,
  initialFilters,
  mergeRecords,
  officialAudio,
  paginate,
  parseRecords,
  progress,
  queryWords,
  serializeRecords,
} from "./model";
import type { Dataset, Records } from "./model";
const data: Dataset = JSON.parse(
  readFileSync(
    new URL("../public/data/vocabulary.json", import.meta.url),
    "utf8",
  ),
);
const words = data.words;
const search = createSearch(words);
const query = (q: string, extra = {}) =>
  queryWords(
    words,
    search,
    { ...initialFilters, query: q, ...extra },
    {},
    "Korean",
    1,
  );
describe("real database search and filtering", () => {
  it("keeps complete data and homographs", () => {
    expect(words).toHaveLength(5965);
    expect(new Set(words.map((w) => w.ID)).size).toBe(5965);
    expect(
      query("가구")
        .filter((w) => w.Korean === "가구")
        .map((w) => w.Hanja)
        .sort(),
    ).toEqual(["家具", "家口"].sort());
  });
  it.each(["학교", "學校", "学校", "school"])("searches %s", (q) => {
    expect(query(q).some((w) => w.Korean === "학교")).toBe(true);
  });
  it("normalizes compatibility ideographs and English case", () => {
    expect(query("SCHOOL").some((w) => w.Korean === "학교")).toBe(true);
    expect(query("金額").some((w) => w.Korean === "금액")).toBe(true);
  });
  it("supports fuzzy typos", () => {
    expect(query("schoool").some((w) => w.Korean === "학교")).toBe(true);
  });
  it("combines filters", () => {
    const list = query("", { grade: "B", pos: "名词", type: "汉字词" });
    expect(list.length).toBeGreaterThan(100);
    expect(
      list.every(
        (w) => w.grade === "B" && w.POS === "名词" && w.Word_Type === "汉字词",
      ),
    ).toBe(true);
  });
  it("does not classify missing origins as native", () => {
    expect(query("", { type: "固有词" })).toHaveLength(0);
    expect(query("", { type: "unknown" })).toHaveLength(2413);
  });
  it("paginates without duplicating or dropping records", () => {
    const all = Array.from(
      { length: 239 },
      (_, i) => paginate(words, i + 1, 25).items,
    ).flat();
    expect(all.map((w) => w.ID)).toEqual(words.map((w) => w.ID));
    expect(paginate(words, 999, 25).current).toBe(239);
    expect(paginate([], 3, 25)).toEqual({ items: [], pages: 1, current: 1 });
  });
  it("sorts both directions", () => {
    const a = queryWords(words, search, initialFilters, {}, "Hanja", 1);
    const b = queryWords(words, search, initialFilters, {}, "Hanja", -1);
    expect(a[0].Hanja).toBe(b.at(-1)?.Hanja);
  });
});
describe("learning record safety", () => {
  const id = words[0].ID,
    other = words[1].ID;
  const old: Records = {
    [id]: {
      favorite: true,
      status: "learning",
      updatedAt: "2026-01-01T00:00:00Z",
    },
  };
  it("roundtrips records", () =>
    expect(parseRecords(serializeRecords(old))).toEqual(old));
  it("merges newer records and retains other words", () => {
    const incoming: Records = {
      [id]: {
        favorite: false,
        status: "mastered",
        updatedAt: "2026-02-01T00:00:00Z",
      },
      [other]: {
        favorite: true,
        status: "new",
        updatedAt: "2026-01-01T00:00:00Z",
      },
    };
    expect(mergeRecords(old, incoming)).toEqual(incoming);
    expect(mergeRecords(incoming, old)).toBe(incoming);
  });
  it("rejects bad schema, status, IDs and dates atomically", () => {
    for (const bad of [
      {},
      { schemaVersion: 2, records: old },
      { schemaVersion: 1, records: { x: old[id] } },
      { schemaVersion: 1, records: { [id]: { ...old[id], status: "bad" } } },
      {
        schemaVersion: 1,
        records: { [id]: { ...old[id], updatedAt: "yesterday" } },
      },
    ])
      expect(() => parseRecords(JSON.stringify(bad))).toThrow();
  });
  it("counts and filters records by ID", () => {
    expect(progress(words, old)).toEqual({
      new: 5964,
      learning: 1,
      mastered: 0,
      favorites: 1,
    });
    expect(
      queryWords(
        words,
        search,
        { ...initialFilters, favorites: true },
        old,
        "Korean",
        1,
      ).map((w) => w.ID),
    ).toEqual([id]);
  });
  it("never plays invented or untrusted audio", () => {
    expect(officialAudio()).toBeUndefined();
    expect(officialAudio("javascript:alert(1)")).toBeUndefined();
    expect(officialAudio("https://evil.test/a.mp3")).toBeUndefined();
    expect(
      officialAudio("https://krdict.korean.go.kr/audio/a.mp3"),
    ).toBeTruthy();
  });
});
