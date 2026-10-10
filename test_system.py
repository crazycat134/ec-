"""
Secondhand EC Agent V3 - 系统测试脚本
按照大厂测试逻辑：功能测试 + 边界测试 + 流程测试 + 回归测试
"""
import requests
import json
import sys

BASE = "http://127.0.0.1:8765"
passed = 0
failed = 0
errors = []

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  ✅ {name}")
        passed += 1
    else:
        print(f"  ❌ {name} - {detail}")
        failed += 1
        errors.append(f"{name}: {detail}")

def section(title):
    print(f"\n{'='*50}")
    print(f"📋 {title}")
    print(f"{'='*50}")

# ========== 1. 基础连通性测试 ==========
section("1. 基础连通性")

try:
    r = requests.get(f"{BASE}/", timeout=5)
    test("首页能打开", r.status_code == 200, f"status={r.status_code}")
    test("首页有标题", "Secondhand EC Agent" in r.text, "")
    test("首页有全选按钮", "select-all" in r.text, "")
    test("首页有批量操作栏", "batch-bar" in r.text, "")
    test("首页有添加按钮", "showAddForm" in r.text, "")
except Exception as e:
    test("首页能打开", False, str(e))

# ========== 2. 商品 CRUD 测试 ==========
section("2. 商品 CRUD")

# 创建商品
try:
    r = requests.post(f"{BASE}/api/products", json={
        "title": "测试商品_TestProduct",
        "price": 29800,
        "status": "CLEAN"
    }, timeout=5)
    data = r.json()
    test("创建商品成功", r.status_code in [200, 201] and "id" in data, str(data))
    test_id = data.get("id")
except Exception as e:
    test("创建商品成功", False, str(e))
    test_id = None

# 获取商品列表
try:
    r = requests.get(f"{BASE}/api/products?all=1", timeout=5)
    data = r.json()
    test("获取商品列表", r.status_code == 200 and "data" in data, str(data)[:100])
    test("列表是数组", isinstance(data.get("data"), list), "")
except Exception as e:
    test("获取商品列表", False, str(e))

# 更新商品
if test_id:
    try:
        r = requests.put(f"{BASE}/api/products/{test_id}", json={
            "title": "测试商品_已更新",
            "price": 30000,
            "confirmed": 1
        }, timeout=5)
        test("更新商品成功", r.status_code == 200, str(r.text[:100]))
    except Exception as e:
        test("更新商品成功", False, str(e))

# 删除商品
if test_id:
    try:
        r = requests.delete(f"{BASE}/api/products/{test_id}", timeout=5)
        test("删除商品成功", r.status_code == 200, str(r.text[:100]))
    except Exception as e:
        test("删除商品成功", False, str(e))

# ========== 3. 价格计算测试 ==========
section("3. 价格计算引擎")

try:
    r = requests.post(f"{BASE}/api/calculate_price", json={
        "base_price": 30000,
        "status": "CLEAN",
        "accessories": ["box", "manual"]
    }, timeout=5)
    data = r.json()
    test("价格计算成功", r.status_code == 200, str(data))
    test("返回 low/center/high", all(k in data for k in ["low", "center", "high"]), "")
    test("价格区间合理", data.get("low", 0) < data.get("center", 0) < data.get("high", 0), f"{data}")
except Exception as e:
    test("价格计算成功", False, str(e))

# 边界测试：空附件
try:
    r = requests.post(f"{BASE}/api/calculate_price", json={
        "base_price": 30000,
        "status": "BRAND_NEW",
        "accessories": []
    }, timeout=5)
    test("空附件不报错", r.status_code == 200, str(r.text[:100]))
except Exception as e:
    test("空附件不报错", False, str(e))

# ========== 4. AI 功能测试 ==========
section("4. AI 功能（DeepSeek）")

