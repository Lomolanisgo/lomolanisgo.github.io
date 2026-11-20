// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { readFileSync } from "node:fs";
import App from "./App";
const dataset = JSON.parse(
  readFileSync(process.cwd() + "/public/data/vocabulary.json", "utf8"),
);
beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => dataset }),
  );
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("searches, combines filters, paginates and opens a homograph detail", async () => {
  render(<App />);
  await screen.findByText("共 5,965 条词汇");
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(screen.getByText("第 2 / 239 页")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("搜索词汇"), {
    target: { value: "학교" },
  });
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "학교" })).toBeInTheDocument(),
  );
  fireEvent.change(screen.getByLabelText("官方分级"), {
    target: { value: "A" },
  });
  fireEvent.change(screen.getByLabelText("词性"), {
    target: { value: "名词" },
  });
  fireEvent.change(screen.getByLabelText("词汇类型"), {
    target: { value: "汉字词" },
  });
  fireEvent.click(screen.getByRole("button", { name: "학교" }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(screen.getByText("官方标准发音暂缺")).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("关闭词汇详情"));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
it("persists favorites and statuses, displays cards and statistics", async () => {
  const { unmount } = render(<App />);
  await screen.findByText("共 5,965 条词汇");
  fireEvent.click(screen.getByLabelText("收藏 가게"));
  fireEvent.change(screen.getByLabelText("가게 学习状态"), {
    target: { value: "mastered" },
  });
  await waitFor(() =>
    expect(localStorage.getItem("korean.learning.v1")).toContain("mastered"),
  );
  fireEvent.click(screen.getByRole("button", { name: "单词卡片" }));
  fireEvent.click(screen.getByRole("button", { name: "显示释义与例句" }));
  expect(
    screen.getByRole("button", { name: "完整词汇详情 ↗" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "学习统计" }));
  expect(
    screen.getByRole("progressbar", { name: "整体掌握进度" }),
  ).toHaveAttribute("value", "1");
  unmount();
  render(<App />);
  await screen.findByText("共 5,965 条词汇");
  expect(screen.getByLabelText("取消收藏 가게")).toBeInTheDocument();
});
it("shows an actionable network failure", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("无法加载");
  expect(screen.getByRole("button", { name: "重新加载" })).toBeInTheDocument();
});
