"""对商品 API、确认过滤、价格诊断和 CORS 来源白名单进行轻量测试。

运行：python test_system.py

测试使用临时 SQLite 数据库，并模拟 AI 客户端调用；不需要先启动 Flask 服务，
也不会请求真实 DeepSeek API。
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import db

# main 模块导入时会初始化数据库；提前替换数据库路径，避免测试读写实际数据。
_TEMP_DIR = tempfile.TemporaryDirectory(prefix="ec_test_")
db.DB_PATH = Path(_TEMP_DIR.name) / "test.db"

from app import main  # noqa: E402


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = main.app.test_client()

    def setUp(self):
        # 每个 API 测试使用新建的临时数据库，避免测试数据相互影响。
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db.init_db()

    def test_home_page_returns_html(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Secondhand EC Agent", response.data)

    def test_removed_routes_are_not_available(self):
        # 已删除的接口（照片导入、草稿、规则价格计算、检查清单）应返回 404
        self.assertEqual(self.client.post("/api/import_photos").status_code, 404)
        self.assertEqual(self.client.get("/api/drafts").status_code, 404)
        self.assertEqual(self.client.post("/api/calculate_price", json={"base_price": 1000}).status_code, 404)
        self.assertEqual(self.client.post("/api/generate_checklist", json={"title": "Test"}).status_code, 404)

    def test_cors_allows_configured_origin(self):
        response = self.client.get("/", headers={"Origin": "http://127.0.0.1:8765"})
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://127.0.0.1:8765")

    def test_cors_does_not_allow_unknown_origin(self):
        response = self.client.get("/", headers={"Origin": "https://untrusted.example"})
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_create_update_and_delete_product(self):
        response = self.client.post(
            "/api/products",
            json={"title": "Test item", "price": 1200, "status": "CLEAN"},
        )
        self.assertEqual(response.status_code, 201)
        product_id = response.get_json()["id"]

        response = self.client.put(
            f"/api/products/{product_id}",
            json={"title": "Updated item", "price": 1500, "confirmed": True},
        )
        self.assertEqual(response.status_code, 200)

        products = self.client.get("/api/products?all=1").get_json()["data"]
        self.assertTrue(any(p["id"] == product_id and p["title"] == "Updated item" for p in products))

        response = self.client.delete(f"/api/products/{product_id}")
        self.assertEqual(response.status_code, 200)

    def test_create_product_requires_title_and_integer_price(self):
        self.assertEqual(self.client.post("/api/products", json={}).status_code, 400)
        self.assertEqual(
            self.client.post("/api/products", json={"title": "Test", "price": "not-a-price"}).status_code,
            400,
        )

    @patch.object(main.deepseek_client, "generate_description", return_value="生成された説明")
    def test_description_endpoint_uses_client_result(self, mocked_generate):
        response = self.client.post(
            "/api/generate_description",
            json={"title": "Test camera", "status": "CLEAN"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["description"], "生成された説明")
        mocked_generate.assert_called_once()

    def test_missing_product_returns_not_found(self):
        self.assertEqual(self.client.put("/api/products/999999", json={"title": "Test"}).status_code, 404)
        self.assertEqual(self.client.delete("/api/products/999999").status_code, 404)

    def test_automa_reads_only_confirmed_products(self):
        # 未确认商品不应出现在默认列表中（Automa 只读取已确认商品）
        created = self.client.post(
            "/api/products", json={"title": "Unconfirmed item", "price": 1000, "status": "CLEAN"}
        )
        pid = created.get_json()["id"]
        default_data = self.client.get("/api/products").get_json()["data"]
        self.assertFalse(any(p["id"] == pid for p in default_data))
        # 确认后应出现在默认列表中
        self.client.put(f"/api/products/{pid}", json={"confirmed": True})
        confirmed_data = self.client.get("/api/products").get_json()["data"]
        self.assertTrue(any(p["id"] == pid for p in confirmed_data))

    def test_all_flag_includes_legacy_draft_records(self):
        # 旧版本草稿（is_draft=1）默认不可见，?all=1 仍返回，避免清理后记录消失
        conn = db.get_db()
        conn.execute(
            "INSERT INTO products (title, price, status, is_draft) VALUES (?, ?, ?, 1)",
            ("Legacy draft", 500, "CLEAN"),
        )
        conn.commit()
        conn.close()
        default_data = self.client.get("/api/products").get_json()["data"]
        self.assertFalse(any(p["title"] == "Legacy draft" for p in default_data))
        all_data = self.client.get("/api/products?all=1").get_json()["data"]
        self.assertTrue(any(p["title"] == "Legacy draft" for p in all_data))

    @patch.object(
        main.deepseek_client,
        "suggest_prices",
        return_value={
            "new": {
                "amazon": {"price": 52000, "low": 47000, "high": 57000},
                "rakuten": {"price": 53000, "low": 48000, "high": 58000},
            },
            "used": {
                "mercari": {"price": 32000, "low": 29000, "high": 35000},
                "yahoo": {"price": 31000, "low": 28000, "high": 34000},
            },
            "new_base": 52500,
            "used_base": 31500,
            "accessory_options": [{"key": "acc_0", "label": "付属品なし", "list": ["box", "manual"]}],
            "note": "テスト",
        },
    )
    def test_suggest_price_returns_structured_prices(self, mocked_suggest):
        response = self.client.post("/api/suggest_price", json={"brand": "Panasonic", "model": "DC-GF9"})
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["new"]["amazon"]["price"], 52000)
        self.assertEqual(body["used"]["yahoo"]["price"], 31000)
        # 附件加成按 price_engine 统一规则重算，而不是沿用模型返回值
        self.assertEqual(body["accessory_options"][0]["bonus"], 0.07)
        self.assertEqual(len(body["status_options"]), 3)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    _TEMP_DIR.cleanup()
    raise SystemExit(0 if result.wasSuccessful() else 1)
