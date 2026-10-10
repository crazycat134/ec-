# Secondhand EC Agent V3

> 个人卖家二手商品上架辅助系统 — 拍照导入 → AI 生成描述 → Automa 半自动上架 Mercari

## ✨ 功能特性

- 📷 **相机自动导入**：Lumix GF9 USB 连接后自动扫描 DCIM、去重、压缩
- 💰 **AI 价格诊断**：输入品牌+型号，AI 查 Amazon/楽天/メルカリ/Yahoo! 多平台价格，状态/附属品联动滑块定价
- 📝 **AI 商品描述**：DeepSeek 自动生成日文商品说明文（含商品介绍/状态/附件/动作确认）
- ✅ **动作确认 Checklist**：AI 生成标准检查清单，逐项打勾
- 📋 **批量操作**：多选商品，批量确认/删除
- 🤖 **Automa 集成**：本地 API 提供商品数据，Automa 浏览器扩展半自动填表

## 🏗️ 技术栈

| 组件 | 技术 |
|---|---|
| 后端 | Python 3.11+ / Flask |
| 数据库 | SQLite |
| 图片处理 | Pillow |
| AI | DeepSeek API |
| 浏览器自动化 | Automa (Chrome 扩展) |

## 📁 项目结构

```
SecondhandECAgent/
├── app/
│   ├── main.py              # Flask 主程序（所有 API）
│   ├── config.py             # 读取配置
│   ├── db.py                # SQLite 数据库
│   ├── deepseek_client.py  # DeepSeek AI 客户端
│   ├── camera_import.py      # 相机照片导入
│   ├── price_engine.py       # 价格计算引擎
│   └── templates/
│       └── index.html        # 状态页（Web UI）
├── config/
│   ├── secrets.env.example   # 配置模板
│   └── secrets.env          # 你的密钥（不要上传）
├── data/
│   └── app.db               # SQLite 数据库
├── images/
│   └── imported/            # 导入的照片
├── requirements.txt
├── run.py                   # 启动入口
└── test_system.py           # 系统测试脚本
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装 Python 3.11 或 3.12（不要用 3.13）
# 安装依赖
pip install -r requirements.txt
```

### 2. 配置密钥

```bash
# 复制模板
cp config/secrets.env.example config/secrets.env

# 编辑 config/secrets.env，填入你的密钥
```

需要配置的内容：

#### DeepSeek API（AI 功能，可选）
- 注册 https://platform.deepseek.com
- 创建 API Key
- `DEEPSEEK_ENABLED=true`
- `DEEPSEEK_API_KEY=你的key`

### 3. 启动

```bash
python run.py
```

打开浏览器访问：http://127.0.0.1:8765

## 📡 API 接口

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/products` | GET | 获取已确认商品列表（供 Automa 读取） |
| `/api/products?all=1` | GET | 获取所有商品（状态页用） |
| `/api/products` | POST | 创建商品 |
| `/api/products/<id>` | PUT | 更新商品 |
| `/api/products/<id>` | DELETE | 删除商品 |
| `/api/drafts` | GET | 获取草稿列表 |
| `/api/calculate_price` | POST | 计算推荐价格 |
| `/api/suggest_price` | POST | AI 查各平台价格（新品/中古 + 状态/附属品选项） |
| `/api/generate_description` | POST | AI 生成商品描述 |
| `/api/generate_checklist` | POST | AI 生成检查清单 |
| `/api/import_photos` | POST | 导入相机照片 |

## 🤖 Automa 工作流

Automa 是 Chrome/Edge 的浏览器自动化扩展。

### 工作流结构
```
[HTTP 请求] GET http://127.0.0.1:8765/api/products
    ↓
[循环数据] 遍历商品列表
    ↓
[新建标签页] https://jp.mercari.com/sell
    ↓
[表单] 填写标题 / 价格 / 描述
    ↓
[点击] 选择分类 / 状态
    ↓
[上传文件] 上传商品图片
    ↓
[延迟] 随机 2-3 秒
    ↓
（人工确认后提交）
```

### ⚠️ 风险提示
- Mercari 禁止自动化批量操作，有账号风险
- 必须人工确认后提交，不要无人值守
- 每小时最多 2-3 件，随机间隔

## 🧪 测试

```bash
python test_system.py
```

## 📝 License

个人项目，仅供学习参考。使用风险自负。

## 🙏 致谢

- [DeepSeek](https://www.deepseek.com/) - AI 大模型
- [Automa](https://www.automa.site/) - 浏览器自动化
