"""HTML 报告。

这个文件是作品的门面：它需要在一屏之内让人看懂"我是谁"，
并且值得被截图发出去。所以排版优先级是——
人格名 > 那句话 > 证据 > 数字，而不是反过来。

单文件输出，内联 CSS，不依赖任何外部资源（离线可开、可直接截图）。
"""

from __future__ import annotations

from html import escape

from analyze import WEEKDAY_CN, Analysis, axis_table
from personas import AXIS_DESC

CSS = """
:root{
  --red:#C8102E; --red-deep:#8E0B20; --gold:#F2B705;
  --ink:#191512; --ink-2:#3D362F; --muted:#7A7067;
  --line:#E7DDCE; --paper:#FBF7F0; --card:#FFFFFF;
}
*{box-sizing:border-box;margin:0;padding:0}
body{
  background:var(--paper); color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:15px; line-height:1.75; -webkit-font-smoothing:antialiased;
}
.sheet{max-width:880px;margin:0 auto;padding:0 28px 80px}
.serif{font-family:"Songti SC","STSong","SimSun","Noto Serif SC",serif}

/* ---------- Hero ---------- */
.hero{position:relative;padding:72px 0 44px;border-bottom:2px solid var(--ink)}
.kicker{font-size:12px;letter-spacing:.34em;color:var(--red);text-transform:uppercase;font-weight:600;margin-bottom:22px}
.hero-main{display:grid;grid-template-columns:190px 1fr;gap:34px;align-items:center}
.mark{
  font-family:"Songti SC","STSong","SimSun",serif;
  font-size:150px;line-height:.86;color:var(--red);
  border:3px solid var(--red);border-radius:4px;
  display:flex;align-items:center;justify-content:center;
  width:190px;height:190px;letter-spacing:0;
  box-shadow:10px 10px 0 rgba(200,16,46,.09);
}
.p-name{font-size:46px;line-height:1.16;font-weight:700;letter-spacing:-.5px}
.p-en{font-size:12.5px;letter-spacing:.24em;color:var(--muted);text-transform:uppercase;margin-top:10px}
.punch{
  font-family:"Songti SC","STSong","SimSun",serif;
  font-size:25px;line-height:1.5;color:var(--red-deep);
  margin-top:20px;padding-left:16px;border-left:3px solid var(--gold);
}
.meta{margin-top:26px;font-size:12.5px;color:var(--muted);letter-spacing:.04em}
.meta b{color:var(--ink-2);font-weight:600}
.stamp{
  position:absolute;top:52px;right:0;width:96px;height:96px;border:2px solid var(--red);
  border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;
  color:var(--red);transform:rotate(9deg);opacity:.82;
}
.stamp span{font-size:10px;letter-spacing:.16em;line-height:1.5}
.stamp b{font-family:"Songti SC",serif;font-size:21px;line-height:1.1}

/* ---------- 通用分区 ---------- */
section{padding:44px 0;border-bottom:1px solid var(--line)}
section:last-of-type{border-bottom:none}
h2{font-size:12px;letter-spacing:.3em;color:var(--muted);text-transform:uppercase;font-weight:600;margin-bottom:26px}
h2 em{color:var(--red);font-style:normal}
.lede{font-size:17px;line-height:1.95;color:var(--ink-2);max-width:66ch}
.lede + .lede{margin-top:14px}

/* ---------- 四轴 ---------- */
.axis{margin-bottom:20px}
.axis:last-child{margin-bottom:0}
.axis-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:7px}
.axis-name{font-size:15px;font-weight:600}
.axis-name i{font-style:normal;font-size:11px;color:var(--muted);letter-spacing:.18em;margin-left:9px;text-transform:uppercase}
.axis-score{font-family:"Songti SC",serif;font-size:21px;color:var(--red);font-variant-numeric:tabular-nums}
.axis-track{height:7px;background:#EDE4D6;border-radius:4px;overflow:hidden}
.axis-fill{height:100%;background:linear-gradient(90deg,var(--red),#E24B5E);border-radius:4px}
.axis.pri .axis-fill{background:linear-gradient(90deg,var(--red-deep),var(--red))}
.axis-desc{font-size:12px;color:var(--muted);margin-top:5px}
.tag{display:inline-block;font-size:10px;letter-spacing:.14em;background:var(--red);color:#fff;padding:1px 7px;border-radius:2px;margin-left:8px;vertical-align:2px}

/* ---------- 数字 ---------- */
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line)}
.cell{background:var(--card);padding:22px 18px}
.cell .n{font-family:"Songti SC",serif;font-size:33px;line-height:1.1;color:var(--ink);font-variant-numeric:tabular-nums}
.cell .n small{font-size:15px;color:var(--muted);margin-left:2px}
.cell .l{font-size:11.5px;color:var(--muted);margin-top:8px;letter-spacing:.06em}

/* ---------- 热力图 ---------- */
.hm{display:grid;grid-template-columns:46px repeat(24,1fr);gap:3px;align-items:center}
.hm .hl{font-size:10.5px;color:var(--muted)}
.hm .hh{font-size:9.5px;color:var(--muted);text-align:center}
.hm .hc{aspect-ratio:1;border-radius:2px;background:#F0E8DB}
.legend{display:flex;align-items:center;gap:8px;margin-top:16px;font-size:11px;color:var(--muted)}
.legend .sw{display:flex;gap:2px}
.legend .sw i{width:13px;height:13px;border-radius:2px;display:block}

/* ---------- 清单 ---------- */
.rank{display:grid;grid-template-columns:26px 1fr 52px;gap:12px;align-items:center;padding:9px 0;border-bottom:1px dashed var(--line)}
.rank:last-child{border-bottom:none}
.rank .i{font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}
.rank .nm{font-size:14.5px}
.rank .bar{height:5px;background:var(--red);opacity:.75;border-radius:3px;margin-top:6px}
.rank .c{text-align:right;font-size:13px;color:var(--ink-2);font-variant-numeric:tabular-nums}

/* ---------- 营养 ---------- */
.pills{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
.pill{background:var(--card);border:1px solid var(--line);padding:18px 14px;text-align:center}
.pill .v{font-family:"Songti SC",serif;font-size:25px;color:var(--ink)}
.pill .v small{font-size:12px;color:var(--muted)}
.pill .k{font-size:11px;color:var(--muted);margin-top:6px;letter-spacing:.08em}

/* ---------- 彩蛋 ---------- */
.egg{background:var(--ink);color:#F6EFE3;padding:34px 32px;position:relative;overflow:hidden}
.egg::after{content:"＋";position:absolute;right:22px;bottom:-26px;font-size:130px;color:rgba(242,183,5,.12);font-family:serif}
.egg .h{font-size:11px;letter-spacing:.28em;color:var(--gold);margin-bottom:14px}
.egg .combo{font-family:"Songti SC",serif;font-size:30px;line-height:1.4}
.egg .why{font-size:13.5px;color:#C9BFAF;margin-top:14px;max-width:52ch}

/* ---------- 证据 ---------- */
.ev{display:flex;gap:16px;padding:16px 0;border-bottom:1px dashed var(--line)}
.ev:last-child{border-bottom:none}
.ev .num{font-family:"Songti SC",serif;font-size:15px;color:var(--red);flex:0 0 auto;width:22px}
.ev p{font-size:14.5px;color:var(--ink-2)}

/* ---------- 页脚 ---------- */
footer{padding:40px 0 0;border-top:2px solid var(--ink);margin-top:8px}
.fine{font-size:11.5px;color:var(--muted);line-height:1.85}
.flaw{margin-top:24px;padding:18px 20px;background:#F5EDDE;border-left:3px solid var(--gold);font-size:14px;color:var(--ink-2)}
.flaw b{color:var(--ink)}
.warn{margin-top:26px;padding:16px 20px;background:#FFF4F0;border:1px solid #F0C9BE;font-size:13.5px;color:#8A3A22}
.warn b{color:#7A2010}

@media (max-width:760px){
  .sheet{padding:0 18px 60px}
  .hero-main{grid-template-columns:1fr;gap:22px}
  .mark{width:132px;height:132px;font-size:104px}
  .p-name{font-size:34px}
  .punch{font-size:20px}
  .stamp{display:none}
  .grid4{grid-template-columns:repeat(2,1fr)}
  .pills{grid-template-columns:repeat(2,1fr)}
  .hm{grid-template-columns:40px repeat(24,1fr);gap:2px}
}
@media print{
  body{background:#fff}
  section{page-break-inside:avoid}
}
"""


