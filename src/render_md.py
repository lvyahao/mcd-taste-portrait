"""终端版报告：Markdown 输出。

给不愿意开浏览器、或者在终端里就想看完的人。
"""

from __future__ import annotations

from analyze import WEEKDAY_CN, Analysis, axis_table
from personas import AXIS_DESC


def _bar(score: int, width: int = 24) -> str:
    filled = round(score / 100 * width)
    return "█" * filled + "·" * (width - filled)


def _pct(v: float, digits: int = 0) -> str:
    return f"{v * 100:.{digits}f}%"


def render_markdown(res: Analysis) -> str:
    if not res.order_count:
        return (
            "# 麦门人格 · 口味年报\n\n"
            "没有找到可用的订单数据。\n\n"
            "如果你刚领到 MCP Token，可能这个账号还没有历史订单；\n"
            "可以先运行 `python src/main.py --demo` 看看演示报告长什么样。\n"
        )

    p = res.persona
    lines: list[str] = []
    add = lines.append

    add(f"# 麦门人格 · 口味年报")
    add("")
    add(f"**{res.range_start} — {res.range_end}　{res.order_count} 笔订单　{res.active_days} 个活跃日**")
    add("")
    add("---")
    add("")
    add(f"## 你的印记：**{p.mark}**")
    add("")
    add(f"### {p.name}")
    add(f"*{p.en}*")
    add("")
    add(f"> {p.punchline}")
    add("")
    add(p.summary)
    add("")
    add(f"**你的小毛病**：{p.flaw}")
    add("")
    if res.low_sample:
        add(f"> **样本不足**：这份报告只基于 {res.order_count} 笔订单。"
            "低于 8 笔时，时间分布、复购率这类指标虽然算得出来，但不代表你的习惯，"
            "所以这里给的是兜底人格，而不是一个看起来很像结论的结论。")
        add("")
    add("---")
    add("")
    add("## 四个轴")
    add("")
    for row in axis_table(res):
        star = " ←主导" if row["is_primary"] else ""
        add(f"`{row['name']}` {row['score']:>3}  {_bar(row['score'])}  {AXIS_DESC[row['key']]}{star}")
    add("")
    add("---")
    add("")
    add("## 为什么这么判断")
    add("")
    for idx, ev in enumerate(p.evidence, 1):
        add(f"{idx}. {ev.format(**res.ctx)}")
    add("")
    add("---")
    add("")
    add("## 这一年，你的数字")
    add("")
    add("| 指标 | 数值 |")
    add("| --- | --- |")
    add(f"| 订单数 | {res.order_count} 笔 |")
    add(f"| 活跃天数 | {res.active_days} 天（跨度 {res.span_days} 天） |")
    add(f"| 实付总额 | ¥{res.total_pay:,.0f} |")
    add(f"| 原价总额 | ¥{res.total_original:,.0f} |")
    add(f"| 一共省下 | ¥{res.saved:,.0f}（{_pct(res.discount_rate, 1)}） |")
    add(f"| 平均实付是原价的 | {res.pay_ratio:.0f}% |")
    add(f"| 用券订单占比 | {_pct(res.coupon_ratio)} |")
    add(f"| 客单价 | ¥{res.avg_pay:.1f} |")
    add(f"| 峰值时段 | {res.busiest_hour_label} |")
    add(f"| 最常下单的日子 | {WEEKDAY_CN[res.peak_weekday]}（{res.weekday_hist[res.peak_weekday]} 次） |")
    add(f"| 最长连续下单 | {res.long_streak} 天 |")
    add(f"| 点过的不同商品 | {res.sku_count} 种 |")
    add(f"| 形成的搭配形态 | {res.combo_count} 种 |")
    add(f"| 平均每单热量 | {res.avg_energy:.0f} kcal |")
    add("")
    add("---")
    add("")
    add("## 你的时间表")
    add("")
    add("```")
    add("时段分布（每小时订单数）")
    for hour in range(24):
        count = res.hour_hist[hour]
        if count == 0:
            continue
        bar = "▇" * min(count, 40)
        add(f"{hour:02d}:00  {bar} {count}")
    add("```")
    add("")
    add("按周分布：")
    add("")
    for idx, name in enumerate(WEEKDAY_CN):
        count = res.weekday_hist[idx]
        add(f"- {name}  {_bar(int(count / max(max(res.weekday_hist), 1) * 100), 30)} {count}")
    add("")
    add("---")
    add("")
    add("## 你的常点清单")
    add("")
    add("| # | 商品 | 次数 |")
    add("| --- | --- | --- |")
    for idx, (name, count) in enumerate(res.top_items, 1):
        add(f"| {idx} | {name} | {count} |")
    add("")
    add("---")
    add("")
    add("## 你的一餐大概长这样")
    add("")
    add(f"- 热量 **{res.avg_energy:.0f} kcal**")
    add(f"- 蛋白质 **{res.avg_protein:.0f} g**")
    add(f"- 脂肪 **{res.avg_fat:.0f} g**")
    add(f"- 钠 **{res.avg_sodium:.0f} mg**")
    add(f"- 糖 **{res.avg_sugar:.0f} g**")
    add("")
    add("（营养数值按常见餐品的参考值折算，仅用于相对比较，不构成营养建议。）")
    add("")
    add("---")
    add("")
    if res.hidden_combo:
        hc = res.hidden_combo
        add("## 一个你大概没试过的组合")
        add("")
        add(f"> **{hc['anchor']} + {hc['add']}**")
        add("")
        add(hc["reason"])
        add("")
        add("下次可以试试。不保证好吃，但保证你没这样点过。")
        add("")
        add("---")
        add("")
    add("## 关于这份报告")
    add("")
    add("数据来自你自己的麦当劳订单记录，所有指标都可以在原始订单里被指出来："
        "没有随机、没有星座式的分组、也没有替你下结论。")
    add("")
    add("人格是一种描述，不是一种诊断。它说的是「你过去这一年怎么吃」，"
        "不是「你是什么人」。想改的话，下一年就变了。")
    add("")
    add("本报告由 mcd-taste-portrait 生成，非麦当劳官方产品。")
    add("")

    return "\n".join(lines)
