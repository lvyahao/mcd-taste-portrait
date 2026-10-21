"""接口探针：把麦当劳 MCP 的真实返回结构落盘，用于对齐数据解析层。

用法：
    python src/probe.py                # 全量探测
    python src/probe.py order-list     # 只探某个工具

产物写入 fixtures/_probe/：
    tools.json          所有工具的 name / description / inputSchema
    <tool>.json         该工具的实际返回
"""

from __future__ import annotations

import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcd_client import MCPError, McDonaldMCPClient  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "_probe")

# 无参或可空参调用的工具，按优先级排列
PROBE_TARGETS = [
    ("now-time-info", {}),
    ("query-my-account", {}),
    ("order-list", {}),
    ("query-my-coupons", {}),
    ("available-coupons", {}),
    ("campaign-calendar", {}),
    ("list-nutrition-foods", {}),
    ("query-lottery-info", {}),
]


def dump(name: str, obj: object) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    return path


def preview(obj: object, limit: int = 1200) -> str:
    text = json.dumps(obj, ensure_ascii=False, indent=2) if not isinstance(obj, str) else obj
    return text if len(text) <= limit else text[:limit] + "\n... (truncated)"


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    client = McDonaldMCPClient()

    print("=" * 70)
    print("初始化 MCP 会话 ...")
    info = client.initialize()
    server = (info.get("serverInfo") or {})
    print(f"  服务器: {server.get('name', '?')} v{server.get('version', '?')}")
    print(f"  协议:   {info.get('protocolVersion', '?')}")
    print(f"  会话ID: {client.session_id or '(无)'}")

    print("=" * 70)
    print("拉取工具清单 ...")
    tools = client.list_tools()
    dump("tools", tools)
    print(f"  共 {len(tools)} 个工具")
    for tool in tools:
        print(f"  - {tool.get('name')}")

    targets = [t for t in PROBE_TARGETS if only is None or t[0] == only]
    for name, args in targets:
        print("=" * 70)
        print(f"调用 {name} ...")
        try:
            data = client.call_tool_json(name, args)
            path = dump(name, data)
            print(f"  已保存 -> {path}")
            print(preview(data))
        except MCPError as exc:
            print(f"  [失败] {exc}")
        except Exception as exc:  # noqa: BLE001 - 探针需容错继续
            print(f"  [异常] {exc}")
            traceback.print_exc()

    print("=" * 70)
    print(f"探测完成，产物目录：{OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