def _heat_color(count: int, max_count: int) -> str:
    if count <= 0:
        return "#F0E8DB"
    alpha = 0.14 + 0.86 * (count / max(max_count, 1)) ** 0.65
    return f"rgba(200,16,46,{alpha:.3f})"


def _section_hero(res: Analysis) -> str:
    p = res.persona
    return f"""
<header class="hero">
  <div class="stamp"><span>麦门人格</span><b>{escape(res.range_end[:4])}</b></div>
  <div class="kicker">McDonald's Taste Portrait</div>
  <div class="hero-main">
    <div class="mark serif">{escape(p.mark)}</div>
    <div>
      <h1 class="p-name serif">{escape(p.name)}</h1>
      <div class="p-en">{escape(p.en)}</div>
      <div class="punch">{escape(p.punchline)}</div>
      <div class="meta">
        <b>{escape(res.range_start)} — {escape(res.range_end)}</b>　·　
        <b>{res.order_count}</b> 笔订单　·　<b>{res.active_days}</b> 个活跃日
      </div>
    </div>
  </div>
</header>"""


def _section_intro(res: Analysis) -> str:
    warn = ""
    if res.low_sample:
        warn = (
            '<div class="warn"><b>样本不足</b>　'
            f"这份报告只基于 {res.order_count} 笔订单。低于 8 笔时，"
            "时间分布、复购率这类指标在数学上算得出来，但不代表你的习惯——"
            "所以这里给的是兜底人格「菜单游牧民」，而不是一个看起来很像结论的结论。"
            "再吃几顿，形状就出来了。</div>"
        )
    return f"""
<section>
  <h2>关于你 <em>/ 01</em></h2>
  <p class="lede">{escape(res.persona.summary)}</p>
  <div class="flaw"><b>你的小毛病</b>　{escape(res.persona.flaw)}</div>
  {warn}
</section>"""


