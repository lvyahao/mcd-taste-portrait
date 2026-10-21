"""麦门人格 · 口味年报 —— 命令行入口。

用法：
    python src/main.py --demo           # 用内置演示数据出报告（不需要 Token）
    python src/main.py                  # 从麦当劳 MCP 拉真实订单出报告（需要 MCD_MCP_TOKEN）
    python src/main.py --out reports    # 指定输出目录
    python src/main.py --json           # 额外导出中间结果，方便二次分析
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from analyze import analyze, axis_table  # noqa: E402
from collect import fetch_live, load_demo  # noqa: E402
from mcd_client import MCPError  # noqa: E402
from render_html import render_html  # noqa: E402
from render_md import render_markdown  # noqa: E402

ROOT = os.path.dirname(HERE)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mcd-taste-portrait",
        description="把麦当劳订单流水变成一份口味人格报告",
    )
    parser.add_argument("--demo", action="store_true", help="使用内置演示数据，不需要 MCP Token")
    parser.add_argument("--input", help="从本地 JSON 文件读取订单（自定义数据源）")
    parser.add_argument("--out", default=os.path.join(ROOT, "reports"), help="输出目录")
    parser.add_argument("--json", action="store_true", help="额外导出中间结果 analysis.json")
    parser.add_argument("--quiet", action="store_true", help="不打印摘要")
    args = parser.parse_args()

    # ---- 1. 取数
    try:
        if args.input:
            with open(args.input, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        elif args.demo:
            payload = load_demo()
        else:
            payload = fetch_live()
    except MCPError as exc:
        print(f"\n[取数失败] {exc}\n", file=sys.stderr)
        print("提示：先用 --demo 跑一遍，确认报告样式；接真实数据时再配 MCD_MCP_TOKEN。", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print(f"[取数失败] 找不到文件：{args.input}", file=sys.stderr)
        return 2

    # ---- 2. 分析
    res = analyze(payload)

    # ---- 3. 输出
    os.makedirs(args.out, exist_ok=True)
    md_path = os.path.join(args.out, "report.md")
    html_path = os.path.join(args.out, "report.html")

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(res))
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(res))

    if args.json:
        dump_path = os.path.join(args.out, "analysis.json")
        with open(dump_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "source": res.source,
                    "order_count": res.order_count,
                    "range": [res.range_start, res.range_end],
                    "axes": res.axes,
                    "persona": res.persona.name if res.persona else None,
                    "metrics": {
                        "total_pay": res.total_pay,
                        "total_original": res.total_original,
                        "saved": res.saved,
                        "discount_rate": res.discount_rate,
                        "coupon_ratio": res.coupon_ratio,
                        "avg_pay": res.avg_pay,
                        "peak_hour": res.peak_hour,
                        "peak_weekday": res.peak_weekday,
                        "long_streak": res.long_streak,
                        "sku_count": res.sku_count,
                        "combo_count": res.combo_count,
                        "top_items": res.top_items[:10],
                        "hidden_combo": res.hidden_combo,
                    },
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )

    if not args.quiet:
        print("")
        print("  麦门人格 · 口味年报")
        print("  " + "─" * 46)
        if res.order_count:
            print(f"  数据源      {res.source}　{res.order_count} 笔 / {res.active_days} 个活跃日")
            print(f"  区间        {res.range_start} — {res.range_end}")
            print(f"  你的人格    {res.persona.mark}　{res.persona.name}（{res.persona.en}）")
            print(f"  {res.persona.punchline}")
            print("  " + "─" * 46)
            for row in axis_table(res):
                flag = " ← 主导" if row["is_primary"] else ""
                bar = "█" * round(row["score"] / 100 * 22)
                print(f"  {row['name']}  {row['score']:>3}  {bar:<22}{flag}")
            print("  " + "─" * 46)
            print(f"  省下        ¥{res.saved:,.0f}　实付是原价的 {res.pay_ratio:.0f}%")
            print(f"  峰值        {res.busiest_hour_label}　最长连续 {res.long_streak} 天")
            if res.hidden_combo:
                hc = res.hidden_combo
                print(f"  没试过的    {hc['anchor']} + {hc['add']}")
        else:
            print("  没有找到可用的订单数据。")
        print("  " + "─" * 46)
        print(f"  Markdown    {md_path}")
        print(f"  HTML        {html_path}")
        print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
