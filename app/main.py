"""Flask 主程序：提供本地 HTTP 接口（状态页 / 照片导入 / 价格计算 / 商品列表）。"""
import json
import logging
import sys
from pathlib import Path

from flask import Flask, jsonify, request

from . import camera_import
from . import db
from . import deepseek_client
from . import price_engine
from .config import Config, PROJECT_ROOT

cfg = Config()
app = Flask(__name__)

# ---------- 日志 ----------
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_DIR / "app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("secea")

db.init_db()


@app.after_request
def _cors(resp):
    """允许 Automa 浏览器扩展跨域读取本地接口。"""
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

STATUS_OPTIONS = "".join(f"<option>{s}</option>" for s in price_engine.STATUS_MULTIPLIERS)

# 本地英文状态 -> Mercari 出品页「商品の状態」日文本选项
STATUS_TO_MERCARI = {
    "BRAND_NEW": "新品、未使用",
    "ALMOST_NEW": "目立った傷や汚れなし",
    "CLEAN": "目立った傷や汚れなし",
    "LITTLE_DIRTY": "やや傷や汚れあり",
    "DIRTY": "目立った傷や汚れあり",
    "BAD": "全体的に状態が悪い",
}


def _mercari_status(raw_status) -> str:
    return STATUS_TO_MERCARI.get(raw_status or "", "目立った傷や汚れなし")


def _parse_categories(value):
    """把用户输入的分类转成数组：接受数组，或「大类 > 中类 > 小类」字符串。"""
    if isinstance(value, str):
        return [c.strip() for c in value.split(">") if c.strip()]
    if isinstance(value, (list, tuple)):
        return [str(c).strip() for c in value if str(c).strip()]
    return []


def _read_categories(raw) -> list:
    """从数据库行读取 categories（JSON 字符串）并解析为数组。"""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _read_template() -> str:
    """查找状态页模板：冻结（PyInstaller）时优先从 _MEIPASS 内读取。"""
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
        candidates.append(meipass / "app" / "templates" / "index.html")
    candidates.append(PROJECT_ROOT / "app" / "templates" / "index.html")
    for c in candidates:
        try:
            if c.exists():
                return c.read_text(encoding="utf-8")
        except OSError:
            continue
    return ""


def _status_page(ready_text, ready_cls, product_count, photo_count, next_no) -> str:
    html = _read_template()
    if not html:
        return "服务已启动，缺少模板文件 app/templates/index.html"
    return (
        html.replace("__READY_TEXT__", ready_text)
        .replace("__READY_CLS__", ready_cls)
        .replace("__PRODUCT_COUNT__", str(product_count))
        .replace("__PHOTO_COUNT__", str(photo_count))
        .replace("__NEXT_NO__", str(next_no))
        .replace("__STATUS_OPTIONS__", STATUS_OPTIONS)
    )


def _max_product_no(conn) -> int:
    """返回当前最大的商品号（全局连续编号的基准）。"""
    rows = conn.execute("SELECT product_no FROM products WHERE product_no IS NOT NULL").fetchall()
    return max((r["product_no"] for r in rows), default=0)


@app.route("/")
def index():
    missing = cfg.check_ready()
    conn = db.get_db()
    try:
        product_count = conn.execute("SELECT COUNT(*) AS c FROM products WHERE is_draft = 0").fetchone()["c"]
        photo_count = conn.execute("SELECT COUNT(*) AS c FROM photos").fetchone()["c"]
        next_no = _max_product_no(conn) + 1
    finally:
        conn.close()
    if missing:
        ready_text = "未就绪，缺少：" + "、".join(missing)
        ready_cls = "warn"
    else:
        ready_text = "就绪"
        ready_cls = "ok"
    return _status_page(ready_text, ready_cls, product_count, photo_count, next_no)


@app.route("/api/import_photos", methods=["POST"])
def api_import_photos():
    result = camera_import.import_photos(cfg)
    log.info("import_photos -> status=%s imported=%d", result["status"], len(result["imported"]))
    return jsonify(result)


@app.route("/api/calculate_price", methods=["POST"])
def api_calculate_price():
    data = request.get_json(silent=True) or {}
    try:
        base_price = int(data.get("base_price", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "base_price 必须是整数"}), 400
    status = str(data.get("status", "CLEAN")).upper()
    if status not in price_engine.STATUS_MULTIPLIERS:
        return jsonify({"error": f"status 必须是 {list(price_engine.STATUS_MULTIPLIERS)} 之一"}), 400
    accessories = data.get("accessories") or []
    return jsonify(price_engine.calculate_price(base_price, status, accessories))


@app.route("/api/generate_description", methods=["POST"])
def api_generate_description():
    """DeepSeek AI 生成商品描述（人工确认后保存）。"""
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify({"error": "title 不能为空"}), 400
    try:
        text = deepseek_client.generate_description(
            cfg,
            title=title,
            brand=str(data.get("brand", "")),
            model=str(data.get("model", "")),
            status=str(data.get("status", "CLEAN")).upper(),
            accessories=data.get("accessories") or [],
            works_confirmed=bool(data.get("works_confirmed", False)),
            custom_prompt=str(data.get("custom_prompt", "")),
        )
        return jsonify({"description": text})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        log.exception("DeepSeek generate failed")
        return jsonify({"error": f"DeepSeek 调用失败: {e}"}), 500