# AI 查价
try:
    r = requests.post(f"{BASE}/api/suggest_price", json={
        "brand": "Panasonic",
        "model": "DC-GF9"
    }, timeout=30)
    data = r.json()
    test("AI 查价成功", r.status_code == 200, str(data)[:100])
    test("返回 new 平台价格", "new" in data and "amazon" in data.get("new", {}), "")
    test("返回 used 平台价格", "used" in data and "mercari" in data.get("used", {}), "")
    test("价格是数字", isinstance(data.get("new", {}).get("amazon", {}).get("price"), (int, float)), "")
except Exception as e:
    test("AI 查价成功", False, str(e))

# AI 生成描述
try:
    r = requests.post(f"{BASE}/api/generate_description", json={
        "title": "LUMIX GF9",
        "status": "CLEAN",
        "works_confirmed": True,
        "accessories": ["box", "manual"]
    }, timeout=30)
    data = r.json()
    test("AI 生成描述成功", r.status_code == 200, str(data)[:100])
    test("返回 description", "description" in data, "")
    test("描述不为空", len(data.get("description", "")) > 50, f"长度={len(data.get('description', ''))}")
except Exception as e:
    test("AI 生成描述成功", False, str(e))

# AI 生成 checklist
try:
    r = requests.post(f"{BASE}/api/generate_checklist", json={
        "title": "LUMIX GF9"
    }, timeout=30)
    data = r.json()
    test("AI 生成 checklist 成功", r.status_code == 200, str(data)[:100])
    test("返回 works_items", "works_items" in data, "")
    test("返回 standard_accessories", "standard_accessories" in data, "")
except Exception as e:
    test("AI 生成 checklist 成功", False, str(e))

# ========== 5. 草稿测试 ==========
section("5. 草稿功能")

try:
    r = requests.get(f"{BASE}/api/drafts", timeout=5)
    data = r.json()
    test("获取草稿列表", r.status_code == 200, str(data)[:100])
except Exception as e:
    test("获取草稿列表", False, str(e))

# ========== 6. 边界/异常测试 ==========
section("6. 边界/异常测试")

# 空值创建
try:
    r = requests.post(f"{BASE}/api/products", json={}, timeout=5)
    test("空值创建不崩溃", r.status_code in [200, 400], f"status={r.status_code}")
except Exception as e:
    test("空值创建不崩溃", False, str(e))

# 不存在的商品更新
try:
    r = requests.put(f"{BASE}/api/products/99999", json={"title": "test"}, timeout=5)
    test("更新不存在商品不崩溃", r.status_code in [200, 404], f"status={r.status_code}")
except Exception as e:
    test("更新不存在商品不崩溃", False, str(e))

# 不存在的商品删除
try:
    r = requests.delete(f"{BASE}/api/products/99999", timeout=5)
    test("删除不存在商品不崩溃", r.status_code in [200, 404], f"status={r.status_code}")
except Exception as e:
    test("删除不存在商品不崩溃", False, str(e))

# AI 查价缺参数
try:
    r = requests.post(f"{BASE}/api/suggest_price", json={"brand": ""}, timeout=5)
    test("AI 查价缺参数不崩溃", r.status_code in [200, 400], f"status={r.status_code}")
except Exception as e:
    test("AI 查价缺参数不崩溃", False, str(e))

# ========== 7. 页面 UI 测试 ==========
section("7. 页面 UI 元素检查")

try:
    r = requests.get(f"{BASE}/", timeout=5)
    html = r.text
    test("有价格诊断函数", "aiPriceSuggest" in html, "")
    test("有批量确认函数", "batchConfirm" in html, "")
    test("有批量删除函数", "batchDelete" in html, "")
    test("有全选函数", "toggleSelectAll" in html, "")
    test("有 toast 提示", "showToast" in html, "")
    test("有创建商品函数", "diagSave" in html, "")
except Exception as e:
    test("页面 UI 检查", False, str(e))

# ========== 总结 ==========
section("测试总结")
print(f"\n✅ 通过: {passed}")
print(f"❌ 失败: {failed}")
print(f"📊 总计: {passed + failed}")
print(f"📈 通过率: {passed/(passed+failed)*100:.1f}%")

if errors:
    print(f"\n失败详情:")
    for e in errors:
        print(f"  - {e}")

sys.exit(0 if failed == 0 else 1)
