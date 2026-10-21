"""生成演示订单数据。

演示数据不是随机噪声，而是按一个具体的人写出来的：
一个在北京工作的上班族，工作日午间在写字楼楼下解决午饭，
加班到深夜会用一顿高热量的东西犒赏自己，夏天周末会为了甜品出门。

只有真实的使用痕迹才能让报告有意思，所以这里刻意保留了
"工作日照常"和"深夜破防"两种模式之间的落差。

用法： python fixtures/build_demo.py
产物： fixtures/demo_orders.json
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "demo_orders.json")

random.seed(1024)

# ---------------------------------------------------------------- 菜单（真实菜单名 + 合理定价）
MENU = {
    "巨无霸": (26.0, "burger"),
    "麦辣鸡腿堡": (23.0, "burger"),
    "板烧鸡腿堡": (23.5, "burger"),
    "双层吉士汉堡": (18.0, "burger"),
    "麦香鸡": (15.0, "burger"),
    "麦乐鸡5块": (15.5, "snack"),
    "中薯条": (12.5, "snack"),
    "大薯条": (15.0, "snack"),
    "麦辣鸡翅2块": (13.0, "snack"),
    "那么大鸡排": (17.0, "snack"),
    "可口可乐中": (10.5, "drink"),
    "雪碧中": (10.5, "drink"),
    "美式咖啡": (15.0, "coffee"),
    "拿铁": (19.0, "coffee"),
    "麦旋风奥利奥": (14.5, "dessert"),
    "原味甜筒": (4.0, "dessert"),
    "香芋派": (8.0, "dessert"),
    "猪柳蛋麦满分": (16.5, "breakfast"),
    "吉士蛋麦满分": (14.0, "breakfast"),
}

STORES = [
    "麦当劳(中关村大街店)",
    "麦当劳(知春路店)",
    "麦当劳(五道口购物中心店)",
    "麦当劳(西二旗地铁站店)",
    "麦当劳(望京SOHO店)",
]

# 组合模板：(情境, [(品名, 数量)...], 券名, 实付)
COMBOS = {
    "lunch_spicy": ([("麦辣鸡腿堡", 1), ("中薯条", 1), ("可口可乐中", 1)], "1+1随心配+中薯条", 29.5),
    "lunch_grill": ([("板烧鸡腿堡", 1), ("中薯条", 1), ("可口可乐中", 1)], "超值三件套", 30.0),
    "lunch_classic": ([("巨无霸", 1), ("中薯条", 1), ("可口可乐中", 1)], "超值三件套", 31.0),
    "lunch_double": ([("双层吉士汉堡", 1), ("中薯条", 1), ("雪碧中", 1)], "1+1随心配+中薯条", 26.0),
    "lunch_nugget": ([("麦乐鸡5块", 1), ("中薯条", 1), ("可口可乐中", 1)], "小食组合券", 25.0),
    "lunch_chicken": ([("那么大鸡排", 1), ("麦辣鸡翅2块", 1), ("可口可乐中", 1)], "小食组合券", 28.0),
    "night_bigmac": ([("巨无霸", 1), ("大薯条", 1), ("麦旋风奥利奥", 1)], "夜宵满减", 42.0),
    "night_spicy": ([("麦辣鸡腿堡", 1), ("麦辣鸡翅2块", 1), ("可口可乐中", 1)], "夜宵满减", 33.0),
    "night_only": ([("麦辣鸡腿堡", 1), ("可口可乐中", 1)], "夜宵满减", 26.0),
    "breakfast": ([("猪柳蛋麦满分", 1), ("美式咖啡", 1)], "早餐组合", 19.0),
    "breakfast_light": ([("吉士蛋麦满分", 1), ("美式咖啡", 1)], "早餐组合", 17.0),
    "weekend_sweet": ([("麦旋风奥利奥", 1), ("原味甜筒", 1)], "", 18.5),
    "weekend_pie": ([("香芋派", 1), ("拿铁", 1)], "", 27.0),
    "evening_mcchicken": ([("麦香鸡", 1), ("中薯条", 1)], "1+1随心配", 17.5),
}

# 情境权重（模拟一年的节奏）
LUNCH = ["lunch_spicy", "lunch_grill", "lunch_classic", "lunch_double", "lunch_nugget", "lunch_chicken"]
LUNCH_W = [34, 20, 14, 12, 12, 8]


def price_of(combo_key: str) -> float:
    items = COMBOS[combo_key][0]
    return round(sum(MENU[name][0] * qty for name, qty in items), 2)


def make_order(ts: datetime, combo_key: str, idx: int) -> dict:
    items_def, coupon, pay = COMBOS[combo_key]
    items = [
        {
            "code": f"SKU{abs(hash(name)) % 90000 + 10000}",
            "name": name,
            "category": MENU[name][1],
            "qty": qty,
            "unitPrice": MENU[name][0],
        }
        for name, qty in items_def
    ]
    original = price_of(combo_key)
    hour = ts.hour
    if 11 <= hour <= 13:
        channel = random.choice(["pickup", "pickup", "delivery", "dinein"])
    elif hour <= 10:
        channel = "pickup"
    elif hour >= 21:
        channel = random.choice(["delivery", "delivery", "pickup"])
    else:
        channel = random.choice(["dinein", "pickup"])

    return {
        "orderId": f"{ts:%Y%m%d}{idx:04d}",
        "createdAt": ts.isoformat(),
        "channel": channel,
        "storeName": random.choice(STORES),
        "items": items,
        "originalPrice": original,
        "payPrice": pay,
        "coupon": coupon,
    }


def build() -> dict:
    orders: list[dict] = []
    idx = 0
    start = datetime(2025, 10, 24, tzinfo=CST)
    end = datetime(2026, 10, 20, tzinfo=CST)

    day = start
    while day <= end:
        weekday = day.weekday()  # 0=Mon
        is_weekend = weekday >= 5

        # 工作日：午间是主战场，偶尔早餐、偶尔加班夜宵
        if not is_weekend:
            if random.random() < 0.45:
                idx += 1
                ts = day.replace(hour=random.choice([11, 12, 12, 12, 13]), minute=random.randint(0, 59))
                orders.append(make_order(ts, random.choices(LUNCH, weights=LUNCH_W)[0], idx))
            if random.random() < 0.10:
                idx += 1
                ts = day.replace(hour=random.choice([8, 8, 9]), minute=random.randint(0, 59))
                orders.append(make_order(ts, random.choice(["breakfast", "breakfast_light"]), idx))
            if random.random() < 0.16:
                idx += 1
                ts = day.replace(hour=random.choice([22, 23, 23]), minute=random.randint(0, 59))
                orders.append(
                    make_order(ts, random.choices(["night_bigmac", "night_spicy", "night_only"], [45, 35, 20])[0], idx)
                )
            if random.random() < 0.08:
                idx += 1
                ts = day.replace(hour=random.choice([19, 20]), minute=random.randint(0, 59))
                orders.append(make_order(ts, "evening_mcchicken", idx))
        else:
            # 周末：为了甜品和咖啡出门，量少但稳定
            if random.random() < 0.22:
                idx += 1
                ts = day.replace(hour=random.choice([15, 16, 16, 17]), minute=random.randint(0, 59))
                orders.append(make_order(ts, random.choice(["weekend_sweet", "weekend_pie"]), idx))
            if random.random() < 0.06:
                idx += 1
                ts = day.replace(hour=13, minute=random.randint(0, 59))
                orders.append(make_order(ts, "lunch_classic", idx))

        day += timedelta(days=1)

    orders.sort(key=lambda o: o["createdAt"])
    return {
        "meta": {
            "source": "demo",
            "seed": 1024,
            "note": "演示数据，用于在没有真实订单的情况下体验完整报告效果。",
            "generatedAt": datetime.now(CST).isoformat(timespec="seconds"),
            "orderCount": len(orders),
            "rangeStart": orders[0]["createdAt"] if orders else "",
            "rangeEnd": orders[-1]["createdAt"] if orders else "",
        },
        "orders": orders,
    }


def main() -> None:
    data = build()
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print(f"已生成 {len(data['orders'])} 笔订单 -> {OUT}")
    print(f"区间：{data['meta']['rangeStart'][:10]} ~ {data['meta']['rangeEnd'][:10]}")


if __name__ == "__main__":
    main()