@app.route("/api/generate_checklist", methods=["POST"])
def api_generate_checklist():
    """DeepSeek AI 根据商品标题生成标准检查清单（动作确认项 + 标准附件）。"""
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify({"error": "title 不能为空"}), 400
    try:
        result = deepseek_client.generate_checklist(cfg, title)
        return jsonify(result)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        log.exception("DeepSeek checklist failed")
        return jsonify({"error": f"DeepSeek 调用失败: {e}"}), 500


# 价格诊断：商品状态系数（与 price_engine 保持一致）
DIAG_STATUS_OPTIONS = [
    {"key": "BRAND_NEW", "label": "新品・未使用", "mult": 1.00},
    {"key": "ALMOST_NEW", "label": "目立った傷や汚れなし", "mult": 0.95},
    {"key": "LITTLE_DIRTY", "label": "やや傷や汚れあり", "mult": 0.85},
]

# 价格诊断：附属品选项（bonus 与 price_engine.ACCESSORY_BONUS 合计一致；
# 箱・説明書 为二手标配，选项不显示但保存时自动带上）
DIAG_ACCESSORY_OPTIONS = [
    {"key": "none", "label": "付属品なし", "bonus": 0.07, "list": ["box", "manual"]},
    {"key": "charger", "label": "充電器", "bonus": 0.10, "list": ["box", "manual", "charger"]},
]


@app.route("/api/suggest_price", methods=["POST"])
def api_suggest_price():
    """根据品牌+型号，AI 调查各平台（新品/中古）实势价格。

    返回：
    {
      "new": {"amazon": {price,low,high}, "rakuten": {...}},
      "used": {"mercari": {...}, "yahoo": {...}},
      "new_base": int, "used_base": int,
      "status_options": [...], "accessory_options": [...],
      "note": "..."
    }
    """
    body = request.get_json(force=True) or {}
    brand = (body.get("brand") or "").strip()
    model = (body.get("model") or "").strip()
    if not brand or not model:
        return jsonify({"error": "brand 和 model は必須です"}), 400
    try:
        result = deepseek_client.suggest_prices(cfg, brand, model)
        # 附属品选项：AI 按商品生成优先，否则用默认；统一计算加分
        if not result.get("accessory_options"):
            result["accessory_options"] = DIAG_ACCESSORY_OPTIONS
        for acc in result["accessory_options"]:
            acc["bonus"] = round(
                sum(price_engine.ACCESSORY_BONUS.get(k, 0.0) for k in acc.get("list", [])), 4
            )
        result["status_options"] = DIAG_STATUS_OPTIONS
        return jsonify(result)
    except Exception as e:
        log.exception("DeepSeek suggest price failed")
        return jsonify({"error": f"DeepSeek 调用失败: {e}"}), 500


@app.route("/api/products", methods=["GET"])
def api_products():
    """返回商品列表（{"data": [...]}），供 Automa 循环读取。
    默认只返回 confirmed=1 的已确认商品；加 ?all=1 返回所有正式商品（状态页用）。"""
    all_flag = request.args.get("all", "0").lower() in ("1", "true", "yes")
    conn = db.get_db()
    try:
        if all_flag:
            rows = conn.execute("SELECT * FROM products WHERE is_draft = 0 ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM products WHERE is_draft = 0 AND confirmed = 1 ORDER BY id DESC").fetchall()
        result = []
        for p in rows:
            photos = conn.execute(
                "SELECT local_path FROM photos WHERE product_id = ? ORDER BY photo_no",
                (p["id"],),
            ).fetchall()
            # Automa 上传图片用本地路径（浏览器模拟人工上传）
            image_paths = [ph["local_path"] for ph in photos]
            result.append({
                "id": p["id"],
                "product_no": p["product_no"],
                "title": p["title"],
                "price": p["price"],
                "status": p["status"],
                "description": p["description"],
                "confirmed": bool(p["confirmed"]),
                "works_confirmed": bool(p["works_confirmed"]),
                "accessories": json.loads(p["accessories"]) if p["accessories"] else [],
                "images": image_paths,
                "image_paths": image_paths,
                "categories": _read_categories(p["categories"]),
                "mercari_status": _mercari_status(p["status"]),
            })
    finally:
        conn.close()
    return jsonify({"data": result})


