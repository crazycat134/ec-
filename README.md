# Secondhand EC Agent V3

本项目是本地二手商品上架工作流：输入品牌和型号 → AI 估算新品/中古推荐价 → 生成日文商品描述 → 人工确认后由 Automa 读取并填写 Mercari 页面。使用 Python/Flask 提供网页和 API，SQLite 保存商品资料，DeepSeek 可选地辅助价格诊断和描述生成。

## 当前功能
- AI 价格诊断：输入品牌和型号，参考 Amazon・楽天・メルカリ・Yahoo! 的行情估算新品/中古推荐价，保存为商品资料
- 可选 DeepSeek AI：生成日文商品描述（人工确认后保存）
- 本地商品资料新增、编辑、删除、分类和确认状态管理
- 本地 API 供 Automa 读取已确认商品并自动上架
- Windows 源码启动与便携版打包

## 当前版本不包含
- USB 相机或存储盘自动扫描、DCIM 照片导入
- 按文件名分组照片并自动创建草稿
- `rename_photos.bat` 批量重命名工具
- 直接抓取电商平台实时价格或通过 Mercari 官方 API 发布商品

相机导入和批量重命名已从当前版本移除。数据库中已有的照片关联不会因这次调整而自动删除，但当前版本没有新的相机导入入口。

## 环境与启动
建议使用 Windows + Python 3.11/3.12。双击 `start.bat`，首次运行会从 `config/secrets.env.example` 创建 `config/secrets.env`，然后按提示再次启动。AI 为可选功能；如需使用，请设置 `DEEPSEEK_ENABLED=true` 并填写 `DEEPSEEK_API_KEY`。默认页面地址为 `http://127.0.0.1:8765`。

## 主要 API

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/` | 商品管理页面 |
| GET | `/api/products` | 获取已确认的正式商品 |
| GET | `/api/products?all=1` | 获取全部商品记录（含旧版本草稿） |
| POST | `/api/products` | 新增商品 |
| PUT | `/api/products/<id>` | 更新商品 |
| DELETE | `/api/products/<id>` | 删除商品记录 |
| POST | `/api/suggest_price` | AI 价格诊断（品牌+型号 → 四平台参考价） |
| POST | `/api/generate_description` | AI 生成日文商品描述 |

当前版本不再提供 `/api/import_photos`、`/api/drafts`、`/api/calculate_price` 或 `/api/generate_checklist`。商品接口返回 `{"data": [...]}`，并包含已有照片路径（如数据库中存在关联）。

## 测试与打包
运行 `python test_system.py` 执行轻量测试。在 Windows 开发环境中运行 `build.bat`，便携版输出到 `dist/SecondhandECAgent/`。本次修改未在 Windows 实机运行打包或验证 Mercari 页面自动化。

## 注意事项
- Automa 的网页操作可能受到 Mercari 平台规则限制；发布前应人工核对并确认。
- 不要把真实 API Key 提交到 GitHub。
- 本地数据库位于 `data/app.db`，日志位于 `logs/`。
