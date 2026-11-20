import { useEffect, useRef } from "react";
import type { RecordEntry, Status, Word } from "./model";
import { officialAudio, statusNames } from "./model";
export function Icon({ name }: { name: "book" | "moon" | "sun" | "search" }) {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {name === "book" ? (
        <>
          <path d="M12 6c-3-2-6-3-10-2v15c4-1 7 0 10 2 3-2 6-3 10-2V4c-4-1-7 0-10 2Z" />
          <path d="M12 6v15" />
        </>
      ) : name === "moon" ? (
        <path d="M20 15A9 9 0 0 1 9 3a9 9 0 1 0 11 12Z" />
      ) : name === "search" ? (
        <>
          <circle cx="10" cy="10" r="7" />
          <path d="m15 15 6 6" />
        </>
      ) : (
        <>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2" />
        </>
      )}
    </svg>
  );
}
export function WordActions({
  word,
  record,
  onChange,
}: {
  word: Word;
  record?: RecordEntry;
  onChange: (id: string, patch: Partial<RecordEntry>) => void;
}) {
  return (
    <div className="word-actions">
      <button
        className={"favorite " + (record?.favorite ? "selected" : "")}
        aria-label={`${record?.favorite ? "取消收藏" : "收藏"} ${word.Korean}`}
        aria-pressed={!!record?.favorite}
        onClick={() => onChange(word.ID, { favorite: !record?.favorite })}
      >
        {record?.favorite ? "★" : "☆"}
      </button>
      <select
        aria-label={`${word.Korean} 学习状态`}
        value={record?.status || "new"}
        onChange={(e) =>
          onChange(word.ID, { status: e.target.value as Status })
        }
      >
        {Object.entries(statusNames).map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </div>
  );
}
export function Details({
  word,
  record,
  onChange,
  onClose,
}: {
  word: Word;
  record?: RecordEntry;
  onChange: (id: string, patch: Partial<RecordEntry>) => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    ref.current?.showModal();
    return () => previous?.focus();
  }, []);
  const audio = officialAudio(word.Audio_URL);
  return (
    <dialog
      ref={ref}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      aria-labelledby="word-title"
    >
      <div className="dialog-header">
        <span className="eyebrow">词汇详情 · {word.ID}</span>
        <button onClick={onClose} aria-label="关闭词汇详情">
          ✕
        </button>
      </div>
      <h2 id="word-title" lang="ko">
        {word.Korean}
        {word.homonym && <sup title="官方同音词编号">{word.homonym}</sup>}
      </h2>
      <p className="hanja">{word.Hanja || "未提供汉字"}</p>
      <div className="meta">
        {word.POS} · {word.Level} · {word.Word_Type || "词源未确认"}
      </div>
      <WordActions word={word} record={record} onChange={onChange} />
      <dl>
        <dt>中文释义</dt>
        <dd>{word.Chinese || "未提供"}</dd>
        <dt>英文释义</dt>
        <dd>{word.English || "未提供"}</dd>
        <dt>标准发音</dt>
        <dd lang="ko">{word.Pronunciation || "官方标准发音暂缺"}</dd>
        {audio && (
          <dd>
            <audio controls preload="none" src={audio} aria-label="官方发音" />
          </dd>
        )}
        <dt>韩语例句</dt>
        <dd lang="ko">{word.Example || "未提供"}</dd>
        <dt>中文翻译</dt>
        <dd>{word.Example_CN || "未提供"}</dd>
        <dt>官方原语／说明</dt>
        <dd>{word.originNote || "未标注"}</dd>
      </dl>
      <div className="source-note">
        <p>
          释义与例句为第三方补充，未逐句获官方核验。官方词表编号与基础词典编号不通用，请在词典中核对义项。
        </p>
        <a
          href={`https://krdict.korean.go.kr/chn/dicSearch/search?nation=chn&mainSearchWord=${encodeURIComponent(word.Korean)}`}
          target="_blank"
          rel="noreferrer"
        >
          在韩国语基础词典查询 ↗
        </a>
        <p>
          词条来源：
          {word.source.split(" ; ").map((s, i) => {
            const match = s.match(/https:\/\/\S+/);
            return match ? (
              <a key={s} href={match[0]} target="_blank" rel="noreferrer">
                {i ? "第三方释义与例句 ↗" : "国立国语院词表 ↗"}{" "}
              </a>
            ) : (
              s
            );
          })}
        </p>
      </div>
    </dialog>
  );
}