@app.route("/api/products", methods=["POST"])
def api_create_product():
    """扩展接口：手动/测试新增商品，便于在没有相机时验证 Automa 流程。"""
    data = request.get_json(silent=True) or {}
    title = str(data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title 不能为空"}), 400
    try:
        price = int(data.get("price"))
    except (TypeError, ValueError):
        return jsonify({"error": "price 必须是整数"}), 400
    status = str(data.get("status", "CLEAN")).upper()
    if status not in price_engine.STATUS_MULTIPLIERS:
        return jsonify({"error": f"status 必须是 {list(price_engine.STATUS_MULTIPLIERS)} 之一"}), 400
    description = str(data.get("description") or "")
    photo_ids = data.get("photo_ids") or []
    categories = _parse_categories(data.get("categories") or [])
    works_confirmed = 1 if data.get("works_confirmed") else 0
    accessories = json.dumps(data.get("accessories") or [], ensure_ascii=False)

    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO products (title, price, status, description, categories, works_confirmed, accessories) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, price, status, description, json.dumps(categories, ensure_ascii=False),
             works_confirmed, accessories),
        )
        product_id = cur.lastrowid
        for pid in photo_ids:
            conn.execute("UPDATE photos SET product_id = ? WHERE id = ?", (product_id, int(pid)))
        conn.commit()
    finally:
        conn.close()
    log.info("create_product -> id=%d title=%s price=%d", product_id, title, price)
    return jsonify({"id": product_id, "ok": True}), 201


@app.route("/api/products/<int:pid>", methods=["PUT"])
def api_update_product(pid):
    """更新商品（标题/价格/状态/描述），供导入分组后完善商品信息。"""
    data = request.get_json(silent=True) or {}
    conn = db.get_db()
    try:
        row = conn.execute("SELECT id FROM products WHERE id = ?", (pid,)).fetchone()
        if row is None:
            return jsonify({"error": "product not found"}), 404
        fields, values = [], []
        if "title" in data:
            title = str(data["title"] or "").strip()
            if not title:
                return jsonify({"error": "title 不能为空"}), 400
            fields.append("title = ?")
            values.append(title)
        if "price" in data:
            try:
                price = int(data["price"])
            except (TypeError, ValueError):
                return jsonify({"error": "price 必须是整数"}), 400
            fields.append("price = ?")
            values.append(price)
        if "status" in data:
            status = str(data["status"]).upper()
            if status not in price_engine.STATUS_MULTIPLIERS:
                return jsonify({"error": f"status 必须是 {list(price_engine.STATUS_MULTIPLIERS)} 之一"}), 400
            fields.append("status = ?")
            values.append(status)
        if "description" in data:
            fields.append("description = ?")
            values.append(str(data["description"] or ""))
        if "categories" in data:
            fields.append("categories = ?")
            values.append(json.dumps(_parse_categories(data["categories"]), ensure_ascii=False))
        if "confirmed" in data:
            fields.append("confirmed = ?")
            values.append(1 if data["confirmed"] else 0)
        if "works_confirmed" in data:
            fields.append("works_confirmed = ?")
            values.append(1 if data["works_confirmed"] else 0)
        if "accessories" in data:
            fields.append("accessories = ?")
            values.append(json.dumps(data["accessories"] or [], ensure_ascii=False))
        if not fields and not data.get("photo_ids"):
            return jsonify({"error": "没有可更新的字段"}), 400
        if fields:
            fields.append("is_draft = 0")  # 保存即转正式（Automa 才能读取）
            values.append(pid)
            conn.execute(f"UPDATE products SET {', '.join(fields)} WHERE id = ?", values)
        # 显式并入照片（保护规则下被拦截的照片，可在此手动挂到商品）
        for photo_id in (data.get("photo_ids") or []):
            conn.execute("UPDATE photos SET product_id = ? WHERE id = ?", (pid, int(photo_id)))
        conn.commit()
    finally:
        conn.close()
    log.info("update_product -> id=%d", pid)
    return jsonify({"id": pid, "ok": True})


@app.route("/api/products/<int:pid>", methods=["DELETE"])
def api_delete_product(pid):
    """删除商品，并解除其照片关联。"""
    conn = db.get_db()
    try:
        cur = conn.execute("DELETE FROM products WHERE id = ?", (pid,))
        if cur.rowcount == 0:
            return jsonify({"error": "product not found"}), 404
        conn.execute("UPDATE photos SET product_id = NULL WHERE product_id = ?", (pid,))
        conn.commit()
    finally:
        conn.close()
    log.info("delete_product -> id=%d", pid)
    return jsonify({"ok": True})


@app.route("/api/drafts", methods=["GET"])
def api_drafts():
    """草稿商品列表（照片按「N.M」命名导入时自动生成），完善后经 PUT 转正式。"""
    conn = db.get_db()
    try:
        rows = conn.execute("SELECT * FROM products WHERE is_draft = 1 ORDER BY product_no").fetchall()
        result = []
        for p in rows:
            photos = conn.execute(
                "SELECT local_path FROM photos WHERE product_id = ? ORDER BY photo_no",
                (p["id"],),
            ).fetchall()
            images = [ph["local_path"] for ph in photos]
            result.append({
                "id": p["id"],
                "product_no": p["product_no"],
                "title": p["title"],
                "price": p["price"],
                "status": p["status"],
                "description": p["description"],
                "images": images,
                "photo_count": len(photos),
                "categories": _read_categories(p["categories"]),
                "mercari_status": _mercari_status(p["status"]),
                "is_draft": True,
            })
        next_no = _max_product_no(conn) + 1
    finally:
        conn.close()
    return jsonify({"data": result, "next_no": next_no})
