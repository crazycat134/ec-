============================================
 Secondhand EC Agent V3 个人卖家复刻版 · 启动说明
============================================

一、首次使用（新电脑）
1. 安装 Python 3.11 或 3.12（安装时勾选 Add python.exe to PATH）
   https://www.python.org/downloads/
2. 安装 Chrome / Edge 及 Automa 扩展（扩展详情里开启"允许访问文件网址"）
3. 注册 DeepSeek（可选，AI 价格诊断/描述功能）：
   - 前往 https://platform.deepseek.com 创建 API Key
   - 配置 config\secrets.env 中 DEEPSEEK_ENABLED=true 与 DEEPSEEK_API_KEY
4. 双击 start.bat
   - 首次运行会自动生成 config\secrets.env
   - 关闭窗口，编辑 config\secrets.env 填入 DeepSeek 密钥（如开启 AI 功能）
   - 再次双击 start.bat 启动

二、日常使用
1. GF9 相机菜单把 USB 模式设为 PC(Storage)，拍完用 USB 线连电脑
   拍照命名建议：「商品号.张号.JPG」，如 1.1.JPG、1.2.JPG、1.3.JPG 属于商品 1，
   2.1.JPG、2.2.JPG 属于商品 2；导入时自动按商品号分组建商品（不匹配规则的照片不分组）
   批量改名：把一组照片拖到 rename_photos.bat 上，输入商品号 N 即可自动改名为 N.1、N.2...
2. 浏览器打开 http://127.0.0.1:8765 查看状态页
   - 导入照片后按「商品号」自动生成的商品会出现在「草稿商品」区
   - 在草稿区完善标题/价格/描述后点「保存并转正式」，才进入 Automa 列表
   - 也可在状态页手动添加测试商品
3. 导入照片：POST /api/import_photos
   - 自动查找 DCIM，MD5 去重，压缩到长边 2000px、质量 85
   - 保存到 images\imported\
   - 文件名「N.M.JPG」自动分组：同 N 归为同一商品（草稿），追加导入的同 N 照片自动并入
   - 保护：商品转正式后，同 N 的新照片不再自动并入（导入结果 blocked 中列出），
     需要时用 PUT /api/products/<id> 传 photo_ids 显式并入
4. 价格测试：POST /api/calculate_price
   示例：{ "base_price": 10000, "status": "CLEAN", "accessories": ["box","charger"] }
5. Automa 读取：GET http://127.0.0.1:8765/api/products
   按 README_项目要求.md 第 9 节配置工作流

三、接口一览
GET  /                    状态页（含添加测试商品表单）
POST /api/import_photos   导入相机照片
POST /api/calculate_price 价格计算（测试）
GET  /api/products        已完善商品列表 {"data": [...]}（草稿除外，Automa 读取）
POST /api/products        新增商品（扩展接口，便于没有相机时测试）
     JSON: {"title":"...","price":29800,"status":"CLEAN","description":"...","photo_ids":[1,2]}
GET  /api/drafts          草稿商品列表（文件名分组自动生成，含 next_no）
PUT  /api/products/<id>   更新商品并转正式；可传 photo_ids 显式并入照片
DELETE /api/products/<id> 删除商品（照片保留，解除关联）

四、打包便携版
运行 build.bat，生成 dist\SecondhandECAgent\
整个文件夹复制到新电脑，改 config\secrets.env 后双击 start.bat

五、Automa 工作流要点
- /api/products 返回 {"data": [...]}，与 README_项目要求.md 第 9.2 节一致
- Automa 循环数据请填 {{ products.data }}，循环 ID 用 item
- 图片上传用 item.image_paths（本地路径列表），浏览器模拟人工上传
- 分类为必填且是三级动态选择：用 {{ item.categories[0] }}、{{ item.categories[1] }}、
  {{ item.categories[2] }} 三个点击块逐级点选（块间加 500-1000ms 延迟等列表加载）
- 状态、配送方式等其余必填项请一并录制/填写，否则无法提交
- 其余按 README_项目要求.md 第 9 节配置

六、重要提醒
- Mercari 禁止自动化批量出品，Automa 有账号风险
- 必须人工确认后提交，每小时最多 2-3 件，随机间隔
- 密钥只填 config\secrets.env，不要外传、不要上传 GitHub
