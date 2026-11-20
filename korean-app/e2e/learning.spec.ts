import { test, expect } from "@playwright/test";
test("production subpath, search, records, import/export, cards and mobile", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/korean/");
  await expect(page.getByText("共 5,965 条词汇")).toBeVisible();
  await page.getByRole("button", { name: "下一页", exact: true }).click();
  await expect(page.getByText("第 2 / 239 页")).toBeVisible();
  await page.getByLabel("搜索词汇").fill("school");
  await page.getByLabel("官方分级", { exact: true }).selectOption("A");
  await page.getByLabel("词性", { exact: true }).selectOption("名词");
  await page.getByLabel("词汇类型", { exact: true }).selectOption("汉字词");
  await page.getByRole("button", { name: "학교", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('.hanja')).toHaveText('學校');
  await dialog.getByLabel("收藏 학교", { exact: true }).click();
  await dialog.getByLabel("학교 学习状态").selectOption("mastered");
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await page.reload();
  await page.getByRole('navigation', {name:'学习栏目'}).getByRole("button", { name: /^收藏/ }).click();
  await expect(page.getByText("共 1 条收藏词汇")).toBeVisible();
  await expect(page.getByLabel("학교 学习状态")).toHaveValue("mastered");
  await page.getByRole("button", { name: "单词卡片", exact: true }).click();
  await page.getByRole("button", { name: "显示释义与例句" }).click();
  await page.getByRole("button", { name: "随机单词" }).click();
  await expect(
    page.getByRole("button", { name: "显示释义与例句" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "学习统计" }).click();
  await expect(
    page.getByRole("progressbar", { name: "整体掌握进度" }),
  ).toHaveAttribute("value", "1");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出学习记录" }).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream!) chunks.push(chunk);
  const exported = JSON.parse(Buffer.concat(chunks).toString());
  expect(Object.keys(exported.records)).toHaveLength(1);
  const id = Object.keys(exported.records)[0];
  exported.records[id].status = "learning";
  exported.records[id].updatedAt = "2099-01-01T00:00:00Z";
  await page
    .getByLabel("导入学习记录文件")
    .setInputFiles({
      name: "records.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(exported)),
    });
  await expect(page.getByRole("status")).toContainText("已合并 1 条");
  await expect(
    page.getByRole("progressbar", { name: "整体掌握进度" }),
  ).toHaveAttribute("value", "0");
  await page
    .getByLabel("导入学习记录文件")
    .setInputFiles({
      name: "bad.json",
      mimeType: "application/json",
      buffer: Buffer.from('{"bad":true}'),
    });
  await expect(page.getByRole("status")).toContainText("不是有效");
  await page.getByRole("button", { name: "词汇库", exact: true }).click();
  await page.getByLabel("搜索词汇").fill("가구");
  await expect(page.getByRole("button", { name: "가구03" })).toBeVisible();
  await expect(page.getByRole("button", { name: "가구04" })).toBeVisible();
  await page.getByRole("button", { name: "重置筛选" }).click();
  await page.screenshot({ path: "test-results/desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel("搜索词汇")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "test-results/mobile.png" });
  await page.getByLabel("切换深色模式").click();
  await page.screenshot({ path: "test-results/mobile-dark.png" });
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(errors).toEqual([]);
});
