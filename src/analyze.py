"""把订单流水变成一份人格报告。

这里做的所有事情都是可复算的：
每条指标都能在原始订单里被指出来，每个人格判定都来自四个明确定义的轴。
没有随机，没有"星座式"的分组。
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from nutrition_ref import guess_category, lookup
from personas import AXIS_DESC, AXIS_LABELS, MIN_ORDERS_FOR_PERSONA, Persona, pick_persona

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


# ---------------------------------------------------------------- 小工具


def _scale(value: float, lo: float, hi: float) -> float:
    """把一个经验区间的值映射到 0-100。区间外的值截断。"""
    if hi <= lo:
        return 50.0
    x = (value - lo) / (hi - lo)
    return max(0.0, min(100.0, x * 100.0))


def _norm_entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total <= 1:
        return 0.0
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            h -= p * math.log(p)
    return h / math.log(len(counts))


def parse_time(raw: str) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    # 兼容 "2026-03-14 12:31:00" 这种不带 T 的写法
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.fromisoformat(text) if fmt is None else datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- 营养取值

NUTRI_FIELDS = ("energy", "protein", "fat", "carb", "sodium", "sugar")


def _build_nutrition_map(
    rows: list[dict[str, Any]],
) -> dict[str, tuple[float | None, float | None, float | None, float | None, float | None, float | None]]:
    """把 MCP 拉回来的营养行整理成 name -> 六元组。

    官方数据可能缺字段（麦当劳的营养表里没有糖，只有钙），所以这里保留 None，
    由 _nutrition() 用本地参考值逐字段补齐，而不是粗暴地填 0——
    填 0 会让"平均每单糖摄入"变成 0，那是错的，不是缺的。
    """
    table: dict[str, tuple] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        values: list[float | None] = []
        for field in NUTRI_FIELDS:
            raw = row.get(field)
            if raw is None or raw == "":
                values.append(None)
                continue
            try:
                values.append(float(raw))
            except (TypeError, ValueError):
                values.append(None)
        if not values[0]:  # 连热量都没有，不可用
            continue
        table[name] = tuple(values)  # type: ignore[assignment]
    return table


def _nutrition(
    name: str,
    category: str,
    table: dict[str, tuple[float | None, ...]],
) -> tuple[float, float, float, float, float, float]:
    """优先用 MCP 的真实营养数据（逐字段），缺失字段才回落到本地参考表。"""
    local = lookup(name, category)
    remote = table.get(name)
    if remote is None:
        for known, values in table.items():
            if known in name or name in known:
                remote = values
                break
    if remote is None:
        return local
    return tuple(  # type: ignore[return-value]
        r if r is not None else l for r, l in zip(remote, local)
    )


# ---------------------------------------------------------------- 结果容器


@dataclass
class Analysis:
    # 数据来源
    source: str = "unknown"
    range_start: str = ""
    range_end: str = ""
    span_days: int = 0

    # 基础
    order_count: int = 0
    active_days: int = 0

    # 金额
    total_pay: float = 0.0
    total_original: float = 0.0
    saved: float = 0.0
    discount_rate: float = 0.0
    pay_ratio: float = 100.0
    avg_pay: float = 0.0
    coupon_ratio: float = 0.0

    # 时间
    peak_hour: int = 12
    peak_weekday: int = 0
    hour_hist: list[int] = field(default_factory=lambda: [0] * 24)
    weekday_hist: list[int] = field(default_factory=lambda: [0] * 7)
    heatmap: list[list[int]] = field(default_factory=lambda: [[0] * 24 for _ in range(7)])
    lunch_ratio: float = 0.0
    night_ratio: float = 0.0
    morning_ratio: float = 0.0
    evening_ratio: float = 0.0
    weekend_ratio: float = 0.0
    long_streak: int = 0
    hour_entropy: float = 0.0
    busiest_hour_label: str = ""

    # 品类
    top_items: list[tuple[str, int]] = field(default_factory=list)
    top1_item: str = ""
    top1_count: int = 0
    top1_ratio: float = 0.0
    anchor_item: str = ""      # 主品（汉堡类）里的头号，用于文案与隐藏搭配
    anchor_count: int = 0
    anchor_ratio: float = 0.0
    sku_count: int = 0
    sku_density: float = 0.0
    repeat_ratio: float = 0.0
    combo_diversity: float = 0.0   # 不同搭配形态数 / 订单数，越低越"专一"
    combo_count: int = 0
    top_combo_desc: str = ""
    top_combo_count: int = 0
    active_density: float = 0.0    # 活跃天 / 跨度天
    category_share: dict[str, int] = field(default_factory=dict)
    sweet_share: float = 0.0
    treat_share: float = 0.0
    dessert_count: int = 0
    dessert_spend: float = 0.0
    monthly: list[tuple[str, int]] = field(default_factory=list)

    # 营养（每单平均）
    avg_energy: float = 0.0
    avg_protein: float = 0.0
    avg_fat: float = 0.0
    avg_sodium: float = 0.0
    avg_sugar: float = 0.0

    # 人格
    axes: dict[str, int] = field(default_factory=dict)
    persona: Persona | None = None
    primary_axis: str = ""
    secondary_axis: str = ""
    low_sample: bool = False

    # 细节
    first_order_date: str = ""
    most_expensive: dict[str, Any] = field(default_factory=dict)
    cheapest: dict[str, Any] = field(default_factory=dict)
    hidden_combo: dict[str, str] | None = None
    channel_share: dict[str, int] = field(default_factory=dict)

    # 渲染上下文
    ctx: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------- 主流程


def analyze(payload: dict) -> Analysis:
    """payload: {"meta": {...}, "orders": [...]}"""
    orders = [o for o in (payload.get("orders") or []) if isinstance(o, dict)]
    meta = payload.get("meta") or {}
    res = Analysis(source=str(meta.get("source") or "mcp"))
    nut_table = _build_nutrition_map(payload.get("nutrition") or [])

    # 清洗 + 排序
    cleaned: list[dict[str, Any]] = []
    for raw in orders:
        ts = parse_time(raw.get("createdAt") or raw.get("orderTime") or "")
        if ts is None:
            continue
        items = [
            it for it in (raw.get("items") or [])
            if isinstance(it, dict) and (it.get("name") or it.get("productName"))
        ]
        if not items:
            continue
        cleaned.append({"ts": ts, "raw": raw, "items": items})
    cleaned.sort(key=lambda c: c["ts"])

    if not cleaned:
        res.ctx = {"empty": True}
        res.persona = pick_persona({"loyalty": 0, "ritual": 0, "gratification": 0, "optimizer": 0}, 0)[0]
        res.low_sample = True
        return res

    res.order_count = len(cleaned)
    res.range_start = cleaned[0]["ts"].strftime("%Y-%m-%d")
    res.range_end = cleaned[-1]["ts"].strftime("%Y-%m-%d")
    res.span_days = max((cleaned[-1]["ts"] - cleaned[0]["ts"]).days + 1, 1)
    res.first_order_date = cleaned[0]["ts"].strftime("%Y年%m月%d日")

    item_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    item_qty_total = 0
    combo_signatures: Counter[str] = Counter()
    coupon_orders = 0
    dessert_count = 0
    dessert_spend = 0.0
    treat_count = 0
    nutrition_totals = {"energy": 0.0, "protein": 0.0, "fat": 0.0, "sodium": 0.0, "sugar": 0.0}
    active_dates: set[str] = set()
    monthly_counter: Counter[str] = Counter()
    channel_counter: Counter[str] = Counter()
    order_sizes: list[float] = []
    lunch = night = morning = evening = weekend = 0
    priced_orders: list[tuple[float, dict[str, Any]]] = []
    per_item_category: dict[str, str] = {}

    for entry in cleaned:
        ts: datetime = entry["ts"]
        raw = entry["raw"]
        hour, wd = ts.hour, ts.weekday()

        res.hour_hist[hour] += 1
        res.weekday_hist[wd] += 1
        res.heatmap[wd][hour] += 1
        active_dates.add(ts.strftime("%Y-%m-%d"))
        monthly_counter[ts.strftime("%Y-%m")] += 1

        if 11 <= hour < 14:
            lunch += 1
        elif 5 <= hour < 11:
            morning += 1
        elif 14 <= hour < 18:
            pass
        elif 18 <= hour < 21:
            evening += 1
        else:
            night += 1  # 21:00 - 04:59
        if wd >= 5:
            weekend += 1

        channel = str(raw.get("channel") or raw.get("orderType") or raw.get("takeWayType") or "unknown")
        channel_counter[channel] += 1

        # 金额
        pay = _num(raw.get("payPrice") or raw.get("actualAmount") or raw.get("totalAmount") or raw.get("amount"))
        original = _num(raw.get("originalPrice") or raw.get("originAmount"))
        item_sum = 0.0
        sig_parts: list[str] = []
        order_qty = 0
        order_energy = order_protein = order_fat = order_sodium = order_sugar = 0.0

        for it in entry["items"]:
            name = str(it.get("name") or it.get("productName") or "").strip()
            qty = int(_num(it.get("qty") or it.get("quantity") or 1) or 1)
            unit = _num(it.get("unitPrice") or it.get("price"))
            cat = str(it.get("category") or "").strip() or guess_category(name)
            per_item_category[name] = cat

            item_counter[name] += qty
            category_counter[cat] += qty
            item_qty_total += qty
            order_qty += qty
            item_sum += unit * qty
            sig_parts.append(f"{name}x{qty}")

            if cat == "dessert":
                dessert_count += qty
                dessert_spend += unit * qty
            if cat in ("dessert", "coffee"):
                treat_count += qty

            e, p, f, c, s, su = _nutrition(name, cat, nut_table)
            order_energy += e * qty
            order_protein += p * qty
            order_fat += f * qty
            order_sodium += s * qty
            order_sugar += su * qty

        if not original:
            original = item_sum
        if not pay:
            pay = original
        if original and pay and original > 0 and pay <= original:
            res.total_original += original
            res.total_pay += pay
            coupon = str(raw.get("coupon") or raw.get("couponName") or "").strip()
            if pay < original - 0.01 or coupon:
                coupon_orders += 1
            priced_orders.append((pay, raw))

        combo_signatures["|".join(sorted(sig_parts))] += 1
        order_sizes.append(pay)
        nutrition_totals["energy"] += order_energy
        nutrition_totals["protein"] += order_protein
        nutrition_totals["fat"] += order_fat
        nutrition_totals["sodium"] += order_sodium
        nutrition_totals["sugar"] += order_sugar

    # ---- 派生指标
    n = res.order_count
    res.active_days = len(active_dates)
    res.saved = round(res.total_original - res.total_pay, 2)
    if res.total_original > 0:
        res.discount_rate = 1 - res.total_pay / res.total_original
        res.pay_ratio = res.total_pay / res.total_original * 100
    res.avg_pay = round(res.total_pay / max(len(priced_orders), 1), 2)
    res.coupon_ratio = coupon_orders / n
    res.lunch_ratio = lunch / n
    res.night_ratio = night / n
    res.morning_ratio = morning / n
    res.evening_ratio = evening / n
    res.weekend_ratio = weekend / n
    res.hour_entropy = _norm_entropy(res.hour_hist)
    res.peak_hour = max(range(24), key=lambda h: res.hour_hist[h])
    res.peak_weekday = max(range(7), key=lambda d: res.weekday_hist[d])
    res.busiest_hour_label = f"{res.peak_hour:02d}:00–{res.peak_hour + 1:02d}:00"
    res.long_streak = _longest_streak(sorted(active_dates))

    res.top_items = item_counter.most_common(10)
    if res.top_items:
        res.top1_item, res.top1_count = res.top_items[0]
        res.top1_ratio = res.top1_count / n

    # 主品（汉堡）单独统计：薯条可乐是搭售，几乎每单都有，
    # 拿它算"专一"会把所有人都算成忠诚型，所以文案锚点用汉堡类。
    burgers = [(name, cnt) for name, cnt in item_counter.items() if per_item_category.get(name) == "burger"]
    if burgers:
        res.anchor_item, res.anchor_count = max(burgers, key=lambda kv: kv[1])
    else:
        res.anchor_item, res.anchor_count = res.top1_item, res.top1_count
    res.anchor_ratio = res.anchor_count / n

    res.sku_count = len(item_counter)
    res.sku_density = res.sku_count / n
    res.combo_count = len(combo_signatures)
    res.combo_diversity = res.combo_count / n
    res.repeat_ratio = sum(c for c in combo_signatures.values() if c > 1) / n
    res.active_density = res.active_days / res.span_days
    if combo_signatures:
        sig, cnt = combo_signatures.most_common(1)[0]
        res.top_combo_count = cnt
        res.top_combo_desc = " + ".join(
            part.rsplit("x", 1)[0] for part in sig.split("|") if part
        )
    res.category_share = dict(category_counter)
    res.sweet_share = dessert_count / max(item_qty_total, 1)
    res.treat_share = treat_count / max(item_qty_total, 1)
    res.dessert_count = dessert_count
    res.dessert_spend = round(dessert_spend, 2)
    res.channel_share = dict(channel_counter)
    res.monthly = sorted(monthly_counter.items())

    res.avg_energy = nutrition_totals["energy"] / n
    res.avg_protein = nutrition_totals["protein"] / n
    res.avg_fat = nutrition_totals["fat"] / n
    res.avg_sodium = nutrition_totals["sodium"] / n
    res.avg_sugar = nutrition_totals["sugar"] / n

    if priced_orders:
        priced_orders.sort(key=lambda t: t[0])
        res.cheapest = _brief(priced_orders[0][1], priced_orders[0][0])
        res.most_expensive = _brief(priced_orders[-1][1], priced_orders[-1][0])

    # ---- 四轴打分
    # 每个系数和区间都是照着"真实点餐行为"调的：
    # 区间取 5%~95% 分位，避免极端值把某一轴顶死。
    axes = {
        "loyalty": round(
            0.45 * (100 - _scale(res.combo_diversity, 0.05, 0.55))
            + 0.30 * _scale(res.anchor_ratio, 0.02, 0.28)
            + 0.25 * (100 - _scale(res.sku_density, 0.15, 0.75))
        ),
        "ritual": round(
            0.35 * (100 - _scale(res.hour_entropy, 0.45, 0.92))
            + 0.25 * _scale(max(res.lunch_ratio, res.night_ratio), 0.28, 0.75)
            + 0.20 * _scale(res.long_streak, 3, 25)
            + 0.20 * _scale(res.active_density, 0.15, 0.75)
        ),
        "gratification": round(
            0.30 * _scale(res.treat_share, 0.03, 0.35)
            + 0.25 * _scale(res.night_ratio, 0.0, 0.30)
            + 0.25 * _scale(res.avg_pay, 22, 55)
            + 0.20 * _scale(res.weekend_ratio, 0.04, 0.30)
        ),
        "optimizer": round(
            0.55 * _scale(res.discount_rate, 0.02, 0.42)
            + 0.45 * _scale(res.coupon_ratio, 0.05, 0.95)
        ),
    }
    res.axes = axes
    persona, primary, secondary = pick_persona(axes, res.order_count)
    res.persona, res.primary_axis, res.secondary_axis = persona, primary, secondary
    res.low_sample = res.order_count < MIN_ORDERS_FOR_PERSONA

    res.hidden_combo = _hidden_combo(cleaned, item_counter, per_item_category, res.anchor_item)

    # ---- 渲染上下文
    res.ctx = {
        "a_order_count": n,
        "a_active_days": res.active_days,
        "a_top_item": res.anchor_item or "—",
        "a_top1_count": res.anchor_count,
        "a_sku_count": res.sku_count,
        "a_combo_count": res.combo_count,
        "a_top_combo_desc": res.top_combo_desc or "—",
        "a_top_combo_count": res.top_combo_count,
        "a_sku_per_order": f"{n / max(res.sku_count, 1):.1f}",
        "a_night_pct": round(res.night_ratio * 100),
        "a_lunch_pct": round(res.lunch_ratio * 100),
        "a_weekend_pct": round(res.weekend_ratio * 100),
        "a_coupon_pct": round(res.coupon_ratio * 100),
        "a_pay_ratio": round(res.pay_ratio),
        "a_discount_pct": round(res.discount_rate * 100),
        "a_saved": f"{res.saved:,.0f}",
        "a_avg_pay": f"{res.avg_pay:.1f}",
        "a_total_pay": f"{res.total_pay:,.0f}",
        "a_total_original": f"{res.total_original:,.0f}",
        "a_sweet_pct": round(res.sweet_share * 100),
        "a_dessert_count": res.dessert_count,
        "a_dessert_spend": f"{res.dessert_spend:,.0f}",
        "a_dessert_gap": max(round(res.span_days / max(res.dessert_count, 1)), 1),
        "a_peak_hour": res.peak_hour,
        "a_peak_weekday": WEEKDAY_CN[res.peak_weekday],
        "a_peak_weekday_count": res.weekday_hist[res.peak_weekday],
        "a_long_streak": res.long_streak,
    }
    return res


def _num(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("¥", "").replace("元", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _longest_streak(sorted_dates: list[str]) -> int:
    if not sorted_dates:
        return 0
    best = cur = 1
    prev = datetime.strptime(sorted_dates[0], "%Y-%m-%d")
    for text in sorted_dates[1:]:
        cur_day = datetime.strptime(text, "%Y-%m-%d")
        if (cur_day - prev).days == 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
        prev = cur_day
    return best


def _brief(raw: dict[str, Any], amount: float) -> dict[str, Any]:
    names = [str(it.get("name") or it.get("productName") or "") for it in (raw.get("items") or [])]
    return {
        "amount": round(amount, 2),
        "items": " + ".join([x for x in names if x][:4]),
        "date": str(raw.get("createdAt") or raw.get("orderTime") or "")[:10],
    }


def _hidden_combo(
    cleaned: list[dict[str, Any]],
    item_counter: Counter[str],
    categories: dict[str, str],
    anchor: str,
) -> dict[str, str] | None:
    """找一个"你经常点、但从没和主品一起点过"的组合，作为可执行的下一步建议。"""
    if not anchor or len(item_counter) < 3:
        return None

    pair_seen: set[tuple[str, str]] = set()
    for entry in cleaned:
        names = {str(it.get("name") or it.get("productName") or "").strip() for it in entry["items"]}
        # 只有这一单真的包含主品时，才算"配过"
        if anchor in names:
            for name in names:
                pair_seen.add((anchor, name))

    candidates = [
        (name, count) for name, count in item_counter.most_common()
        if name != anchor and (anchor, name) not in pair_seen and categories.get(name) in ("dessert", "drink", "coffee", "snack")
    ]
    if not candidates:
        return None
    name, count = candidates[0]
    return {
        "anchor": anchor,
        "add": name,
        "reason": f"你点过{count}次{name}，但从来没有和{anchor}出现在同一单里。",
    }


def axis_table(res: Analysis) -> list[dict[str, Any]]:
    rows = []
    for key, score in sorted(res.axes.items(), key=lambda kv: kv[1], reverse=True):
        cn, en = AXIS_LABELS[key]
        rows.append({
            "key": key,
            "name": cn,
            "en": en,
            "score": score,
            "desc": AXIS_DESC[key],
            "is_primary": key == res.primary_axis,
        })
    return rows
