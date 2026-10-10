"""DeepSeek API：根据商品信息生成日文商品描述。"""
import logging

import requests

log = logging.getLogger("secea")

# 固定免责声明（中古品必加）
DISCLAIMER = "\n\n中古品のため、現状渡しとなります。状態をご理解の上、ご購入をお願いいたします。"


def _default_price_result() -> dict:
    """DeepSeek 未开启或调用失败时的兜底价格结构（new/used 各两平台 + 基准价）。"""
    return {
        "new": {
            "amazon": {"price": 30000, "low": 27000, "high": 33000},
            "rakuten": {"price": 29500, "low": 26500, "high": 32500},
        },
        "used": {
            "mercari": {"price": 16500, "low": 14800, "high": 18200},
            "yahoo": {"price": 16200, "low": 14500, "high": 17900},
        },
        "new_base": 29700,
        "used_base": 16300,
        "accessory_options": [
            {"key": "none", "label": "付属品なし", "list": ["box", "manual"]},
            {"key": "charger", "label": "充電器", "list": ["box", "manual", "charger"]},
        ],
        "note": "AI 未配置，使用默认参考价（仅供参考）",
    }


# 附属品标准内部 key（与 price_engine.ACCESSORY_BONUS 一致）
STD_ACC_KEYS = {"box", "manual", "charger", "other", "battery", "lens_cap", "strap", "cable"}
# 附属品日文显示名
ACC_LABELS = {
    "charger": "充電器",
    "other": "その他付属品",
    "battery": "バッテリー",
    "lens_cap": "レンズキャップ",
    "strap": "ストラップ",
    "cable": "ケーブル",
}
# 二手标配（箱・説明書）：所有附属品选项自动带上，选项内容不显示
BASE_ACCESSORIES = ["box", "manual"]


def _normalize_accessory_options(raw_options) -> list:
    """把 AI 返回的附属品选项规整为 [{key, label, list}]。
    箱・説明書 为二手标配，从选项显示中扣除，但每个选项的 list 自动带上标配。"""
    opts = []
    if not isinstance(raw_options, (list, tuple)):
        return opts
    seen = set()
    for i, a in enumerate(raw_options):
        if not isinstance(a, dict):
            continue
        raw_keys = a.get("keys") or a.get("list") or []
        extra = []
        for k in raw_keys:
            k = str(k).strip().lower()
            if k in STD_ACC_KEYS and k not in ("box", "manual") and k not in extra:
                extra.append(k)
        if not extra:
            if "付属品なし" in seen:
                continue
            opts.append({"key": f"acc_{i}", "label": "付属品なし", "list": list(BASE_ACCESSORIES)})
            seen.add("付属品なし")
        else:
            label = "・".join(ACC_LABELS.get(k, k) for k in extra)
            if label in seen:
                continue
            opts.append({"key": f"acc_{i}", "label": label, "list": list(BASE_ACCESSORIES) + extra})
            seen.add(label)
    return opts


def _normalize_platform(data: dict, default_price: int) -> dict:
    """把 AI 返回的平台价格规整为 {price, low, high}，缺失字段兜底。"""
    try:
        price = int(float(data.get("price", default_price)))
    except (TypeError, ValueError):
        price = default_price
    try:
        low = int(float(data.get("low", round(price * 0.9))))
    except (TypeError, ValueError):
        low = round(price * 0.9)
    try:
        high = int(float(data.get("high", round(price * 1.1))))
    except (TypeError, ValueError):
        high = round(price * 1.1)
    if high <= low:
        high = round(price * 1.1)
        low = round(price * 0.9)
    return {"price": price, "low": low, "high": high}


