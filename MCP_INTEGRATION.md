# MCP 接入说明

本项目通过**麦当劳中国 MCP Server**（Model Context Protocol）读取用户自己的订单与餐品数据。
本文说明实际使用了哪些 MCP 能力、调用链路长什么样，以及每一步为什么这么设计。

---

## 1. 使用的 MCP Server

| 项 | 值 |
| --- | --- |
| Server 名称 | 麦当劳中国 MCP Server（`mcd-mcp`） |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | **Streamable HTTP**（MCP 2025-06-18） |
| 鉴权方式 | 请求头 `Authorization: Bearer <MCP_TOKEN>` |
| 会话机制 | `initialize` 响应头返回 `Mcp-Session-Id`，后续请求必须携带 |
| 限流 | 每个 Token **600 次/分钟**（超限返回 `429`） |
| Token 获取 | <https://open.mcd.cn/mcp> 手机号登录 → 控制台 → 激活 |

**本项目不内置、不代理、不缓存任何 Token。** Token 只从环境变量 `MCD_MCP_TOKEN` 读取。

---

## 2. 实际使用的 Tool

### 2.1 `order-list` —— 历史订单查询（核心能力）

整份报告的所有行为指标都从这个 Tool 的返回里算出来：

| 报告里的东西 | 来自订单的哪个字段 |
| --- | --- |
| 忠诚轴（搭配形态数、主品集中度、SKU 密度） | 每单包含的商品名与数量 |
| 规律轴（小时分布熵、主时段、连续天数、活跃密度） | 下单时间 |
| 犒赏轴（甜品咖啡占比、夜间占比、客单价、周末占比） | 商品品类、下单时间、实付金额 |
| 精算轴（实付/原价、用券率） | 实付价、原价、券名 |
| 常点清单 / 隐藏搭配 | 商品名 + 出现频次 + 同单共现关系 |

调用参数按兼容顺序尝试（不同版本接受的字段名不一致）：

```python
[{"pageSize": 120, "pageNum": 1},
 {"pageSize": 120},
 {"size": 120},
 {"limit": 120},
 {}]
```

### 2.2 `list-nutrition-foods` —— 餐品营养信息（可选增强）

用于把报告里"平均每一单"的营养数值，从**本地参考表**升级为**官方实际数值**。

调用成功后，`analyze.py` 会优先使用 MCP 返回的营养数据；
调用失败或返回为空时，自动回退到 `src/nutrition_ref.py` 里的公开参考值，**主流程不中断**。

这是刻意设计的降级路径：营养是报告的"装饰性深色"，不是结论本身，
它不应该因为一次接口异常就让整份报告出不来。

### 2.3 为什么不使用其他 Tool

`create-order` / `cancel-order` 等写操作**一律不调用**。

这是一个只读的分析工具。它的全部价值在于"看清楚过去发生了什么"，
一旦它能下单，它就从一面镜子变成了一个销售终端——那会让报告里所有的话都变得不可信。

---

## 3. 调用流程

```
main.py
  │
  ├─ collect.fetch_live()
  │    │
  │    ├─①  McDonaldMCPClient()
  │    │     从环境变量读 MCD_MCP_TOKEN，缺失则立刻给出可执行的修复提示
  │    │
  │    ├─②  initialize
  │    │     POST /  {"method":"initialize",
  │    │            "params":{"protocolVersion":"2025-06-18",...}}
  │    │     响应头取 Mcp-Session-Id → 保存到 self.session_id
  │    │
  │    ├─③  notifications/initialized（通知，无返回值）
  │    │
  │    ├─④  tools/call  name="order-list"
  │    │     依次尝试 5 组参数，直到解析出订单数组
  │    │     响应体可能是 application/json 也可能是 text/event-stream
  │    │     → _parse_sse() 逐个 event 拆 data: 行，取最后一条 JSON-RPC 响应
  │    │
  │    ├─⑤  find_orders(payload)
  │    │     递归遍历返回结构，找出"元素像订单"的最长数组
  │    │
  │    ├─⑥  normalize_order() × N
  │    │     按候选键映射到统一结构（时间/商品/金额/券）
  │    │
  │    └─⑦  tools/call  name="list-nutrition-foods"
  │          失败则返回 []，后续用本地参考表兜底
  │
  ├─ analyze.analyze()        ← 纯计算，不再访问网络
  └─ render_md / render_html  ← 纯渲染
```

