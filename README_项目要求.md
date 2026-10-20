# Secondhand EC Agent  

## 1. 技术栈
| 部分 | 技术 |
|---|---|
| 操作系统 | Windows 10 / 11 x64 |
| 编程语言 | Python 3.11 或 3.12 |
| 本地服务 | Flask |
| 数据库 | SQLite |
| 环境变量 | python-dotenv |
| 浏览器自动化 | Automa（Chrome / Edge 扩展） |
| AI | DeepSeek API |
---
## 2. 项目目录结构
项目根目录建议：
```text
D:\PROJECTS\SecondhandECAgent
```
完整结构：
```text
SecondhandECAgent/
├─ start.bat                  # 启动本地服务
├─ build.bat                  # 打包成 Windows 便携版
├─ requirements.txt           # Python 依赖
├─ README_项目要求.md          # 本文档
├─ config/
│  ├─ secrets.env.example     # 配置模板
│  └─ secrets.env             # 你实际填密钥的文件，不要外传
├─ app/
│  ├─ __init__.py             # 空文件
│  ├─ main.py                 # Flask 主程序
│  ├─ config.py               # 读取 secrets.env
│  ├─ db.py                   # SQLite 初始化与连接
│  ├─ camera_import.py        # GF9 照片导入
│  ├─ price_engine.py         # 价格修正规则
│  └─ mercari_client.py       # 占位，个人卖家版不使用官方 API
├─ data/
│  └─ app.db                  # SQLite 数据库
├─ images/
│  └─ imported/               # 从相机导入的照片
└─ logs/
```
---
## 4. 环境准备（新电脑复刻步骤）
### 4.1 安装 Python
1. 访问 `https://www.python.org/downloads/`
2. 下载 **Python 3.11.x 或 3.12.x**，不要用 3.13。
3. 安装时**必须勾选**：
   ```text
   Add python.exe to PATH
   ```
4. 安装完成后，打开 `cmd`，验证：
   ```cmd
   python --version
   pip --version
   ```
   都能显示版本号即可。
如果已装过 Python 但仍报 `Python was not found`，去：
```text
设置 → 应用 → 高级应用设置 → 应用执行别名
```
关闭 `python.exe` 和 `python3.exe` 的别名开关。
### 4.2 安装浏览器与 Automa
1. 安装 Chrome 或 Edge。
2. 在扩展商店搜索 **Automa**，安装。
3. 在 `chrome://extensions` 中，找到 Automa → 详情 → 开启：
   ```text
   允许访问文件网址
   ```
### 4.3 注册 DeepSeek（可选，AI 功能）
1. 访问 `https://platform.deepseek.com` 注册并登录。
2. 创建 API Key 并复制。
3. 在 `config/secrets.env` 中填入：
   ```env
   DEEPSEEK_ENABLED=true
   DEEPSEEK_API_KEY=你的Key
   ```
   DeepSeek 未配置时 AI 功能不开启，价格诊断会使用默认参考价。
### 4.4 准备 Mercari 账号
个人卖家账号即可，不需要 Mercari Shops API。  
Automa 将模拟人工操作网页。
---
## 5. 配置文件 `config/secrets.env`
把 `config/secrets.env.example` 复制为 `config/secrets.env`，然后填写：
```env
# ========== Mercari Shops（个人卖家版可留空，不使用官方 API） ==========
MERCARI_ENV=production
MERCARI_ACCESS_TOKEN=
MERCARI_SHOP_ID=
MERCARI_BASE_URL=https://api.mercari-shops.com
# ========== 相机 Lumix GF9 USB 存储模式 ==========
CAMERA_MODE=usb_storage
CAMERA_AUTO_DETECT=true
CAMERA_DRIVE=auto
CAMERA_DCIM_SUBDIR=DCIM
CAMERA_IMPORT_DIR=./images/imported
CAMERA_JPEG_QUALITY=85
CAMERA_MAX_LONG_EDGE=2000
# ========== DeepSeek API（可选，默认关闭） ==========
DEEPSEEK_ENABLED=false
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
# ========== 本地服务 ==========
APP_HOST=127.0.0.1
APP_PORT=8765
```
⚠️ **密钥只填 `secrets.env`，不要填 `start.bat`，不要上传 GitHub。**
---
## 6. Python 依赖 `requirements.txt`
```txt
flask==3.0.3
python-dotenv==1.0.1
requests==2.32.3
Pillow==12.0.0
pyinstaller==6.22.3
```