def suggest_prices(cfg, brand: str, model: str) -> dict:
    """根据品牌+型号，AI 调查各平台（Amazon/楽天 新品、メルカリ/Yahoo! 中古）实势价格。

    返回：{"new": {amazon, rakuten}, "used": {mercari, yahoo}, "new_base", "used_base", "note"}
    每个平台为 {"price", "low", "high"}；DeepSeek 未开启时返回默认估算。
    """
    if not cfg.deepseek_enabled or not cfg.deepseek_api_key:
        return _default_price_result()

    prompt = f"""
あなたは日本の価格調査アシスタントです。
以下の商品の新品・中古の実勢価格を、日本の大手ECサイトの相場を参考に予想してください。

商品：{brand} {model}

回答は JSON 形式で：
{{
  "new": {{
    "amazon": {{"price": 新品実勢価格の目安（円）, "low": 想定下限（円）, "high": 想定上限（円）}},
    "rakuten": {{"price": ..., "low": ..., "high": ...}}
  }},
  "used": {{
    "mercari": {{"price": 中古・動作確認済みの相場（円）, "low": ..., "high": ...}},
    "yahoo": {{"price": ..., "low": ..., "high": ...}}
  }},
  "accessory_options": [
    {{"label": "付属品なし", "keys": []}},
    {{"label": "箱・説明書", "keys": ["box", "manual"]}},
    {{"label": "箱・説明書・充電器", "keys": ["box", "manual", "charger"]}}
  ],
  "note": "補足説明（日本語、1〜2文）"
}}

必ず JSON だけを返してください。価格はすべて円（整数）で返してください。
accessory_options は商品に合わせて2〜4通りの組み合わせにしてください。
箱・説明書は標準付属品として常に含まれる前提のため、オプションには箱・説明書を含めず、
追加の付属品のみの組み合わせを列挙してください（例：カメラなら「充電器」「充電器・バッテリー」等）。
keys は標準キーのみ：charger=充電器, battery=バッテリー, lens_cap=レンズキャップ, strap=ストラップ, cable=ケーブル, other=その他付属品。
最初の項目は必ず「付属品なし」にしてください。
"""
    try:
        url = f"{cfg.deepseek_base_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {cfg.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": cfg.deepseek_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 600,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        resp = data["choices"][0]["message"]["content"].strip()
        import json, re
        m = re.search(r"\{.*\}", resp, re.DOTALL)
        if m:
            raw = json.loads(m.group(0))
            result = {
                "new": {
                    "amazon": _normalize_platform(raw.get("new", {}).get("amazon", {}), 30000),
                    "rakuten": _normalize_platform(raw.get("new", {}).get("rakuten", {}), 29500),
                },
                "used": {
                    "mercari": _normalize_platform(raw.get("used", {}).get("mercari", {}), 16500),
                    "yahoo": _normalize_platform(raw.get("used", {}).get("yahoo", {}), 16200),
                },
                "note": str(raw.get("note", "")) or "調査結果",
            }
            acc_options = _normalize_accessory_options(raw.get("accessory_options"))
            if acc_options:
                result["accessory_options"] = acc_options
            result["new_base"] = round((result["new"]["amazon"]["price"] + result["new"]["rakuten"]["price"]) / 2)
            result["used_base"] = round((result["used"]["mercari"]["price"] + result["used"]["yahoo"]["price"]) / 2)
            return result
    except Exception as e:
        log.exception("suggest_prices failed: %s", e)
    return _default_price_result()