def _section_axes(res: Analysis) -> str:
    rows = []
    for row in axis_table(res):
        pri = " pri" if row["is_primary"] else ""
        tag = '<span class="tag">主导</span>' if row["is_primary"] else ""
        rows.append(f"""
    <div class="axis{pri}">
      <div class="axis-head">
        <div class="axis-name">{escape(row['name'])}<i>{escape(row['en'])}</i>{tag}</div>
        <div class="axis-score">{row['score']}</div>
      </div>
      <div class="axis-track"><div class="axis-fill" style="width:{row['score']}%"></div></div>
      <div class="axis-desc">{escape(AXIS_DESC[row['key']])}</div>
    </div>""")
    return f"""
<section>
  <h2>四个轴 <em>/ 02</em></h2>
  {''.join(rows)}
</section>"""


def _section_numbers(res: Analysis) -> str:
    cells = [
        (f"¥{res.total_pay:,.0f}", "实付总额"),
        (f"¥{res.saved:,.0f}", f"一共省下 · {res.discount_rate * 100:.0f}%"),
        (f"{res.pay_ratio:.0f}<small>%</small>", "实付 / 原价"),
        (f"{res.combo_count}<small>种</small>", "点单组合形态"),
    ]
    html_cells = "".join(
        f'<div class="cell"><div class="n">{v}</div><div class="l">{escape(l)}</div></div>'
        for v, l in cells
    )
    return f"""
<section>
  <h2>这一年的数字 <em>/ 03</em></h2>
  <div class="grid4">{html_cells}</div>
</section>"""


def _section_heatmap(res: Analysis) -> str:
    max_count = max((max(row) for row in res.heatmap), default=0)
    parts = ['<div class="hm">']
    parts.append('<div class="hl"></div>')
    for hour in range(24):
        label = f"{hour}" if hour % 3 == 0 else ""
        parts.append(f'<div class="hh">{label}</div>')
    for wd in range(7):
        parts.append(f'<div class="hl">{WEEKDAY_CN[wd]}</div>')
        for hour in range(24):
            c = res.heatmap[wd][hour]
            parts.append(
                f'<div class="hc" style="background:{_heat_color(c, max_count)}" '
                f'title="{WEEKDAY_CN[wd]} {hour:02d}:00 · {c} 单"></div>'
            )
    parts.append("</div>")

    swatches = "".join(
        f'<i style="background:{_heat_color(int(round(max_count * r)), max_count)}"></i>'
        for r in (0.15, 0.35, 0.55, 0.75, 1.0)
    )
    return f"""
<section>
  <h2>你的节奏 <em>/ 04</em></h2>
  <p class="lede" style="margin-bottom:26px">
    峰值出现在 <b>{escape(res.busiest_hour_label)}</b>，
    最常下单的日子是 <b>{WEEKDAY_CN[res.peak_weekday]}</b>（{res.weekday_hist[res.peak_weekday]} 次），
    最长连续下单 <b>{res.long_streak}</b> 天。
  </p>
  {''.join(parts)}
  <div class="legend"><span>少</span><span class="sw">{swatches}</span><span>多</span></div>
</section>"""