注：原固定版本 Pillow==10.4.0 / pyinstaller==6.10.0 仅支持 Python ≤ 3.13；本仓库改为 3.14 兼容版本（在 3.11/3.12 上同样可用）。
安装命令：
```cmd
pip install -r requirements.txt
```
---
## 7. Python 模块功能要求
### 7.1 `app/config.py`
- 读取 `config/secrets.env`
- 提供 `Config` 类，包含 Mercari、相机、DeepSeek、本地服务配置
- `Config.check_ready()` 检查关键配置是否缺失
### 7.2 `app/db.py`
- 初始化 SQLite 数据库 `data/app.db`
- 表 `photos`：保存导入照片的本地路径、文件哈希、商品 ID
- 表 `products`：保存商品标题、价格、状态、描述、Mercari ID
- 提供 `get_db()` 返回可像字典访问的行
### 7.3 `app/camera_import.py`
- 自动查找相机盘符：遍历盘符，找存在 `DCIM` 的盘
- 扫描 `DCIM` 下所有 `.JPG` / `.JPEG`
- 用 MD5 去重，已导入的跳过
- 用 Pillow 自动旋转、转 RGB、压缩到长边 2000px、质量 85
- 保存到 `images/imported/`
- 写入 `photos` 表
- **按文件名自动分组**：文件名「N.M.jpg」（N=商品号，M=张号）的照片，导入时同 N 自动归为同一商品
  （全局连续编号），自动创建/关联**草稿商品**（标题占位「商品 N」、价格 0、`is_draft=1`）并挂接照片；
  不匹配命名的照片（如相机默认 `P1000001.JPG`）不分组、不建商品
- 返回 `{status, imported, photos, products, blocked}`
- **保护规则**：商品已转正式（`is_draft=0`）后，同 N 的新照片**不再自动并入**（进入 `blocked` 列表），
  需要时通过 `PUT /api/products/<id>` 传 `photo_ids` 显式并入
### 7.4 `app/price_engine.py`
- 根据 Mercari 商品状态和附件计算推荐价格区间
- 状态系数：
  ```text
  BRAND_NEW 1.00
  ALMOST_NEW 0.95
  CLEAN 0.90
  LITTLE_DIRTY 0.85
  DIRTY 0.75
  BAD 0.60
  ```
- 附件加分：箱子 +0.05，说明书 +0.02，充电器 +0.03，其他配件 +0.02
- 返回 `{low, center, high, multiplier}`
### 7.5 `app/main.py`
提供本地 HTTP 接口：
| 接口 | 方法 | 功能 |
|---|---|---|
| `/` | GET | 简单状态页面 |
| `/api/import_photos` | POST | 导入相机照片 |
| `/api/calculate_price` | POST | 测试价格计算 |
| `/api/products` | GET | 返回**已完善**商品列表（草稿除外），供 Automa 读取 |
| `/api/products/<id>` | PUT | 更新商品并**自动转正式**（草稿在此完善标题/价格/描述）；可传 `photo_ids` 显式并入照片 |
| `/api/products/<id>` | DELETE | 删除商品（照片保留，解除关联） |
| `/api/drafts` | GET | 草稿商品列表（文件名分组自动生成），含照片数与下一个可用商品号 |
`/api/products` 返回 `{"data": [...]}`，每项包含：
```json
{
  "id": 1,
  "product_no": 1,
  "title": "商品标题",
  "price": 29800,
  "status": "CLEAN",
  "description": "商品描述",
  "images": [
    "D:\\PROJECTS\\SecondhandECAgent\\images\\imported\\xxxx.jpg"
  ],
  "image_paths": [
    "D:\\PROJECTS\\SecondhandECAgent\\images\\imported\\xxxx.jpg"
  ],
  "categories": ["レディース", "トップス", "Tシャツ/カットソー"]
}
```
分类说明：`categories` 为数组（大类→中类→小类），Automa 逐级点选用；POST/PUT 可传数组或字符串
`"レディース > トップス > Tシャツ/カットソー"`（`>` 分隔自动拆分）。
```
### 7.6 `app/mercari_client.py`
个人卖家版**不使用官方 API**，此文件仅作占位。  
Automa 负责网页自动化，不需要真实 Mercari API 调用。
---
## 8. 相机使用要求（Lumix GF9）
1. GF9 不支持 USB 联机拍摄，只能用手动拍照。
2. 相机菜单设置 USB 模式为：
   ```text
   PC(Storage) / 存储模式
   ```
3. 拍照格式建议 JPEG；如果拍 RAW+JPEG，程序只导入 JPG。
4. 拍完用 USB 线连接电脑。
5. Windows 识别为可移动磁盘，程序自动扫描 `DCIM`。
6. 导入后照片保存在 `images/imported/`。
7. **推荐命名**：导入前把照片改名为「商品号.张号.JPG」（如 `1.1.JPG`、`1.2.JPG`、`1.3.JPG` 属于商品 1，
   `2.1.JPG`、`2.2.JPG` 属于商品 2），同商品号自动归为一组并生成草稿商品；
   不匹配规则的照片（相机默认命名）不分组。
8. **批量改名工具**：把一组照片拖到项目根目录 `rename_photos.bat` 上，输入商品号 N，
   自动按文件名排序改名为 `N.1.jpg`、`N.2.jpg` ...；已是「N.M」命名、非 JPG、目标已存在的文件会跳过。
9. 如果自动检测失败，在 `secrets.env` 中设：
   ```env
   CAMERA_DRIVE=E:\
   ```
---
## 9. Automa 工作流要求
### 9.1 工作流结构
```text
[HTTP 请求]  GET http://127.0.0.1:8765/api/products
   ↓
