"""数据采集层。

职责：把"麦当劳 MCP 返回的一坨结构未知的 JSON"和"本地演示数据"
统一成同一种订单结构，让下游 analyze 只面对一种形状。

真实接口的字段名可能在版本间变化，所以这里的解析是宽容的：
按候选键取值、递归找数组、缺失字段允许留空。
解析不到的字段会在报告里体现为"—"，而不是让整份报告崩掉。
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable

from mcd_client import MCPError, McDonaldMCPClient

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEMO_PATH = os.path.join(ROOT, "fixtures", "demo_orders.json")

TIME_KEYS = (
    "createdAt", "orderTime", "createTime", "orderDate", "orderCreateTime",
    "payTime", "timestamp", "date", "time",
)
ITEM_KEYS = ("items", "orderItems", "products", "productList", "itemList", "details", "goodsList", "list")
NAME_KEYS = ("name", "productName", "itemName", "goodsName", "skuName", "title")
QTY_KEYS = ("qty", "quantity", "num", "count", "number")
PRICE_KEYS = ("unitPrice", "price", "salePrice", "currentPrice", "amount", "originalPrice")
CODE_KEYS = ("code", "productCode", "skuCode", "itemCode", "goodsCode", "id")


def _first(obj: dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for key in keys:
        if key in obj and obj[key] not in (None, "", [], {}):
            return obj[key]
    return default


def _walk_lists(node: Any, depth: int = 0) -> Iterable[list[Any]]:
    """递归收集所有列表。"""
    if depth > 6:
        return
    if isinstance(node, list):
        yield node
        for child in node[:5]:
            yield from _walk_lists(child, depth + 1)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk_lists(value, depth + 1)


def _looks_like_order(obj: Any) -> bool:
    return isinstance(obj, dict) and _first(obj, TIME_KEYS) is not None


def find_orders(payload: Any) -> list[dict[str, Any]]:
    """在任意嵌套结构里找出订单数组。

    策略：优先选"元素像订单"的最长列表；找不到时间字段时退化为
    "元素里有 items 的最长列表"。
    """
    best: list[dict[str, Any]] = []
    best_score = -1
    for candidate in _walk_lists(payload):
        dicts = [x for x in candidate if isinstance(x, dict)]
        if not dicts:
            continue
        with_time = sum(1 for x in dicts if _looks_like_order(x))
        with_items = sum(1 for x in dicts if _first(x, ITEM_KEYS) is not None)
        score = with_time * 3 + with_items * 2 + len(dicts) * 0.01
        if score > best_score and (with_time or with_items):
            best, best_score = dicts, score
    return best


def normalize_items(raw_items: Any) -> list[dict[str, Any]]:
    if isinstance(raw_items, dict):
        raw_items = _first(raw_items, ITEM_KEYS) or [raw_items]
    if not isinstance(raw_items, list):
        return []

    out: list[dict[str, Any]] = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        name = str(_first(it, NAME_KEYS, "") or "").strip()
        if not name:
            continue
        qty_raw = _first(it, QTY_KEYS, 1)
        try:
            qty = int(float(qty_raw))
        except (TypeError, ValueError):
            qty = 1
        price_raw = _first(it, PRICE_KEYS, 0)
        try:
            price = float(str(price_raw).replace("¥", "").replace(",", "") or 0)
        except (TypeError, ValueError):
            price = 0.0
        out.append({
            "code": str(_first(it, CODE_KEYS, "") or ""),
            "name": name,
            "qty": max(qty, 1),
            "unitPrice": price,
        })
    return out


def normalize_order(raw: dict[str, Any]) -> dict[str, Any] | None:
    items = normalize_items(_first(raw, ITEM_KEYS))
    if not items:
        return None

    pay = _first(raw, ("payPrice", "actualAmount", "totalAmount", "amount", "payAmount", "orderAmount"))
    original = _first(raw, ("originalPrice", "originAmount", "totalOriginAmount", "originalAmount"))
    coupon = _first(raw, ("coupon", "couponName", "couponTitle", "discountDesc", "promotionName"))

    return {
        "orderId": str(_first(raw, ("orderId", "orderNo", "id", "orderCode"), "") or ""),
        "createdAt": str(_first(raw, TIME_KEYS, "") or ""),
        "channel": str(_first(raw, ("channel", "orderType", "takeWayType", "deliveryType", "mode"), "") or ""),
        "storeName": str(_first(raw, ("storeName", "store", "shopName", "restaurantName", "storeCode"), "") or ""),
        "items": items,
        "originalPrice": _to_float(original),
        "payPrice": _to_float(pay),
        "coupon": str(coupon or ""),
    }


def _to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(str(value).replace("¥", "").replace(",", "").replace("元", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _try_call(client: McDonaldMCPClient, tool: str, variants: list[dict[str, Any]]) -> Any:
    last_error: Exception | None = None
    for args in variants:
        try:
            return client.call_tool_json(tool, args)
        except MCPError as exc:
            last_error = exc
            if "401" in str(exc):
                raise  # 鉴权失败不用重试
            continue
    if last_error:
        raise last_error
    return None


def fetch_live(limit: int = 120, verbose: bool = True) -> dict[str, Any]:
    """从麦当劳 MCP 拉取真实历史订单 + 营养数据。"""
    client = McDonaldMCPClient()
    client.initialize()
    if verbose:
        print("  已连接麦当劳 MCP，正在拉取历史订单 ...")

    payload = _try_call(
        client,
        "order-list",
        [
            {"pageSize": limit, "pageNum": 1},
            {"pageSize": limit},
            {"size": limit},
            {"limit": limit},
            {},
        ],
    )

    raw_orders = find_orders(payload)
    if not raw_orders:
        data = payload.get("data") if isinstance(payload, dict) else payload
        if data in ({}, [], None, ""):
            raise MCPError(
                "接口连接正常，但这个麦当劳账号没有可用的历史订单（order-list 返回空）。\n"
                "可能的原因：\n"
                "  · 你平时在柜台 / 自助点餐机买，订单没有进到账号里\n"
                "  · 点餐用的手机号和领 Token 的账号不是同一个\n"
                "  · 订单记录已被清理\n"
                "可以先运行 python src/main.py --demo 查看报告效果。"
            )
        raise MCPError(
            "order-list 有返回数据，但没有解析出订单——接口结构可能变了。\n"
            "请运行 python src/probe.py order-list 查看原始返回，"
            "再按实际字段补充 collect.py 里的候选键。"
        )

    orders = [o for o in (normalize_order(r) for r in raw_orders) if o]
    orders.sort(key=lambda o: o["createdAt"])
    if verbose:
        print(f"  拉到 {len(orders)} 笔订单（{orders[0]['createdAt'][:10]} ~ {orders[-1]['createdAt'][:10]}）")

    nutrition = fetch_nutrition(client, verbose=verbose)

    return {
        "meta": {
            "source": "mcp",
            "orderCount": len(orders),
            "rangeStart": orders[0]["createdAt"] if orders else "",
            "rangeEnd": orders[-1]["createdAt"] if orders else "",
        },
        "orders": orders,
        "nutrition": nutrition,
    }


NUTRI_KEY_MAP = {
    "energy": ("energyKcal", "energy", "calorie", "calories", "kcal", "热量"),
    "protein": ("protein", "proteinG", "蛋白质"),
    "fat": ("fat", "fatG", "脂肪"),
    "carb": ("carbohydrate", "carb", "carbs", "碳水"),
    "sodium": ("sodium", "sodiumMg", "na", "钠"),
    "sugar": ("sugar", "sugarG", "糖"),
    "calcium": ("calcium", "钙"),
}


def _parse_compact_table(text: str) -> list[dict[str, str]]:
    """解析 MCP 返回的紧凑表格文本。

    形如：
        [160]{productName,nutritionDescription,energyKcal,protein,...}:
          猪柳麦满分,null,308,16,...
          中薯条,null,289,4,...

    这是麦当劳 MCP 对列表型数据的统一呈现方式，不是标准 JSON。
    """
    rows: list[dict[str, str]] = []
    if not isinstance(text, str):
        return rows
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines or "{" not in lines[0]:
        return rows

    head = lines[0]
    start, end = head.find("{"), head.find("}")
    if start < 0 or end <= start:
        return rows
    columns = [c.strip() for c in head[start + 1:end].split(",")]
    if not columns:
        return rows

    for line in lines[1:]:
        values = [v.strip() for v in line.split(",")]
        if len(values) != len(columns):
            continue
        rows.append(dict(zip(columns, values)))
    return rows


def fetch_nutrition(client: McDonaldMCPClient, verbose: bool = True) -> list[dict[str, Any]]:
    """拉取餐品营养数据。失败不阻断主流程——analyze 会用本地参考表兜底。"""
    try:
        payload = _try_call(client, "list-nutrition-foods", [{}, {"pageSize": 200}])
    except MCPError as exc:
        if verbose:
            print(f"  [提示] 营养数据拉取失败（{exc}），改用本地参考值。")
        return []

    data = payload.get("data") if isinstance(payload, dict) else payload

    # 形态一：紧凑表格文本
    table_rows: list[dict[str, Any]] = []
    if isinstance(data, str):
        table_rows = _parse_compact_table(data)
    elif isinstance(data, list):
        table_rows = [x for x in data if isinstance(x, dict)]
    elif isinstance(data, dict):
        for candidate in _walk_lists(data):
            dicts = [x for x in candidate if isinstance(x, dict)]
            if dicts and _first(dicts[0], NAME_KEYS) is not None:
                table_rows = dicts
                break

    rows: list[dict[str, Any]] = []
    for raw in table_rows:
        name = str(_first(raw, ("productName",) + NAME_KEYS, "") or "").strip()
        if not name:
            continue
        row: dict[str, Any] = {"name": name}
        for field, keys in NUTRI_KEY_MAP.items():
            value = _first(raw, keys)
            row[field] = _to_float(value) if value not in (None, "", "null") else None
        if not row.get("energy"):
            continue
        rows.append(row)

    if verbose:
        if rows:
            print(f"  拉到 {len(rows)} 条官方餐品营养数据")
        else:
            print("  [提示] 营养数据为空或格式无法识别，改用本地参考值。")
    return rows


def load_demo(path: str | None = None) -> dict[str, Any]:
    target = path or DEMO_PATH
    with open(target, "r", encoding="utf-8") as fh:
        return json.load(fh)