### 3.1 协议层实现要点

MCP 的 Streamable HTTP 有几个容易踩的地方，`src/mcd_client.py` 逐个处理了：

| 问题 | 处理 |
| --- | --- |
| 响应可能是 SSE 而不是 JSON | 判断 `Content-Type`，是 `text/event-stream` 就走 `_parse_sse()` |
| 一个 SSE 流里可能有多条事件 | 只取含 `result` 或 `error` 的那条，丢弃 progress 通知 |
| `Accept` 头不完整会被拒 | 固定发 `application/json, text/event-stream` |
| 会话需要保持 | 从响应头捕获 `Mcp-Session-Id`，后续每个请求都带上 |
| `initialize` 之后必须发通知 | `_notify("notifications/initialized")` |
| 401 / 429 语义不同 | 分别抛出可读的错误提示（Token 无效 / 触发限流） |
| 通知类请求返回 202 无 body | 只读不解析，异常吞掉不影响主流程 |

全部用 `urllib` 实现，**零第三方依赖**。

### 3.2 字段变更的应对

MCP 返回的字段名在版本之间变化过。`collect.py` 不做固定假设，而是：

```python
TIME_KEYS = ("createdAt","orderTime","createTime","orderDate","createOrderTime",
             "payTime","timestamp","date","time")
ITEM_KEYS = ("items","orderItems","products","productList","itemList","goodsList",...)
NAME_KEYS = ("name","productName","itemName","goodsName","skuName","title")
```

按候选键取值，取不到留空；数组用递归定位而不是写死路径。
真的对不上时，`src/probe.py` 可以把原始返回完整 dump 到 `fixtures/_probe/`，
直接看到结构长什么样，再回来加一个键名即可——不用改算法。

---

## 3.5 真实响应结构（实测记录）

以下结构由 `src/probe.py` 对 `mcd-mcp v1.0.0`（协议 2025-06-18）实测得到，
不是从文档抄的——文档里没有这些细节。

### 统一外层

所有 Tool 的返回都是同一个信封：

```json
{"success": true, "code": 200, "message": "请求成功",
 "datetime": "...", "traceId": "...", "data": <实际内容>}
```

### 一个必须先解决的坑：content 是混排文本

MCP 的 `content[0].text` 并不是纯 JSON，而是长这样：

```
# API Response Information
...
## Response Structure
- **data**: 订单列表 (Type: object)
  - **data.list[].orderId**: 订单编码 (Type: string)
  - **data.list[].createTime**: 下单时间 (Type: string)
  ...
## Original Response

{"success":true,"code":200,"data":{...}}
```

直接 `json.loads()` 会失败。`mcd_client.parse_tool_payload()` 的做法是：
截取 `## Original Response` 之后的部分再解析，失败则从尾部逐字符回退重试，
最后才退回纯文本（优惠券类 Tool 返回的就是 Markdown，本来就没有 JSON）。

### `order-list`

**入参：无**（`inputSchema.properties = {}`，不接受分页或日期过滤）。

返回结构（由 Response Structure 段读出的字段表）：

| 字段 | 说明 |
| --- | --- |
| `data.list[]` | 订单列表 |
| `data.list[].orderId` | 订单编码 |
| `data.list[].orderType` | 订单类型 |
| `data.list[].createTime` | 下单时间 |
| `data.list[].storeCode` / `storeName` | 门店 |
| `data.list[].orderStatus` | 订单状态 |
| `data.list[].orderProductList[]` | 商品列表 |
| `data.list[].orderProductList[].productName` | 商品名称 |
| `data.list[].orderProductList[].quantity` | 数量 |
| `data.list[].orderProductList[].comboItemList[]` | 套餐子项 |
| `data.list[].realTotalAmount` | 总金额 |

实测一个**零消费账号**返回的是 `"data": {}`——不是空数组，也不是 null。
所以 `collect.py` 对这种情况单独判断，给出「账号没有历史订单」的准确提示，
而不是笼统地报「接口结构变了」。

