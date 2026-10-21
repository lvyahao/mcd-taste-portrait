"""Minimal MCP (Model Context Protocol) Streamable-HTTP client.

纯标准库实现，不依赖 mcp / httpx / requests。
只实现本项目需要的部分：initialize -> tools/list -> tools/call。

参考：MCP 2025-06-18 规范的 Streamable HTTP transport。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-06-18"


class MCPError(RuntimeError):
    """MCP 调用失败。"""


class McDonaldMCPClient:
    """麦当劳 MCP Server 的最小客户端。

    用法：
        client = McDonaldMCPClient()          # 从环境变量读 token
        client.initialize()
        tools = client.list_tools()
        result = client.call_tool("query-meals", {"storeCode": "..."})
    """

    def __init__(self, token: str | None = None, url: str | None = None, timeout: int = 60):
        self.url = (url or os.environ.get("MCD_MCP_URL") or DEFAULT_URL).rstrip("/")
        self.token = token or os.environ.get("MCD_MCP_TOKEN") or ""
        self.timeout = timeout
        self.session_id: str | None = None
        self._seq = 0
        self._initialized = False

        if not self.token:
            raise MCPError(
                "未找到 MCD_MCP_TOKEN。\n"
                "请先到 https://open.mcd.cn/mcp 用手机号登录，在【控制台】激活并复制 Token，\n"
                "然后设置环境变量：  set MCD_MCP_TOKEN=你的token   （Windows）\n"
                "                    export MCD_MCP_TOKEN=你的token  （macOS/Linux）"
            )

    # ------------------------------------------------------------------ 底层

    def _next_id(self) -> int:
        self._seq += 1
        return self._seq

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.token}",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
            "User-Agent": "mcd-taste-portrait/1.0 (+workbuddy)",
        }
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post(self, payload: dict) -> dict | None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
                if sid:
                    self.session_id = sid
                ctype = (resp.headers.get("Content-Type") or "").lower()
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:800]
            except Exception:  # noqa: BLE001 - 错误读取失败不应掩盖原始错误
                pass
            if exc.code == 401:
                raise MCPError(
                    "401 未授权：MCP Token 无效、已过期或未激活。请到 open.mcd.cn/mcp 控制台重新复制。"
                ) from exc
            if exc.code == 429:
                raise MCPError("429 触发限流（600 次/分钟），请稍后重试。") from exc
            raise MCPError(f"HTTP {exc.code} 调用失败：{detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise MCPError(f"网络不可达：{exc.reason}。请检查网络或代理设置。") from exc

        if not raw:
            return None
        text = raw.decode("utf-8", "replace")
        if "text/event-stream" in ctype:
            return self._parse_sse(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise MCPError(f"响应不是合法 JSON：{text[:300]}") from exc

    @staticmethod
    def _parse_sse(text: str) -> dict | None:
        """从 SSE 流里挑出最后一条 JSON-RPC 响应。"""
        last: dict | None = None
        for block in text.replace("\r\n", "\n").split("\n\n"):
            payload_lines = [
                line[5:].lstrip() for line in block.split("\n") if line.startswith("data:")
            ]
            if not payload_lines:
                continue
            data = "\n".join(payload_lines).strip()
            if not data or data == "[DONE]":
                continue
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and ("result" in obj or "error" in obj):
                last = obj
        return last

    def _notify(self, method: str) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp.read()
        except urllib.error.HTTPError:
            # 通知类请求即使失败也不影响主流程
            pass

    def _request(self, method: str, params: dict | None = None) -> dict:
        payload = {"jsonrpc": "2.0", "id": self._next_id(), "method": method}
        if params is not None:
            payload["params"] = params
        resp = self._post(payload)
        if resp is None:
            raise MCPError(f"{method} 返回空响应")
        if "error" in resp:
            err = resp["error"]
            raise MCPError(f"{method} 失败：{err.get('message') or err}")
        return resp.get("result") or {}

    # ------------------------------------------------------------------ 公开

    def initialize(self) -> dict:
        result = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcd-taste-portrait", "version": "1.0.0"},
            },
        )
        self._notify("notifications/initialized")
        self._initialized = True
        return result

    def _ensure_init(self) -> None:
        if not self._initialized:
            self.initialize()

    def list_tools(self) -> list[dict]:
        self._ensure_init()
        result = self._request("tools/list")
        return result.get("tools") or []

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        self._ensure_init()
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        if result.get("isError"):
            raise MCPError(f"工具 {name} 返回错误：{_flatten_content(result)}")
        return result

    def call_tool_json(self, name: str, arguments: dict | None = None) -> object:
        """调用工具并尽量把结果解析成 Python 对象。

        麦当劳 MCP 的 text content 有两种形态：
        1. 结构化工具：一段"字段说明 + ## Original Response + JSON"的混排文本
        2. 展示型工具：纯 Markdown 文本（如优惠券列表）

        这里优先从 Original Response 段里取 JSON，取不到再尝试整体解析，
        最后才退回文本——保证结构化工具拿到的是 dict 而不是一坨字符串。
        """
        result = self.call_tool(name, arguments)
        text = _flatten_content(result)
        return parse_tool_payload(text)


ORIGINAL_MARKER = "## Original Response"


def parse_tool_payload(text: str) -> object:
    """从 MCP 的 text content 里抽出真正的 JSON。"""
    if not isinstance(text, str):
        return text
    stripped = text.strip()
    if not stripped:
        return {}

    # 1) 优先取 "## Original Response" 之后的部分
    if ORIGINAL_MARKER in stripped:
        tail = stripped.split(ORIGINAL_MARKER, 1)[1].strip()
        tail = tail.strip("`").strip()
        try:
            return json.loads(tail)
        except json.JSONDecodeError:
            # 有时后面还跟了别的段落，逐行截断重试
            for end in range(len(tail), 0, -1):
                if tail[end - 1] in "}]":
                    try:
                        return json.loads(tail[:end])
                    except json.JSONDecodeError:
                        continue

    # 2) 整体就是 JSON
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return text


def _flatten_content(result: dict) -> str:
    """把 MCP 的 content 数组摊平成文本。"""
    parts: list[str] = []
    for block in result.get("content") or []:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif "text" in block:
                parts.append(str(block["text"]))
    if not parts:
        structured = result.get("structuredContent")
        if structured is not None:
            return json.dumps(structured, ensure_ascii=False)
    return "\n".join(parts)