def _section_rank(res: Analysis) -> str:
    rows = []
    top_count = res.top_items[0][1] if res.top_items else 1
    for idx, (name, count) in enumerate(res.top_items[:8], 1):
        width = max(count / top_count * 100, 4)
        rows.append(f"""
    <div class="rank">
      <div class="i">{idx:02d}</div>
      <div><div class="nm">{escape(name)}</div><div class="bar" style="width:{width:.0f}%"></div></div>
      <div class="c">{count}</div>
    </div>""")
    return f"""
<section>
  <h2>常点清单 <em>/ 05</em></h2>
  {''.join(rows)}
</section>"""


def _section_nutrition(res: Analysis) -> str:
    pills = [
        (f"{res.avg_energy:.0f}", "kcal", "热量"),
        (f"{res.avg_protein:.0f}", "g", "蛋白质"),
        (f"{res.avg_fat:.0f}", "g", "脂肪"),
        (f"{res.avg_sodium:.0f}", "mg", "钠"),
        (f"{res.avg_sugar:.0f}", "g", "糖"),
    ]
    html_pills = "".join(
        f'<div class="pill"><div class="v">{v}<small>{u}</small></div><div class="k">{escape(k)}</div></div>'
        for v, u, k in pills
    )
    return f"""
<section>
  <h2>平均每一单 <em>/ 06</em></h2>
  <div class="pills">{html_pills}</div>
  <p class="fine" style="margin-top:18px">
    营养数值按常见餐品的公开参考值折算，仅用于相对比较，不构成营养或医疗建议。
  </p>
</section>"""


def _section_egg(res: Analysis) -> str:
    hc = res.hidden_combo
    if not hc:
        return ""
    return f"""
<section style="padding:0;border-bottom:none">
  <div class="egg">
    <div class="h">一个你大概没试过的组合</div>
    <div class="combo">{escape(hc['anchor'])} ＋ {escape(hc['add'])}</div>
    <div class="why">{escape(hc['reason'])}　下次可以试试——不保证好吃，但保证你没这样点过。</div>
  </div>
</section>"""


def _section_evidence(res: Analysis) -> str:
    items = "".join(
        f'<div class="ev"><div class="num">{idx:02d}</div><p>{escape(ev.format(**res.ctx))}</p></div>'
        for idx, ev in enumerate(res.persona.evidence, 1)
    )
    return f"""
<section>
  <h2>为什么这么判断 <em>/ 07</em></h2>
  {items}
</section>"""


def _footer(res: Analysis) -> str:
    source = "麦当劳 MCP 实时拉取" if res.source == "mcp" else "内置演示数据"
    return f"""
<footer>
  <p class="fine">
    数据来源：{escape(source)}　·　订单区间 {escape(res.range_start)} — {escape(res.range_end)}　·　
    共 {res.order_count} 笔<br>
    四个轴（忠诚 / 规律 / 犒赏 / 精算）均由订单行为直接计算，所有指标都可以在原始订单里被指出来：没有随机，没有星座式分组。<br>
    人格是一种描述，不是一种诊断。它说的是「你过去这一年怎么吃」，不是「你是什么人」。<br><br>
    本报告由开源项目 mcd-taste-portrait 生成，非麦当劳官方产品。
    餐品信息与价格以麦当劳官方渠道为准。
  </p>
</footer>"""


def render_html(res: Analysis) -> str:
    if not res.order_count:
        body = """
<header class="hero">
  <div class="kicker">McDonald's Taste Portrait</div>
  <h1 class="p-name serif">还没有足够的订单</h1>
  <div class="punch">这份报告需要你的历史订单才长得出来。</div>
</header>
<section>
  <p class="lede">没有从麦当劳 MCP 找到可用的历史订单。可能这个账号还没点过，或者接口结构变了。</p>
  <p class="lede">可以先运行 <b>python src/main.py --demo</b> 看看演示报告长什么样。</p>
</section>"""
    else:
        body = (
            _section_hero(res)
            + _section_intro(res)
            + _section_axes(res)
            + _section_numbers(res)
            + _section_heatmap(res)
            + _section_rank(res)
            + _section_nutrition(res)
            + _section_egg(res)
            + _section_evidence(res)
            + _footer(res)
        )

    title = f"{res.persona.name} · 麦门人格" if res.persona else "麦门人格 · 口味年报"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="sheet">
{body}
</div>
</body>
</html>
"""
