"""封装 DeepSeek API 调用：生成商品描述、检查清单和价格参考结构。"""
import json
import logging
import re

import requests

log = logging.getLogger("secea")

# 生成商品描述后追加的固定说明文字。
DISCLAIMER = "\n\n中古品のため、現状渡しとなります。状態をご理解の上、ご購入をお願いいたします。"


def _default_price_result() -> dict:
    """返回固定兜底数据；其中价格是代码内的默认值，不是实时查询结果。"""
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


# 附件内部键名；价格加成定义在 price_engine.ACCESSORY_BONUS。
STD_ACC_KEYS = {"box", "manual", "charger", "other", "battery", "lens_cap", "strap", "cable"}
# 附件内部键到日文显示名称的映射。
ACC_LABELS = {
    "charger": "充電器",
    "other": "その他付属品",
    "battery": "バッテリー",
    "lens_cap": "レンズキャップ",
    "strap": "ストラップ",
    "cable": "ケーブル",
}
# 价格选项默认包含箱和说明书；该规则作用于本模块生成的附件选项。
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
    """请求模型生成各平台的价格参考值；本函数不直接抓取平台商品页面，返回值应视为估算。

    返回：{"new": {amazon, rakuten}, "used": {mercari, yahoo}, "new_base", "used_base", "note"}
    每个平台为 {"price", "low", "high"}；未启用 API 或无法解析模型回复时，返回固定兜底值。
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

    # 将附件内部键转换为商品描述中使用的日文名称。
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

    # 将内部商品状态码转换为日文展示文本。
    status_map = {
        "BRAND_NEW": "新品、未使用",
        "ALMOST_NEW": "目立った傷や汚れなし",
        "CLEAN": "目立った傷や汚れなし",
        "LITTLE_DIRTY": "やや傷や汚れあり",
        "DIRTY": "目立った傷や汚れあり",
        "BAD": "全体的に状態が悪い",
    }
    status_text = status_map.get(status, status)

    # 根据人工确认标记生成动作品质说明；未确认时会写为未确认/ジャンク前提。
    works_text = "動作確認済み（正常に動作することを確認済）" if works_confirmed else "動作未確認（ジャンク品・部品取り前提）"

    # 未传入自定义提示词时，使用内置的日文商品描述模板。
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
    # 在模型生成文本末尾追加固定说明。
    text = text.rstrip() + DISCLAIMER
    log.info("DeepSeek generated %d chars", len(text))
    return text