[循环数据]  循环 ID: item，遍历 {{ products.data }}
   ↓
[新建标签页] https://jp.mercari.com/sell
   ↓
[表单] 填写商品标题 → {{ item.title }}
   ↓
[表单] 填写价格 → {{ item.price }}
   ↓
[表单] 填写描述 → {{ item.description }}
   ↓
[上传文件] 上传图片 → {{ item.images[0] }} 等
   ↓
[点击元素] 点击“出品する”
   ↓
[延迟] 随机 2000-3000 毫秒
   ↓
[循环断点]
```
### 9.2 配置要点
- `HTTP 请求`：
  - Method: `GET`
  - URL: `http://127.0.0.1:8765/api/products`
  - 响应类型: `JSON`
  - 勾选“将响应分配给变量”，变量名 `products`
- `循环数据`：
  - 循环 ID：`item`
  - 遍历数据：`{{ products.data }}`
- `新建标签页`：
  - URL: `https://jp.mercari.com/sell`
- `表单`：
  - 点击十字准星，去 Mercari 页面点选输入框
  - 值手动输入 `{{ item.title }}`、`{{ item.price }}`、`{{ item.description }}`
- `分类（必填，Mercari 是三级动态选择）`：
  - 录制时手动选一次分类（大类 → 中类 → 小类），录制结果为三个点击块
  - 三个点击块的文本值依次改为 `{{ item.categories[0] }}`、`{{ item.categories[1] }}`、`{{ item.categories[2] }}`
  - 每个点击块之间加 `延迟` 500-1000 毫秒，等分类列表异步加载
- `上传文件`：
  - 选择图片上传控件
  - 文件路径填 `{{ item.image_paths[0] }}`（本地路径；第二张用 `[1]`，依此类推）
  - 必须开启 Automa 的“允许访问文件网址”
- `点击元素`：
  - 选择“出品する”按钮
- `延迟`：
  - 2000-3000 毫秒随机
### 9.3 风险控制
- Mercari 禁止自动化批量出品。
- 必须**人工确认后提交**，不要全自动无人值守。
- 每小时最多 2-3 件，随机间隔。
- 不要短时间内大量提交，避免账号被封。
- 页面结构更新后，选择器可能失效，需要重新抓取。
---
## 10. 启动与打包
### 10.1 启动
双击 `start.bat`。  
如果 `config/secrets.env` 不存在，会自动生成并提示填写。  
填好后再次双击，浏览器打开：
```text
http://127.0.0.1:8765
```
### 10.2 打包成 Windows 便携版
在开发电脑上运行：
```cmd
build.bat
```
生成：
```text
dist\SecondhandECAgent\
```
把这个文件夹整个复制到新电脑，修改 `config/secrets.env`，双击 `start.bat` 即可。
---
## 11. 复刻验收清单
- [ ] Windows 10/11 已安装 Python 3.11/3.12，并勾选 Add to PATH
- [ ] `pip install -r requirements.txt` 成功
- [ ] `config/secrets.env` 已填写，且未外传
- [ ] 双击 `start.bat` 能启动 Flask，访问 `http://127.0.0.1:8765`
- [ ] GF9 设为 PC(Storage)，USB 连接后程序能扫描到 DCIM
- [ ] 导入照片后，`images/imported/` 有压缩后的 JPG
- [ ] SQLite `products` 表中有测试商品数据
- [ ] `/api/products` 返回正确 JSON
- [ ] Automa 已安装，允许访问文件网址
- [ ] Automa 工作流能读取 `/api/products`
- [ ] Automa 能在 Mercari 出品页填写标题、价格、描述
- [ ] 图片上传测试成功
- [ ] 人工确认后提交，账号无异常
---
## 12. 当前已知限制
1. 个人卖家无法使用 Mercari Shops 官方 API，所以放弃 API 自动上架，改用 Automa。
2. Automa 自动化违反 Mercari 服务条款，有账号风险，必须人工确认、低频操作。
3. GF9 不支持 USB 联机拍摄，只能手动拍完再连接电脑导入。
4. 项目中的 `mercari_client.py` 仅为占位，个人卖家版不调用。
---
## 13. 下一步建议
1. 先在新电脑安装 Python 3.11/3.12。
2. 建好 `D:\PROJECTS\SecondhandECAgent` 目录结构。
3. 填好 `config/secrets.env`。
4. 运行 `pip install -r requirements.txt`。
5. 双击 `start.bat`，确认 `http://127.0.0.1:8765/api/products` 能打开。
6. 再配置 Automa 工作流，先测试填写一个标题。
7. 成功后再加价格、描述、图片上传。
8. 最后人工确认提交，控制频率。
---
这份文档就是复刻标准。  
你之后换电脑、重装系统，或者让别人帮你做，都按这份要求执行即可。
