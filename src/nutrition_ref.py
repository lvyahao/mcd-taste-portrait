"""麦当劳常见餐品的营养成分参考值。

用途：当 MCP 的 list-nutrition-foods 没有覆盖某个餐品（或离线演示时），
用这张表兜底，保证营养画像不出现大块空洞。

口径：每 1 份，能量 kcal / 蛋白质·脂肪·碳水·糖 g / 钠 mg。
数值为公开资料整理的近似值，仅用于趋势与相对比较，
不作为医学或营养建议——这与麦当劳官方口径一致。
"""

from __future__ import annotations

# name -> (energy_kcal, protein_g, fat_g, carb_g, sodium_mg, sugar_g)
NUTRITION_REF: dict[str, tuple[float, float, float, float, float, float]] = {
    "巨无霸": (550, 26, 30, 42, 930, 9),
    "麦辣鸡腿堡": (470, 22, 22, 44, 1100, 6),
    "板烧鸡腿堡": (470, 26, 21, 43, 900, 8),
    "双层吉士汉堡": (450, 25, 24, 33, 1100, 7),
    "麦香鸡": (400, 20, 18, 38, 800, 5),
    "麦乐鸡5块": (250, 15, 15, 12, 500, 0),
    "中薯条": (340, 4, 16, 43, 260, 0),
    "大薯条": (460, 5, 22, 58, 350, 0),
    "麦辣鸡翅2块": (260, 14, 17, 11, 620, 0),
    "那么大鸡排": (390, 20, 22, 30, 780, 1),
    "可口可乐中": (190, 0, 0, 48, 40, 48),
    "雪碧中": (180, 0, 0, 45, 45, 45),
    "美式咖啡": (5, 0, 0, 1, 5, 0),
    "拿铁": (150, 8, 8, 12, 100, 11),
    "麦旋风奥利奥": (340, 7, 12, 50, 200, 42),
    "原味甜筒": (150, 4, 4, 25, 70, 20),
    "香芋派": (260, 3, 13, 33, 180, 12),
    "猪柳蛋麦满分": (400, 20, 21, 33, 800, 3),
    "吉士蛋麦满分": (300, 15, 14, 28, 700, 3),
}

# 分类兜底：名称里出现这些词时的粗略估值
CATEGORY_FALLBACK: dict[str, tuple[float, float, float, float, float, float]] = {
    "burger": (450, 23, 22, 38, 900, 7),
    "snack": (300, 8, 16, 32, 400, 1),
    "drink": (180, 0, 0, 45, 40, 45),
    "coffee": (110, 5, 5, 10, 60, 9),
    "dessert": (250, 5, 9, 37, 150, 28),
    "breakfast": (350, 18, 18, 30, 750, 3),
}

# 关键词 -> 分类（用于 MCP 只给名称的场景）
CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    ("咖啡", "coffee"),
    ("拿铁", "coffee"),
    ("美式", "coffee"),
    ("可乐", "drink"),
    ("雪碧", "drink"),
    ("可乐", "drink"),
    ("芬达", "drink"),
    ("茶", "drink"),
    ("汁", "drink"),
    ("奶昔", "dessert"),
    ("甜筒", "dessert"),
    ("新地", "dessert"),
    ("麦旋风", "dessert"),
    ("派", "dessert"),
    ("蛋糕", "dessert"),
    ("麦满分", "breakfast"),
    ("薯饼", "breakfast"),
    ("薯条", "snack"),
    ("麦乐鸡", "snack"),
    ("鸡翅", "snack"),
    ("鸡排", "snack"),
    ("鸡块", "snack"),
    ("堡", "burger"),
]


def guess_category(name: str) -> str:
    for keyword, category in CATEGORY_KEYWORDS:
        if keyword in name:
            return category
    return "snack"


def lookup(name: str, category: str | None = None) -> tuple[float, float, float, float, float, float]:
    """按名称精确匹配 -> 包含匹配 -> 分类兜底。"""
    if name in NUTRITION_REF:
        return NUTRITION_REF[name]

    # 包含匹配：处理"M记中薯条"这类带前缀的写法
    for known, value in NUTRITION_REF.items():
        if known in name or name in known:
            return value

    cat = category or guess_category(name)
    return CATEGORY_FALLBACK.get(cat, CATEGORY_FALLBACK["snack"])
