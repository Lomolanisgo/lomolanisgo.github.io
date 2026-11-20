import { Icon, WordActions, Details } from "./components";
import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import type {
  Dataset,
  Filters,
  Records,
  RecordEntry,
  SortKey,
  Word,
} from "./model";
import {
  createSearch,
  initialFilters,
  mergeRecords,
  paginate,
  parseRecords,
  progress,
  queryWords,
  serializeRecords,
  statusNames,
  STORAGE_KEY,
} from "./model";

type View = "words" | "cards" | "favorites" | "stats";
const labels: Record<View, string> = {
  words: "词汇库",
  cards: "单词卡片",
  favorites: "收藏",
  stats: "学习统计",
};
const columns: [SortKey, string][] = [
  ["Korean", "韩语"],
  ["Hanja", "汉字"],
  ["Chinese", "中文"],
  ["English", "英文"],
  ["POS", "词性"],
  ["Level", "官方分级"],
  ["Word_Type", "词汇类型"],
  ["Pronunciation", "标准发音"],
];
const blank = "—";
export default function App() {
  const [dataset, setDataset] = useState<Dataset>();
  const [loadError, setLoadError] = useState("");
  const [view, setView] = useState<View>("words");
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const query = useDeferredValue(filters.query);
  const [sort, setSort] = useState<SortKey>("Korean");
  const [direction, setDirection] = useState<1 | -1>(1);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(25);
  const [records, setRecords] = useState<Records>({});
  const [notice, setNotice] = useState("");
  const [storageReady, setStorageReady] = useState(false);
  const [selected, setSelected] = useState<Word>();
  const [cardIndex, setCardIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [dark, setDark] = useState(() => {
    try {
      return (
        (localStorage.getItem("korean.theme") ||
          (matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light")) === "dark"
      );
    } catch {
      return false;
    }
  });
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${import.meta.env.BASE_URL}data/vocabulary.json`, {
      signal: controller.signal,
    })
      .then((r) => {
        if (!r.ok) throw new Error("数据加载失败");
        return r.json();
      })
      .then((data: Dataset) => {
        if (
          data.schemaVersion !== 1 ||
          !Array.isArray(data.words) ||
          data.total !== data.words.length
        )
          throw new Error("数据库格式不兼容");
        setDataset(data);
      })
      .catch((e) => {
        if (e.name !== "AbortError")
          setLoadError("无法加载词汇数据，请检查网络后重试。");
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setRecords(parseRecords(raw));
      setStorageReady(true);
    } catch {
      setNotice(
        "本地记录无法读取，暂不覆盖原记录。可先导出备份，再导入有效文件以恢复保存。",
      );
    }
  }, []);
  useEffect(() => {
    if (storageReady)
      try {
        localStorage.setItem(STORAGE_KEY, serializeRecords(records));
      } catch {
        setNotice("浏览器无法保存记录。本次更改仅在当前页面有效，请导出备份。");
      }
  }, [records, storageReady]);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try {
      localStorage.setItem("korean.theme", dark ? "dark" : "light");
    } catch {
      /* Theme remains usable in memory. */
    }
  }, [dark]);
  useEffect(() => {
    const sync = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && e.newValue)
        try {
          setRecords((current) =>
            mergeRecords(current, parseRecords(e.newValue!)),
          );
        } catch {
          setNotice("另一标签页的记录格式异常，已保留当前记录。");
        }
    };
    addEventListener("storage", sync);
    return () => removeEventListener("storage", sync);
  }, []);
  const words = dataset?.words || [];
  const search = useMemo(() => createSearch(words), [dataset]);
  const results = useMemo(
    () =>
      queryWords(
        words,
        search,
        { ...filters, query, favorites: view === "favorites" },
        records,
        sort,
        direction,
      ),
    [dataset, search, filters, query, view, records, sort, direction],
  );
  const paged = paginate(results, page, size);
  const counts = useMemo(() => progress(words, records), [dataset, records]);
  const card = results[cardIndex % Math.max(1, results.length)];
  useEffect(() => {
    setRevealed(false);
  }, [card?.ID]);
  function filter(patch: Partial<Filters>) {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
    setCardIndex(0);
    setRevealed(false);
  }
  function update(id: string, patch: Partial<RecordEntry>) {
    setRecords((r) => ({
      ...r,
      [id]: {
        ...(r[id] || { favorite: false, status: "new" }),
        ...patch,
        updatedAt: new Date().toISOString(),
      },
    }));
  }
  function download() {
    const blob = new Blob([serializeRecords(records)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `korean-learning-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function importFile(file?: File) {
    if (!file) return;
    try {
      if (file.size > 5_000_000) throw new Error("文件过大，最大支持 5 MB。");
      const incoming = parseRecords(await file.text());
      setRecords((current) => mergeRecords(current, incoming));
      setStorageReady(true);
      const ids = new Set(words.map((w) => w.ID));
      const unknown = Object.keys(incoming).filter((id) => !ids.has(id)).length;
      setNotice(
        `已合并 ${Object.keys(incoming).length} 条记录，同一词条保留更新时间较新的记录。${unknown ? `其中 ${unknown} 条不在当前词表中，已保留备份但不计入进度。` : ""}`,
      );
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "导入失败");
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }
  function switchView(next: View) {
    setView(next);
    setPage(1);
    setCardIndex(0);
    setRevealed(false);
  }
  return (
    <>
      <a className="skip" href="#main">
        跳至内容
      </a>
      <div className="site-link">
        <a href="/">← Yicheng's Grocery · 杂货铺</a>
        <span>个人学习空间</span>
      </div>
      <div className="app-shell">
        <header>
          <div className="title-row">
            <h1>
              <Icon name="book" />
              <span lang="ko">한국어</span>
              <span className="title-divider">·</span> 韩语学习
            </h1>
            <button
              className="theme-button"
              aria-label={dark ? "切换浅色模式" : "切换深色模式"}
              onClick={() => setDark(!dark)}
            >
              <Icon name={dark ? "sun" : "moon"} />
            </button>
          </div>
          <nav aria-label="学习栏目">
            {(Object.keys(labels) as View[]).map((v) => (
              <button
                key={v}
                aria-current={view === v ? "page" : undefined}
                className={view === v ? "active" : ""}
                onClick={() => switchView(v)}
              >
                {labels[v]}
                {v === "favorites" && counts.favorites > 0 && (
                  <span className="count">{counts.favorites}</span>
                )}
              </button>
            ))}
          </nav>
        </header>
        <main id="main">
          <div className="intro">
            <span>
              国立国语院分级词汇 ·{" "}
              {dataset ? dataset.total.toLocaleString() : "…"} 条
            </span>
            <span>面向汉语学习者 · TOPIK 4 级学习目标</span>
          </div>
          {notice && (
            <div role="status" className="notice">
              {notice}
              <button aria-label="关闭提示" onClick={() => setNotice("")}>
                ✕
              </button>
            </div>
          )}
          {loadError ? (
            <div role="alert" className="empty">
              {loadError}
              <button onClick={() => location.reload()}>重新加载</button>
            </div>
          ) : !dataset ? (
            <p role="status" className="empty">
              正在加载词汇数据库…
            </p>
          ) : view === "stats" ? (
            <section aria-label="学习进度">
              <h2>每一个词，都是一点进步。</h2>
              <p className="muted">
                记录保存在当前浏览器中。清理浏览器数据前，请导出备份。
              </p>
              <div className="stats-grid">
                {(["new", "learning", "mastered", "favorites"] as const).map(
                  (k) => (
                    <article key={k}>
                      <span>
                        {k === "favorites" ? "已收藏" : statusNames[k]}
                      </span>
                      <strong>{counts[k].toLocaleString()}</strong>
                    </article>
                  ),
                )}
              </div>
              <h3>
                掌握进度{" "}
                <span className="muted">
                  {((counts.mastered / words.length) * 100).toFixed(1)}%
                </span>
              </h3>
              <progress
                value={counts.mastered}
                max={words.length}
                aria-label="整体掌握进度"
              />
              <div className="level-progress">
                {["A", "B", "C"].map((grade, i) => {
                  const subset = words.filter((w) => w.grade === grade);
                  const p = progress(subset, records);
                  return (
                    <div key={grade}>
                      <span>
                        {["初级", "中级", "高级"][i]} · {grade}
                      </span>
                      <progress
                        value={p.mastered}
                        max={subset.length}
                        aria-label={`${grade} 级掌握进度`}
                      />
                      <span>
                        {p.mastered} / {subset.length}
                      </span>
                    </div>
                  );
                })}
              </div>
              <div className="backup">
                <h3>学习记录备份</h3>
                <p>
                  导入时按更新时间合并收藏与学习状态，不清空已有记录。文件不包含个人账户信息。
                </p>
                <button onClick={download}>导出学习记录</button>
                <button onClick={() => fileRef.current?.click()}>
                  导入学习记录
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".json,application/json"
                  className="visually-hidden"
                  aria-label="导入学习记录文件"
                  onChange={(e) => void importFile(e.target.files?.[0])}
                />
              </div>
            </section>
          ) : (
            <>
              <div className="search-box">
                <Icon name="search" />
                <input
                  aria-label="搜索词汇"
                  placeholder="搜索韩语、汉字、中文、英文…"
                  value={filters.query}
                  onChange={(e) => filter({ query: e.target.value })}
                />
                {filters.query && (
                  <button
                    onClick={() => filter({ query: "" })}
                    aria-label="清空搜索"
                  >
                    ✕
                  </button>
                )}
              </div>
              <div className="filters">
                <select
                  aria-label="官方分级"
                  value={filters.grade}
                  onChange={(e) => filter({ grade: e.target.value })}
                >
                  <option value="">全部等级</option>
                  <option value="A">初级 · A</option>
                  <option value="B">中级 · B</option>
                  <option value="C">高级 · C</option>
                </select>
                <select
                  aria-label="词性"
                  value={filters.pos}
                  onChange={(e) => filter({ pos: e.target.value })}
                >
                  <option value="">全部词性</option>
                  {[...new Set(words.map((w) => w.POS))].map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
                <select
                  aria-label="词汇类型"
                  value={filters.type}
                  onChange={(e) => filter({ type: e.target.value })}
                >
                  <option value="">全部词汇类型</option>
                  {["汉字词", "固有词", "外来词", "混合词"].map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                  <option value="unknown">词源未确认</option>
                </select>
                <select
                  aria-label="学习状态筛选"
                  value={filters.status}
                  onChange={(e) => filter({ status: e.target.value })}
                >
                  <option value="">全部学习状态</option>
                  {Object.entries(statusNames).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
                <button
                  className="text-button"
                  onClick={() => filter(initialFilters)}
                >
                  重置筛选
                </button>
              </div>
              <div className="result-info" aria-live="polite">
                <span>
                  共 {results.length.toLocaleString()} 条
                  {view === "favorites" ? "收藏" : ""}词汇
                </span>
                <span>
                  {view === "cards"
                    ? "卡片使用当前筛选结果"
                    : "点击词头查看详情 · 点击表头排序"}
                </span>
              </div>
              {!results.length ? (
                <div className="empty">
                  <h2>
                    {view === "favorites"
                      ? "还没有符合条件的收藏"
                      : "没有匹配的词汇"}
                  </h2>
                  <p>
                    {filters.type === "固有词"
                      ? "当前数据尚未确认固有词分类，请查看“词源未确认”。"
                      : "试试其他关键词，或清除筛选条件。"}
                  </p>
                  <button onClick={() => filter(initialFilters)}>
                    清除筛选
                  </button>
                </div>
              ) : view === "cards" ? (
                <section className="card-area">
                  <div className="flashcard">
                    <div className="card-meta">
                      <span>
                        {(cardIndex % results.length) + 1} / {results.length}
                      </span>
                      <span>
                        {card.Level} · {card.POS}
                      </span>
                    </div>
                    <h2 lang="ko">
                      {card.Korean}
                      {card.homonym && <sup>{card.homonym}</sup>}
                    </h2>
                    <p className="hanja">{card.Hanja || blank}</p>
                    {revealed ? (
                      <div className="card-answer">
                        <p>{card.Chinese || "中文释义暂缺"}</p>
                        <p className="muted">{card.English || blank}</p>
                        <p lang="ko">{card.Example || "例句暂缺"}</p>
                        <p className="muted">{card.Example_CN}</p>
                      </div>
                    ) : (
                      <button
                        className="reveal"
                        onClick={() => setRevealed(true)}
                      >
                        显示释义与例句
                      </button>
                    )}
                    <WordActions
                      word={card}
                      record={records[card.ID]}
                      onChange={update}
                    />
                    <button
                      className="text-button"
                      onClick={() => setSelected(card)}
                    >
                      完整词汇详情 ↗
                    </button>
                  </div>
                  <div className="card-controls">
                    <button
                      onClick={() => {
                        setCardIndex(
                          (i) => (i - 1 + results.length) % results.length,
                        );
                        setRevealed(false);
                      }}
                    >
                      上一个
                    </button>
                    <button
                      onClick={() => {
                        setCardIndex((i) =>
                          results.length > 1
                            ? (i +
                                1 +
                                Math.floor(
                                  Math.random() * (results.length - 1),
                                )) %
                              results.length
                            : 0,
                        );
                        setRevealed(false);
                      }}
                    >
                      随机单词
                    </button>
                    <button
                      onClick={() => {
                        setCardIndex((i) => (i + 1) % results.length);
                        setRevealed(false);
                      }}
                    >
                      下一个
                    </button>
                  </div>
                </section>
              ) : (
                <>
                  <div
                    className="table-scroll"
                    tabIndex={0}
                    role="region"
                    aria-label="词汇表，可横向滚动"
                  >
                    <table>
                      <thead>
                        <tr>
                          {columns.map(([key, label]) => (
                            <th
                              key={key}
                              aria-sort={
                                sort === key
                                  ? direction === 1
                                    ? "ascending"
                                    : "descending"
                                  : "none"
                              }
                            >
                              <button
                                onClick={() => {
                                  setSort(key);
                                  setDirection(
                                    sort === key && direction === 1 ? -1 : 1,
                                  );
                                  setPage(1);
                                }}
                              >
                                {label}
                                <span className="sort-arrow">
                                  {sort === key
                                    ? direction === 1
                                      ? "↑"
                                      : "↓"
                                    : "↕"}
                                </span>
                              </button>
                            </th>
                          ))}
                          <th>学习记录</th>
                        </tr>
                      </thead>
                      <tbody>
                        {paged.items.map((w) => (
                          <tr key={w.ID}>
                            <td>
                              <button
                                className="word-link"
                                lang="ko"
                                onClick={() => setSelected(w)}
                              >
                                {w.Korean}
                                {w.homonym && <sup>{w.homonym}</sup>}
                              </button>
                            </td>
                            <td className="hanja-cell">{w.Hanja || blank}</td>
                            <td>{w.Chinese || blank}</td>
                            <td className="english">{w.English || blank}</td>
                            <td className="nowrap">{w.POS}</td>
                            <td className="nowrap">
                              <span className="grade">{w.Level}</span>
                            </td>
                            <td className="nowrap muted">
                              {w.Word_Type || "未确认"}
                            </td>
                            <td lang="ko" className="muted">
                              {w.Pronunciation || "暂缺"}
                            </td>
                            <td>
                              <WordActions
                                word={w}
                                record={records[w.ID]}
                                onChange={update}
                              />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="pagination">
                    <label>
                      每页{" "}
                      <select
                        aria-label="每页条数"
                        value={size}
                        onChange={(e) => {
                          setSize(+e.target.value);
                          setPage(1);
                        }}
                      >
                        {[25, 50, 100].map((n) => (
                          <option key={n}>{n}</option>
                        ))}
                      </select>
                    </label>
                    <span>
                      第 {paged.current} / {paged.pages} 页
                    </span>
                    <div>
                      <button
                        disabled={paged.current === 1}
                        onClick={() => setPage(1)}
                      >
                        首页
                      </button>
                      <button
                        disabled={paged.current === 1}
                        onClick={() => setPage(paged.current - 1)}
                      >
                        上一页
                      </button>
                      <button
                        disabled={paged.current === paged.pages}
                        onClick={() => setPage(paged.current + 1)}
                      >
                        下一页
                      </button>
                      <button
                        disabled={paged.current === paged.pages}
                        onClick={() => setPage(paged.pages)}
                      >
                        末页
                      </button>
                    </div>
                  </div>
                </>
              )}
            </>
          )}
        </main>
        <footer>
          <p>
            官方 A / B / C 为词汇学习阶段，不等同于 TOPIK
            考试等级。标准发音暂缺；词源未确认不等于固有词。
          </p>
          <details>
            <summary>数据来源、许可与更新时间</summary>
            <p>
              词表：
              <a
                href="https://www.korean.go.kr/front/etcData/etcDataView.do?etc_seq=70&mn_id=46&pageIndex=1"
                target="_blank"
                rel="noreferrer"
              >
                国立国语院 2003 年《한국어 학습용 어휘 목록》
              </a>
              ，KOGL 第 1 类型（署名）。释义与例句：
              <a
                href="https://topikvocab.foldalpha.com/download/"
                target="_blank"
                rel="noreferrer"
              >
                Foldalpha
              </a>
              ，其网站允许用于学习；不代表官方译文或已获逐句核验。
            </p>
            <p>
              快照记录时间：
              {dataset
                ? new Date(dataset.updatedAt).toLocaleString("zh-CN")
                : "加载中"}
              。这是本项目快照时间，并非官方词表修订日期。词源分类根据原语规则推导；缺失值保持为空。
            </p>
            <p>
              本工具不收集学习记录；记录只保存在当前设备与浏览器。没有登录、云同步或合成发音。
            </p>
          </details>
        </footer>
      </div>
      {selected && (
        <Details
          key={selected.ID}
          word={selected}
          record={records[selected.ID]}
          onChange={update}
          onClose={() => setSelected(undefined)}
        />
      )}
    </>
  );
}