> 这条限制值得写进 README：MCP 只能读到通过官方渠道（APP / 小程序 / 官网）下的单。
> 在柜台和自助点餐机买的不会进来。这决定了这个作品在真实用户那里的可用面。

### `list-nutrition-foods`

**入参：无**。返回 156 条餐品营养数据，但 `data` 不是 JSON 数组，而是一张**紧凑表格文本**：

```
[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
  猪柳麦满分,null,1288,308,16,16,24,781,213
  中薯条,null,1210,289,4,12,38,165,18
  ...
```

格式是 `[行数]{列名}` 后跟逗号分隔的数据行。`collect._parse_compact_table()` 负责解析。

**注意字段缺口**：官方表里有 `energyKcal`、`protein`、`fat`、`carbohydrate`、`sodium`、`calcium`，
**没有糖（sugar）**。所以 `analyze._build_nutrition_map()` 对缺失字段保留 `None`，
再由 `_nutrition()` 逐字段回落到本地参考表——而不是填 0。
填 0 会让"平均每单糖摄入"这个数字变成 0，那是错的，不是缺的。

实测差异（官方值 vs 项目原来的估算值）：

| 餐品 | 官方 kcal | 原估算 | 偏差 |
| --- | --- | --- | --- |
| 巨无霸 | 513 | 550 | +7% |
| 中薯条 | 289 | 340 | +18% |

这个偏差本身就是接入真实数据的价值——估算表能用来看趋势，但不能用来下结论。

---

## 4. 业务价值

### 4.1 对用户：把"消费记录"变成"自我认知"

麦当劳的订单记录本身只是流水，用户不会去看。这个项目做了三件事：

1. **归因**：把散落的订单归纳成四个可解释的行为维度
2. **命名**：给这个形状一个人格化的名字（并提供一句话浓缩）
3. **举证**：把每个判断对应的原始数据摊开——用户可以逐条核对

第 3 点是最关键的。市面上所有"人格测试"都是黑箱，用户只能信或不信。
这个项目的结果是**可证伪的**：报告说你有 91% 的订单用了券，你可以自己数。

### 4.2 对 MCP 生态：一个只读、可复算的示范

- 展示了 MCP 在"**分析型**"场景下的用法：不是替用户执行操作，而是读懂用户的历史
- `mcd_client.py` 是一个可以直接复用的零依赖 MCP 客户端实现
- 全程不触碰写操作，不涉及支付，不产生任何实际消费

### 4.3 对商家（如果这个思路被采用）

报告里最有价值的不是人格名，是那些**用户自己都不知道的事实**：

- 一个人一年点了 229 单，只形成 14 种搭配 —— 菜单对他其实是无效的
- 20% 的订单在 21 点之后，且深夜那单几乎必点同一个品 —— 这是一个明确的、尚未被单独运营的时段
- 91% 的订单用券，但客单价并不低 —— 这不是价格敏感，是"不愿意多付"

这些结论都不需要问卷，只需要订单。而且它们是**用户愿意主动看、主动分享**的形态。

---

## 5. 安全与合规

- **只读**：不调用任何下单、取消、支付类 Tool
- **凭据**：Token 仅从环境变量读取，不进代码、不进日志、不进 git（见 `.gitignore`）
- **数据**：订单只在本机内存中处理；输出到 `reports/` 的报告不含订单号、门店地址、手机号
- **配置示例**：`mcp-config.example.json` 仅使用环境变量占位符，不含任何真实凭据
- **定位**：本项目为参赛作品，由参赛者独立开发，**非麦当劳官方产品**；
  餐品信息与价格以麦当劳官方渠道为准

---

## 6. 自行验证

```bash
# 1. 检查接口可用性 + 把真实返回结构 dump 下来
export MCD_MCP_TOKEN=你的token
python src/probe.py

# 产物：fixtures/_probe/tools.json      所有工具及其 inputSchema
#      fixtures/_probe/order-list.json  订单接口的真实返回

# 2. 只用订单数据出报告
python src/main.py
```

`probe.py` 的存在是为了让这个项目在接口变化时**仍然能被别人接手**——
下一个维护者不需要猜，跑一次就知道结构长什么样。
