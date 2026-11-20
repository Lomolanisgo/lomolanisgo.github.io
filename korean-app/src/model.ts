import Fuse from "fuse.js";

export interface Word {
  ID: string;
  Korean: string;
  Hanja: string;
  Chinese: string;
  English: string;
  POS: string;
  Level: string;
  Word_Type: string;
  Pronunciation: string;
  Example: string;
  Example_CN: string;
  grade: string;
  homonym: string;
  officialWord: string;
  originNote: string;
  source: string;
  search: string;
  Audio_URL?: string;
}
export interface Dataset {
  schemaVersion: number;
  updatedAt: string;
  hash: string;
  total: number;
  words: Word[];
}
export type Status = "new" | "learning" | "mastered";
export interface RecordEntry {
  favorite: boolean;
  status: Status;
  updatedAt: string;
}
export type Records = Record<string, RecordEntry>;
export const statusNames: Record<Status, string> = {
  new: "未学习",
  learning: "学习中",
  mastered: "已掌握",
};
export const STORAGE_KEY = "korean.learning.v1";
export interface Filters {
  query: string;
  grade: string;
  pos: string;
  type: string;
  status: string;
  favorites: boolean;
}
export const initialFilters: Filters = {
  query: "",
  grade: "",
  pos: "",
  type: "",
  status: "",
  favorites: false,
};
export type SortKey =
  | "Korean"
  | "Hanja"
  | "Chinese"
  | "English"
  | "POS"
  | "Level"
  | "Word_Type"
  | "Pronunciation";
const collator = new Intl.Collator("ko", { numeric: true });
export function createSearch(words: Word[]) {
  return new Fuse(words, {
    keys: ["Korean", "Hanja", "Chinese", "English"],
    threshold: 0.28,
    ignoreLocation: true,
    minMatchCharLength: 2,
  });
}
export function queryWords(
  words: Word[],
  search: ReturnType<typeof createSearch>,
  filters: Filters,
  records: Records,
  sort: SortKey,
  direction: 1 | -1,
) {
  const query = filters.query.trim().normalize("NFKC").toLowerCase();
  const exact = query
    ? words.filter((w) => query.split(/\s+/).every((t) => w.search.includes(t)))
    : words;
  // Exact substring matches first; fuzzy results only when no exact match exists.
  const candidates =
    query && !exact.length ? search.search(query).map((r) => r.item) : exact;
  return candidates
    .filter(
      (w) =>
        (!filters.grade || w.grade === filters.grade) &&
        (!filters.pos || w.POS === filters.pos) &&
        (!filters.type ||
          (filters.type === "unknown"
            ? !w.Word_Type
            : w.Word_Type === filters.type)) &&
        (!filters.status ||
          (records[w.ID]?.status || "new") === filters.status) &&
        (!filters.favorites || records[w.ID]?.favorite),
    )
    .sort(
      (a, b) =>
        direction * collator.compare(a[sort], b[sort]) ||
        a.ID.localeCompare(b.ID),
    );
}
export function paginate<T>(items: T[], page: number, size: number) {
  const pages = Math.max(1, Math.ceil(items.length / size));
  const current = Math.max(1, Math.min(page, pages));
  return {
    items: items.slice((current - 1) * size, current * size),
    pages,
    current,
  };
}
export function parseRecords(text: string): Records {
  const data: unknown = JSON.parse(text);
  if (
    !data ||
    typeof data !== "object" ||
    !("schemaVersion" in data) ||
    data.schemaVersion !== 1 ||
    !("records" in data) ||
    !data.records ||
    typeof data.records !== "object" ||
    Array.isArray(data.records)
  )
    throw new Error("不是有效的版本 1 学习记录文件。");
  const result: Records = {};
  for (const [id, r] of Object.entries(data.records)) {
    if (
      !/^NIKL2003-[a-f0-9]{16}$/.test(id) ||
      !r ||
      typeof r !== "object" ||
      typeof r.favorite !== "boolean" ||
      !["new", "learning", "mastered"].includes(r.status) ||
      typeof r.updatedAt !== "string" ||
      !Number.isFinite(Date.parse(r.updatedAt))
    )
      throw new Error("学习记录包含无效词条或状态，未导入任何数据。");
    result[id] = {
      favorite: r.favorite,
      status: r.status,
      updatedAt: r.updatedAt,
    };
  }
  return result;
}
export function serializeRecords(records: Records) {
  return JSON.stringify(
    { schemaVersion: 1, exportedAt: new Date().toISOString(), records },
    null,
    2,
  );
}
export function mergeRecords(current: Records, incoming: Records): Records {
  const result = { ...current };
  let changed = false;
  for (const [id, r] of Object.entries(incoming))
    if (
      !result[id] ||
      Date.parse(r.updatedAt) > Date.parse(result[id].updatedAt)
    ) {
      result[id] = r;
      changed = true;
    }
  return changed ? result : current;
}
export function progress(words: Word[], records: Records) {
  const counts = { new: 0, learning: 0, mastered: 0, favorites: 0 };
  for (const w of words) {
    counts[records[w.ID]?.status || "new"]++;
    if (records[w.ID]?.favorite) counts.favorites++;
  }
  return counts;
}
export function officialAudio(url?: string) {
  try {
    const u = new URL(url || "");
    return u.protocol === "https:" &&
      (u.hostname === "krdict.korean.go.kr" ||
        u.hostname.endsWith(".korean.go.kr"))
      ? u.href
      : undefined;
  } catch {
    return undefined;
  }
}