def generate_description(cfg, title: str, brand: str = "", model: str = "",
                         status: str = "", accessories: list = None,
                         works_confirmed: bool = False,
                         custom_prompt: str = "") -> str:
    """调用 DeepSeek API 生成商品描述。

    cfg: Config 实例
    title: 商品标题
    brand: 品牌
    model: 型号
    status: 状态（BRAND_NEW 等）
    accessories: 附件列表 ["box", "manual"]
    works_confirmed: 动作确认済み True/False
    custom_prompt: 自定义提示词模板（可选，留空用默认）
    返回：生成的描述文本（末尾自动加免责声明）
    """
    if not cfg.deepseek_enabled:
        raise RuntimeError("DeepSeek 未开启（DEEPSEEK_ENABLED=false）")

    # 附件转日文
    accessory_map = {
        "box": "箱",
        "manual": "説明書",
        "charger": "充電器",
        "other": "その他付属品",
        "battery": "バッテリー",
        "lens_cap": "レンズキャップ",
        "strap": "ストラップ",
        "cable": "ケーブル",
    }
    accessory_list = [accessory_map.get(a, a) for a in (accessories or [])]
    accessory_text = "・".join(accessory_list) if accessory_list else "本体のみ（付属品なし）"

    # 状态转日文
    status_map = {
        "BRAND_NEW": "新品、未使用",
        "ALMOST_NEW": "目立った傷や汚れなし",
        "CLEAN": "目立った傷や汚れなし",
        "LITTLE_DIRTY": "やや傷や汚れあり",
        "DIRTY": "目立った傷や汚れあり",
        "BAD": "全体的に状態が悪い",
    }
    status_text = status_map.get(status, status)

    # 动作确认转日文
    works_text = "動作確認済み（正常に動作することを確認済）" if works_confirmed else "動作未確認（ジャンク品・部品取り前提）"

    # 默认提示词：固定模板 + 商品介绍
    if not custom_prompt:
        custom_prompt = (
            "あなたは日本のフリマアプリ「メルカリ」の出品文案を書くプロです。\n"
            "以下のテンプレートに沿って商品説明文を作成してください。\n"
            "ネガティブ表現は使わず、商品の良いところだけを書いてください。\n"
            "\n"
            "【商品名】\n{title}\n\n"
            "【商品紹介】\nこの商品の特徴・おすすめポイントを1〜2文で書いてください。\n\n"
            "【状態】\n{status}\n\n"
            "【付属品】\n{accessories}\n\n"
            "【動作確認】\n{works}\n"
        )

    prompt = custom_prompt.format(
        title=title or "",
        brand=brand or "未記入",
        model=model or "未記入",
        status=status_text or "",
        accessories=accessory_text,
        works=works_text,
    )

    url = f"{cfg.deepseek_base_url.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.deepseek_model,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 500,
    }

    log.info("DeepSeek generating description for: %s (works=%s)", title, works_confirmed)
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    text = data["choices"][0]["message"]["content"].strip()
    # 末尾自动加固定免责声明
    text = text.rstrip() + DISCLAIMER
    log.info("DeepSeek generated %d chars", len(text))
    return text


def generate_checklist(cfg, title: str) -> dict:
    """根据商品标题生成标准检查清单：
    - works_items: 应该检查的动作项（电源/快门/对焦等）
    - standard_accessories: 标准附件清单（本体/电池/充电器/说明书/箱等）
    返回 {"works_items": [...], "standard_accessories": [...]}
    """
    if not cfg.deepseek_enabled:
        raise RuntimeError("DeepSeek 未开启（DEEPSEEK_ENABLED=false）")

    prompt = f"""
あなたは中古品買取・出品のプロです。
商品タイトル：{title}

この商品について、以下2つのリストをJSON形式で生成してください。

1. works_items：動作確認すべき項目（5〜8個、具体的なチェックポイント）
   例（カメラの場合）：「電源が入るか」「シャッターが切れるか」「液晶モニターは正常か」「バッテリーは充電できるか」「レンズにカビ・クモリはないか」

2. standard_accessories：標準付属品（同梱されているべきもの、4〜6個）
   例（カメラの場合）：「本体」「バッテリー」「充電器」「説明書」「元箱」

JSONのみ出力してください。説明文は不要です。
フォーマット：
{{"works_items": ["項目1", "項目2", ...], "standard_accessories": ["付属品1", "付属品2", ...]}}
"""

    url = f"{cfg.deepseek_base_url.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.deepseek_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 400,
    }

    log.info("DeepSeek generating checklist for: %s", title)
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    text = data["choices"][0]["message"]["content"].strip()

    # 提取 JSON
    import json, re
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        result = json.loads(match.group())
        return {
            "works_items": result.get("works_items", []),
            "standard_accessories": result.get("standard_accessories", []),
        }
    else:
        return {"works_items": [], "standard_accessories": [], "raw": text}
