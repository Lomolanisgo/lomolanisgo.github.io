# 韩语学习网站 `/korean/`

这是现有 Jekyll 个人网站的独立静态子页面。React + TypeScript + Vite 仅用于该页面，其他页面继续使用现有 Liquid/Jekyll/Bootstrap。界面依据提供的参考图，沿用个人站的系统字体、深蓝强调色与简洁布局。未修改主页导航、其他页面布局或婚礼页同步流程。

## 开发与构建

推荐 **Node.js 24 LTS**（CI 使用 24），npm；依赖由 package-lock.json 固定。

```bash
cd korean-app
npm ci
npm run dev
# 打开 http://127.0.0.1:5173/korean/

npm run build
npm run preview
# 打开 http://127.0.0.1:4173/korean/
```

`build` 先生成数据、运行 TypeScript 检查，再将静态产物写入仓库根目录 `korean/`。它只清理该专用输出目录，不修改网站其他目录。不要手工编辑 `korean/`；它需要连同源代码一起提交。

## 架构

```text
vocabulary.json + provenance.json + data/raw/manifest.json
    → scripts/prepare-data.mjs
    → public/data/vocabulary.json（生成，不提交）
    → Vite build
    → ../korean/（提交到现有 Pages 发布分支）
```

- `src/model.ts`：检索、排序、分页、记录格式校验、合并及进度计算，独立于 UI。
- `src/components.tsx`：词条详情、收藏/状态控件、图标。
- `src/App.tsx`：四栏目、加载、筛选、卡片、记录导入导出与浏览器存储。
- `src/style.css`：独立样式，不会覆盖其他页面；系统韩文字体、响应式布局、浅/深色主题。
- `src/*.test.*`：基于完整真实数据的逻辑和组件测试。
- `e2e/learning.spec.ts`：对生产构建进行真实浏览器测试。

数据库生成与前端构建解耦：网站从已有 JSON 生成搜索文本，不调用原始数据网站，不重新抓取或编造词条。当前数据约 3.6 MB，gzip 约 640 KiB（实际网络压缩由静态托管服务决定）；应用 JS gzip 约 83 KiB。完整词表只请求一次；搜索索引构建一次，延迟更新查询，结果只渲染当前页。5,965 条数据不需要后端、数据库服务或网络搜索 API。

## 功能和行为

- 韩/汉/中/英跨字段搜索。NFKC 规范化只用于检索；显示内容保留原汉字字形。搜索包含匹配优先，无包含匹配时使用 Fuse.js 容错匹配（例如 `schoool`）。不支持简繁任意转换或中文拼音输入。
- 等级、词性、词源、学习状态可组合筛选；收藏栏目额外限定已收藏。卡片沿用筛选条件。
- 八个数据列可双向排序，25/50/100 条分页，首/末/上/下页，筛选更改后回到第一页。
- 详情显示全部请求字段、来源、原语说明及官方词典查询链接。同形词使用官方编号和稳定 ID 区分；词典链接是检索链接，不能假定不同词典编号相同。
- 当前标准发音及音频均缺失，明确显示“暂缺”。仅当未来数据真实提供官方 HTTPS `Audio_URL` 时显示播放器；不使用 TTS 冒充官方录音。
- 收藏、未学习/学习中/已掌握、卡片翻面、随机选词、整体和分级掌握进度。
- 移动端保留完整表格，表格内部可横向滚动；页面本身不横向溢出。使用键盘可操作的按钮/选择框、原生模态框、Escape 关闭和焦点恢复。

## 学习记录

localStorage 键：`korean.learning.v1`。主题另存 `korean.theme`，首次跟随系统。

```json
{
  "schemaVersion": 1,
  "exportedAt": "ISO-8601 时间",
  "records": {
    "NIKL2003-稳定哈希": {
      "favorite": true,
      "status": "learning",
      "updatedAt": "ISO-8601 时间"
    }
  }
}
```

“学习统计”中导入/导出 JSON，最大导入 5 MB。校验整个文件后才写入；同 ID 按更新时间保留较新的记录，未出现在当前数据库中的合法旧 ID 保留备份但不计入统计。未知版本/无效状态/日期/ID 会拒绝整个文件。跨标签页使用 storage 事件同步。存储受限或配额不足时显示提示，并允许导出内存中的记录。

无需登录，无云同步，也不上传学习记录。浏览器清理、换设备或更换域名不会自动迁移数据，需手工导出/导入。用户手动将设备时钟设置到未来可能影响合并顺序。

## 数据准确性与更新

官方旧表完整 5,965 条，A/B/C 982/2,111/2,872。没有 TOPIK 等级换算。中英文释义及例句属于第三方补充；原语缺失不能推出固有词。页面底部和详情注明来源、许可及快照时间，不把快照时间当官方修订日期。详细核验与缺失统计见仓库根目录 README 和 quality_report.json。

使用现有数据库更新前端：

```bash
# 仓库根目录，若已有新的 vocabulary.json，只需后两步
python3 main.py
cd korean-app
npm run build
npm test
```

只有明确希望更新原始快照时才运行 `python3 main.py --download`，随后核查根目录 validation_report.json 和 quality_report.json。前端构建不联网更新词表；新增词条必须有稳定唯一 ID 和 provenance。未来定时数据更新任务可在数据核验成功后复用同一 `npm run build`，不必修改 UI。

## 测试

```bash
npm run data
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

测试包括真实数据的多语搜索、模糊搜索、组合筛选、分级数量、分页边界、排序、同形词、记录格式校验/合并、持久化、详情、卡片、统计、生产子路径、导入导出、错误文件拒绝、深色模式和 390px 手机布局。截图输出到被忽略的 test-results/。已有兼容 Chromium 时可用 `PLAYWRIGHT_EXECUTABLE_PATH=/path/to/chromium npm run test:e2e`。

## 部署到现有域名

`vite.config.ts` 固定 `base: '/korean/'`，所有应用 JS/CSS/数据请求均在该子路径。栏目使用页面状态，不引入需要服务器回退的 history 路由。`/korean/` 刷新直接加载 `korean/index.html`。

本仓库现有配置为根域名 Jekyll/GitHub Pages，未迁移托管平台，也未添加会覆盖整站的部署任务。部署操作：

```bash
cd korean-app
npm ci
npm run build
npm test
npm run test:e2e
cd ..
git add korean-app korean .github/workflows/check-korean.yml _config.yml .gitignore README.md
# 首次部署还需一起提交根目录词汇数据与 provenance、manifest 等数据项目文件。
git commit -m "Add Korean vocabulary learning page"
git push
```

提交到当前 GitHub Pages 使用的发布分支，沿用已有部署设置；最终地址为同一域名的 `/korean/`。仓库配置的域名是 `https://lomolanisgo.github.io`，若 Pages 已绑定其他自定义域名则沿用该域名。发布后可访问 `https://lomolanisgo.github.io/korean/`；部署结果以 GitHub Pages workflow 和线上检查为准。

`_config.yml` 只新增排除项，避免把前端源码、node_modules 及原始数据快照复制到 Jekyll 输出中。新增 `check-korean.yml` 在相关文件变更时构建、测试并检查提交的 `korean/` 是否最新，不改动现有婚礼页 workflow，不改变 Pages 设置。若将来迁移到有仓库前缀的域名（非根域名），需同时调整 Vite base、首页及 favicon 链接。
