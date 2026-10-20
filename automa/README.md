# Automa 上架 / 删除工作流对接说明

本目录提供与项目配套的 **Automa 浏览器扩展** 工作流，实现「从本系统读取已确认商品 → 自动在メルカリ填写并保存草稿」「自动删除メルカリ草稿」。

## 文件

| 文件 | 说明 |
|---|---|
| `mercari_listing.automa.json` | 修复版工作流（**推荐导入这个**）：已补全 trigger 起点与上架分类链连线，可直接运行 |
| `mercari_listing_original.automa.json` | 你的原始导出（备份），连线不完整（trigger 未连线、分类链未接主线） |

## 导入方法

1. 打开 Automa 扩展 → 左侧「工作流」列表
2. 右上角 `⋮` / 导入按钮 → 选择 `mercari_listing.automa.json`
3. 导入后进入工作流，点右上角「运行」即可执行上架流程

> 工作流通过 `http://127.0.0.1:8765/api/products` 读取商品，请先启动本系统（`run.py`）。

## 上架流程（主链）

```
手动触发 → GET /api/products（只返回 confirmed=1 的已确认商品）
→ 循环逐件（最多 10 件）：
   1. 打开 https://jp.mercari.com/sell/create
   2. 等待 2 秒（页面加载）
   3. 自动填写：标题(title) / 描述(description) / 价格(price)
      - 用 React 原生 setter 赋值 + input/change/blur 事件，兼容メルカリ表单
   4. 逐级点击分类（最多 6 级，来自商品的 categories 数组）：
      categories[0] → [1] → [2] → …（只点存在的级别）
   5. 确认分类选择
   6. 点击「保存草稿」按钮（save-draft）
   7. 进入下一件商品
```

- 商品数据契约（`/api/products` → `{data:[...]}`）：
  `title`（标题）、`description`（描述）、`price`（整数价格）、`categories`（分类字符串数组，如 `["本・雑誌・漫画","漫画","少年漫画"]`）
- 商品必须先在前端勾选 → 「✓ 批量确认」（或单件确认），`confirmed=1` 后才会被工作流读取。

## 删除流程（草稿清理）

1. 在 Automa 工作流中，**右键 `new-tab` 块（打开草稿页）→ 从此处运行**
2. 打开 https://jp.mercari.com/mypage/drafts
3. 循环（最多 10 次）：
   - 等待草稿列表出现 → 跳转到第一件草稿详情页
   - 点击「删除草稿」按钮 → 点击「削除する」确认
   - 跳回草稿列表，处理下一件
4. 已删除 10 件后自动停止（sessionStorage 计数）

## 本次修复点（相对你的原始导出）

| 问题 | 修复 |
|---|---|
| trigger 未连线，手动运行无法启动 | 补 `trigger → webhook` 边 |
| 填表后直接保存草稿，分类链未接入主线 | 补 `填表 → 第一级分类`、`末级分类 → 确认分类`、`确认分类 → 保存草稿延迟` 三条边；移除 `填表 → 保存草稿延迟` 直连边 |

## 注意事项

- **图片上传**：当前工作流不包含图片上传块。当前应用版本已移除相机照片导入功能，因此只有数据库中已有照片关联的商品才会返回本地图片路径；如需上传此类图片，可在 Automa 中配置「文件上传」块。
- **循环次数可配置**：上架和删除的循环次数都由 `loop-data` 块控制，想处理几件就设几：
  - 上架流程（变量循环）：`loop-data` 块的 `maxLoop`（当前 10）= 一次上架处理的商品件数
  - 删除流程（数字循环）：`loop-data` 块的 `toNumber`（当前 10）= 一次删除的草稿件数
- **分类必须存在于商品数据**：商品没有 `categories` 时分类步骤会跳过，草稿保存后需手动补分类。
- 有 1 个被禁用的「勾选 checkbox」块（`m0ep5u6`，原设计勾选某项选项），保留未启用；如需启用，在 Automa 中打开该块并取消禁用。
- 若メルカリ页面改版导致选择器失效，需要更新对应块的 selector：
  - 标题/描述/价格：`input[name="name"]` / `textarea[name="description"]` / `input[name="price"]`
  - 分类确认：`[data-testid="category-link"] .mer-spacing-y-8`
  - 保存草稿：`button[data-testid="save-draft"]`
  - 草稿项：`a[data-testid="draft-item"]`
  - 删除按钮：`[data-testid="delete-draft"] button`
  - 删除确认：文本为「削除する」的按钮
