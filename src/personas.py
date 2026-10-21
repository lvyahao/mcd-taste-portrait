"""麦门人格体系。

设计原则：
1. 用四个可测量的轴（忠诚 / 规律 / 犒赏 / 精算）定义人格，而不是星座式的随机分组。
   每条轴都能在订单数据里找到对应的行为痕迹，报告里会把这些痕迹摊开给你看。
2. 人格名必须能被截图单独传播——所以每个人格只配一个汉字印记。
3. 不评判。深夜点巨无霸不是"失控"，是"你今天需要它"。

轴上没有好坏，只有形状。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    en: str
    mark: str          # 单字印记，用于报告视觉锚点
    punchline: str     # 一句话，最可能被截图的那句
    summary: str       # 2-3 句解释，第二人称
    flaw: str          # 一句自嘲式的小毛病，防止报告变成夸奖或诊断
    evidence: tuple[str, str]  # 两条证据模板，{key} 由指标填充


# 忠诚家族：麦当劳对你来说是"一个地方"，不是一份菜单
KEEPER = Persona(
    id="keeper",
    name="一号位守夜人",
    en="Keeper of Seat No.1",
    mark="守",
    punchline="你的麦当劳不需要菜单。",
    summary=(
        "你点单的方式像回家：走到同一个柜台，说同一句话，拿到同一样东西。"
        "菜单上的新品你都知道，但你清楚地知道自己为什么不吃。"
        "这种稳定不是懒得选，是你已经替你未来的每一次饥饿做完了决定。"
    ),
    flaw="别人问你推荐什么，你推荐的是自己那份，而且真的觉得那就是最好吃的。",
    evidence=(
        "你的头号单品是{a_top_item}，在{a_order_count}笔订单里出现了{a_top1_count}次。",
        "过去一年你只点过{a_sku_count}种东西，最常见的搭配「{a_top_combo_desc}」重复了{a_top_combo_count}次。",
    ),
)

FIXED_SEAT = Persona(
    id="fixed-seat",
    name="深夜的固定座位",
    en="Same Seat, Later Hours",
    mark="座",
    punchline="白天那单是给身体的，深夜那单才是给情绪的。",
    summary=(
        "你很少在工作日光天化日之下出现在麦当劳。"
        "你的订单集中在别人已经睡下的时段，而且点的东西相当固定——"
        "这不是没得选，这是你在一天结束前，给自己留的一个可控的小时。"
    ),
    flaw="你大概说过很多次「今天早点睡」，然后 23:40 又打开了点餐页。",
    evidence=(
        "你有{a_night_pct}%的订单发生在 21:00 之后，最常出现的时间是 {a_peak_hour} 点。",
        "深夜这一单里，{a_top_item}依然是你的默认答案（共{a_top1_count}次）。",
    ),
)

MUSCLE_MEMORY = Persona(
    id="muscle-memory",
    name="肌肉记忆型点单员",
    en="Muscle-Memory Orderer",
    mark="记",
    punchline="券在哪、怎么叠、点哪个——你的手比脑子快。",
    summary=(
        "你对这套系统的熟悉程度已经到了不用思考的地步：什么时候有券、"
        "哪张跟哪张能叠、哪套组合最划算，全都在手指里而不是在脑子里。"
        "你省下的钱不算多，但你享受的是「没有多花」这件事本身。"
    ),
    flaw="你的优惠券用得比你的健身卡勤。",
    evidence=(
        "你一共只形成了{a_combo_count}种点单组合，最常见的那一种是「{a_top_combo_desc}」，重复了{a_top_combo_count}次。",
        "你有{a_coupon_pct}%的订单用到了券，实付压到原价的{a_pay_ratio}%——这套动作已经不需要思考了。",
    ),
)

# 规律家族：麦当劳对你来说是"一个时钟"
NOON_COG = Persona(
    id="noon-cog",
    name="午间齿轮",
    en="The Noon Cog",
    mark="齿",
    punchline="12:00 到 12:40 之间，你不在工位。",
    summary=(
        "你的麦当劳是一段被精确切出来的时间：从工位消失、走到店里、"
        "拿着同一个纸袋回来。它不浪漫，但它极其可靠——"
        "在这座城市里，能每天准时发生的事已经不多了。"
    ),
    flaw="如果哪天午休被会议吃掉，你那一整天都会有点不对劲。",
    evidence=(
        "{a_lunch_pct}%的订单落在 11:00–14:00，峰值出现在 {a_peak_hour} 点。",
        "最长的一次，你连续{a_long_streak}天都下了单。",
    ),
)

WEDNESDAY = Persona(
    id="wednesday",
    name="周三点餐员",
    en="The Wednesday Regular",
    mark="三",
    punchline="你比活动日历更早知道这周该点什么。",
    summary=(
        "你不是每天都来，但你来的时机准得可疑——"
        "总是在有值得出手的东西的时候。"
        "你把点餐这件事做成了一份每周的小日程，稳定，且带着一点精算的乐趣。"
    ),
    flaw="你会在群里说「这周不点了」，然后周三准时出现。",
    evidence=(
        "你在{a_peak_weekday}下单最多，共{a_peak_weekday_count}次。",
        "有{a_coupon_pct}%的订单用到了券，平均实付是原价的{a_pay_ratio}%。",
    ),
)

FRIDAY = Persona(
    id="friday",
    name="周五仪式官",
    en="The Friday Ritualist",
    mark="仪",
    punchline="这一单不是晚饭，是这周的收尾。",
    summary=(
        "你把麦当劳用成了一个标点符号：一周结束的时候，需要一个动作把它合上。"
        "这顿饭的性价比你不太在意，你在意的是它准时出现。"
        "仪式感不需要贵，需要的是重复。"
    ),
    flaw="如果周五没吃到，你会觉得这周没真正结束。",
    evidence=(
        "你的{a_peak_weekday}订单明显多于其他日子（{a_peak_weekday_count}次）。",
        "其中{a_night_pct}%发生在 21 点之后——收尾往往拖得比较晚。",
    ),
)

# 犒赏家族：麦当劳对你来说是"一套奖励机制"
CONE_REGULAR = Persona(
    id="cone-regular",
    name="甜筒常客",
    en="The Cone Regular",
    mark="甜",
    punchline="你不是来吃饭的，你是来领今天的糖的。",
    summary=(
        "在你的订单里，正餐是配角，甜品才是主角。"
        "你会为了一支甜筒专门下楼，也接受「顺便吃个汉堡」这种合理性包装。"
        "这不叫嘴馋，这叫你找到了一个每天都能兑现的小奖励。"
    ),
    flaw="你算过甜筒的单价，然后说服自己「才四块钱」。",
    evidence=(
        "甜品和饮品占了你全部点单的{a_sweet_pct}%。",
        "你一共点了{a_dessert_count}次甜品——平均每{a_dessert_gap}天一次。",
    ),
)

REASON_OUT = Persona(
    id="reason-out",
    name="周末出门的理由",
    en="A Reason to Go Out",
    mark="由",
    punchline="周末的麦当劳不是刚需，是你给自己找的借口。",
    summary=(
        "工作日的你和麦当劳关系一般，但一到周末你就出现了。"
        "你要的其实不是那口吃的，是一个「该出门了」的信号——"
        "而麦当劳恰好足够便宜、足够近、足够不需要理由。"
    ),
    flaw="你出门前说的是「去走走」，回来时手里拿着纸袋。",
    evidence=(
        "你的周末订单占比达到{a_weekend_pct}%，明显高于工作日的密度。",
        "而且多数集中在下午 {a_peak_hour} 点前后——那正是「没事干」的时段。",
    ),
)

DISCOUNTED_INDULGER = Persona(
    id="discounted-indulger",
    name="券后犒赏家",
    en="The Discounted Indulger",
    mark="券",
    punchline="你舍得花钱，但你更舍得省钱。",
    summary=(
        "你不会为了省钱而吃得将就，也不会为了吃好而无视价格。"
        "你的模式是：先想吃什么，再想办法把它变便宜。"
        "这种人通常过得不错——欲望清楚，方法也清楚。"
    ),
    flaw="省下的那几块钱，最后又拿去买了个甜筒。",
    evidence=(
        "你的客单价是¥{a_avg_pay}，比平均高一截；同时实付只有原价的{a_pay_ratio}%。",
        "{a_coupon_pct}%的订单用了券——你省钱，但不肯降级。",
    ),
)

# 精算家族：麦当劳对你来说是一道题
WINDOW_HUNTER = Persona(
    id="window-hunter",
    name="午市窗口猎人",
    en="The Lunch Window Hunter",
    mark="猎",
    punchline="11:58 你还在算，12:01 你已经下单了。",
    summary=(
        "你把午餐当成一次有时间窗的交易：券的有效期、满减的门槛、"
        "套餐和单点的差价，全都在你脑子里实时跑着。"
        "别人午休是休息，你午休是结算。"
    ),
    flaw="你曾经因为凑满减，多点了一份自己并不想吃的东西。",
    evidence=(
        "你的实付率是{a_pay_ratio}%，全年省下¥{a_saved}。",
        "{a_lunch_pct}%的订单集中在午间两小时——你的战场很窄，但打得很准。",
    ),
)

COUPON_SNIPER = Persona(
    id="coupon-sniper",
    name="满减狙击手",
    en="The Coupon Sniper",
    mark="狙",
    punchline="同一份套餐，你比隔壁桌少付八块。",
    summary=(
        "你对价格的敏感不是因为缺钱，是因为你对「多付了」这件事有生理性反感。"
        "同一份餐，别人按标价买，你能拆成两张券再加一个满减。"
        "这是一种手艺。"
    ),
    flaw="你会在心里默默给隔壁桌算他多花了多少。",
    evidence=(
        "原价累计¥{a_total_original}，你实付¥{a_total_pay}，省了{a_discount_pct}%。",
        "{a_coupon_pct}%的订单用到了优惠，几乎没按标价买过东西。",
    ),
)

PAID_WITH_SAVINGS = Persona(
    id="paid-with-savings",
    name="省下的钱买了麦旋风",
    en="Paid With Savings",
    mark="省",
    punchline="省下来的，最后都花回去了。",
    summary=(
        "你确实会精打细算，但你的精算有一个固定的出口：甜的那部分。"
        "先用券把正餐的价格压下去，再用省下的预算换一点额外的快乐。"
        "这是一种很健康的财政结构，真的。"
    ),
    flaw="你的省钱计划从来没有真正存下过钱。",
    evidence=(
        "你把实付压到了原价的{a_pay_ratio}%，但甜品仍占了{a_sweet_pct}%的点单。",
        "全年省下¥{a_saved}——同一时期你在甜品上花了¥{a_dessert_spend}。",
    ),
)

# 兜底：还没形成模式
NOMAD = Persona(
    id="nomad",
    name="菜单游牧民",
    en="The Menu Nomad",
    mark="野",
    punchline="你和麦当劳还没熟到那个份上，但也没走。",
    summary=(
        "你的订单还没有长出固定的形状：时间不固定、品类不固定、"
        "连优惠用不用都很随机。这不是没特点，这只是说明——"
        "麦当劳对你来说还是「选项之一」，而不是「某个时刻的答案」。"
        "再吃一年，形状自己就出来了。"
    ),
    flaw="你每次都说「随便」，然后真的随便点了一个。",
    evidence=(
        "你的{a_order_count}笔订单分散在{a_active_days}天里，没有一个稳定的时间窗。",
        "你点过{a_sku_count}种东西，最长连续下单只有{a_long_streak}天。",
    ),
)


ALL_PERSONAS: tuple[Persona, ...] = (
    KEEPER, FIXED_SEAT, MUSCLE_MEMORY,
    NOON_COG, WEDNESDAY, FRIDAY,
    CONE_REGULAR, REASON_OUT, DISCOUNTED_INDULGER,
    WINDOW_HUNTER, COUPON_SNIPER, PAID_WITH_SAVINGS,
    NOMAD,
)

# (主导轴, 次导轴) -> 人格
MATRIX: dict[tuple[str, str], Persona] = {
    ("loyalty", "ritual"): KEEPER,
    ("loyalty", "gratification"): FIXED_SEAT,
    ("loyalty", "optimizer"): MUSCLE_MEMORY,
    ("ritual", "loyalty"): NOON_COG,
    ("ritual", "optimizer"): WEDNESDAY,
    ("ritual", "gratification"): FRIDAY,
    ("gratification", "loyalty"): CONE_REGULAR,
    ("gratification", "ritual"): REASON_OUT,
    ("gratification", "optimizer"): DISCOUNTED_INDULGER,
    ("optimizer", "ritual"): WINDOW_HUNTER,
    ("optimizer", "loyalty"): COUPON_SNIPER,
    ("optimizer", "gratification"): PAID_WITH_SAVINGS,
}

AXIS_LABELS = {
    "loyalty": ("忠诚", "Loyalty"),
    "ritual": ("规律", "Ritual"),
    "gratification": ("犒赏", "Gratification"),
    "optimizer": ("精算", "Optimizer"),
}

AXIS_DESC = {
    "loyalty": "你多常点同一批东西",
    "ritual": "你的下单时间有多稳定",
    "gratification": "你多常把这一单当作奖励",
    "optimizer": "你多常为价格动脑子",
}


MIN_ORDERS_FOR_PERSONA = 8
"""低于这个订单量，任何人格判定都是噪声。

1 笔订单的小时分布熵恒为 0，会被算成"规律度 80 分"——数学上成立，语义上荒谬。
与其给出一个注定错误的结论，不如直接承认样本不够。
"""


def pick_persona(axes: dict[str, int], order_count: int = 999) -> tuple[Persona, str, str]:
    """按主导轴 + 次导轴选人格；样本太少或数据太稀薄时退回游牧民。"""
    if order_count < MIN_ORDERS_FOR_PERSONA:
        ranked = sorted(axes.items(), key=lambda kv: kv[1], reverse=True) or [
            ("loyalty", 0), ("ritual", 0), ("gratification", 0), ("optimizer", 0)
        ]
        return NOMAD, ranked[0][0], ranked[1][0]

    ranked = sorted(axes.items(), key=lambda kv: kv[1], reverse=True)
    primary, primary_score = ranked[0]
    secondary, secondary_score = ranked[1]

    if primary_score < 40:
        return NOMAD, primary, secondary

    persona = MATRIX.get((primary, secondary))
    if persona is None:  # 理论上不会发生，兜底防止 KeyError
        persona = MATRIX.get((primary, ranked[2][0]), NOMAD)
    return persona, primary, secondary
