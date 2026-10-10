"""价格修正规则：按 Mercari 商品状态系数 + 附件加分，计算推荐价格区间。"""

STATUS_MULTIPLIERS = {
    "BRAND_NEW": 1.00,
    "ALMOST_NEW": 0.95,
    "CLEAN": 0.90,
    "LITTLE_DIRTY": 0.85,
    "DIRTY": 0.75,
    "BAD": 0.60,
}

ACCESSORY_BONUS = {
    "box": 0.05,      # 箱子（二手标配，自动带上）
    "manual": 0.02,   # 说明书（二手标配，自动带上）
    "charger": 0.03,  # 充电器
    "other": 0.02,    # 其他配件
    "battery": 0.03,  # 电池
    "lens_cap": 0.02, # 镜头盖
    "strap": 0.01,    # 背带
    "cable": 0.02,    # 线缆
}


def calculate_price(base_price: int, status: str = "CLEAN", accessories: list = None) -> dict:
    """计算推荐价格。

    base_price: 全新基准价（日元）
    status:     Mercari 状态（BRAND_NEW / ALMOST_NEW / CLEAN / LITTLE_DIRTY / DIRTY / BAD）
    accessories: 附件列表，如 ["box", "charger"]
    返回 {low, center, high, multiplier}
    """
    status = str(status).strip().upper()
    multiplier = STATUS_MULTIPLIERS.get(status, STATUS_MULTIPLIERS["CLEAN"])

    bonus = sum(ACCESSORY_BONUS.get(str(a).strip().lower(), 0.0) for a in (accessories or []))
    multiplier = round(multiplier + bonus, 4)

    center = int(round(base_price * multiplier))
    low = int(round(center * 0.9))
    high = int(round(center * 1.1))
    return {"low": low, "center": center, "high": high, "multiplier": multiplier}


if __name__ == "__main__":
    # 手动测试：python -m app.price_engine
    for s in STATUS_MULTIPLIERS:
        print(s, calculate_price(10000, s, ["box", "charger"]))
