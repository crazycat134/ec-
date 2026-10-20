"""定义状态系数与附件加成，价格诊断界面用这些系数估算推荐区间。"""

STATUS_MULTIPLIERS = {
    "BRAND_NEW": 1.00,
    "ALMOST_NEW": 0.95,
    "CLEAN": 0.90,
    "LITTLE_DIRTY": 0.85,
    "DIRTY": 0.75,
    "BAD": 0.60,
}

ACCESSORY_BONUS = {
    "box": 0.05,      # 箱子：此处只定义加成系数，是否加入附件列表由调用方决定。
    "manual": 0.02,   # 说明书：此处只定义加成系数，是否加入附件列表由调用方决定。
    "charger": 0.03,  # 充电器
    "other": 0.02,    # 其他配件
    "battery": 0.03,  # 电池
    "lens_cap": 0.02, # 镜头盖
    "strap": 0.01,    # 背带
    "cable": 0.02,    # 线缆
}
