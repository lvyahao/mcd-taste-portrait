"""在麦当劳官方仓库提交报名 Issue。

报名校验逻辑比较严格，这个脚本严格按官方格式拼 body：
  - 标题与正文分开设置，标题内不含换行
  - 每条「标签：内容」保持在同一行
  - 项目地址用裸 URL，不用 Markdown 链接语法

用法：
    set GITHUB_TOKEN=ghp_xxx
    python tools/apply.py --repo mcd-taste-portrait
    python tools/apply.py --repo mcd-taste-portrait --dry-run   # 只看 body，不提交
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
TARGET_OWNER = "M-China"
TARGET_REPO = "mcd-developer-innovation-challenge"

REQUIRED = [
    "README.md",
    "CONTEST_DECLARATION.md",
    "MCP_INTEGRATION.md",
    "mcp-config.example.json",
    "workbuddy.md",
]


def api(method: str, path: str, tok: str, body: dict | None = None) -> tuple[int, dict | list | None]:
    url = path if path.startswith("http") else f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "mcd-taste-portrait-apply",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw.decode("utf-8", "replace")
        return exc.code, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="mcd-taste-portrait")
    parser.add_argument("--name", default="麦门人格 · 口味年报")
    parser.add_argument(
        "--intro",
        default="读取你自己的麦当劳历史订单，用忠诚/规律/犒赏/精算四个可测量维度算出你的点餐行为形状，"
                "给出 13 型人格之一，并把每条判断依据摊开供你核对——一份关于你而不是关于汉堡的报告",
    )
    parser.add_argument("--root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not tok:
        sys.exit("缺少 GITHUB_TOKEN")

    # 上传前自查：必需文件齐不齐
    missing = [f for f in REQUIRED if not os.path.exists(os.path.join(args.root, f))]
    if missing:
        print(f"[警告] 仓库里缺少报名必需文件：{', '.join(missing)}")
        print("      报名系统会校验这几个文件，缺一个都会被拒。")
        if not args.dry_run:
            return 1

    code, me = api("GET", "/user", tok)
    if code != 200 or not isinstance(me, dict):
        sys.exit(f"[失败] Token 无效（HTTP {code}）")
    login = me["login"]

    title = f"【参赛申请】{args.name}"
    body = "\n".join([
        "【参赛申请】",
        f"项目名称：{args.name}",
        f"项目地址：https://github.com/{login}/{args.repo}",
        f"项目简介：{args.intro}",
    ])

    print("=" * 62)
    print("标题：")
    print(title)
    print("-" * 62)
    print("正文：")
    print(body)
    print("=" * 62)

    if args.dry_run:
        print("\n[dry-run] 未提交。去掉 --dry-run 即可正式报名。")
        return 0

    code, issue = api(
        "POST", f"/repos/{TARGET_OWNER}/{TARGET_REPO}/issues", tok,
        {"title": title, "body": body},
    )
    if code == 201 and isinstance(issue, dict):
        print(f"\n  报名 Issue 已提交：{issue['html_url']}")
        print("  官方机器人会在 Issue 下回复报名结果，通常几分钟内。")
        print("  如果失败，按回复里的原因修正后重新提交即可。")
        return 0

    print(f"\n[失败] 提交被拒（HTTP {code}）：{issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
