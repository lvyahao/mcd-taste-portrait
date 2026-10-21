"""通过 GitHub REST API 发布仓库（不依赖 git push）。

为什么需要这个脚本：
本机网络可以访问 api.github.com，但 github.com 的 git 协议与网页端点被代理拦截（HTTP 502）。
所以不能走 `git remote add && git push`，改为用 Git Data API 直接构造提交：
  blobs -> tree -> commit -> ref
这条路只依赖 api.github.com，稳定可用。

用法：
    set GITHUB_TOKEN=ghp_xxx
    python tools/publish.py                 # 创建仓库并上传
    python tools/publish.py --repo mcd-taste-portrait --desc "..."

安全：Token 只从环境变量读，不落盘、不打印。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
SKIP_DIRS = {".git", "__pycache__", "_probe", "reports", ".venv", "venv", ".idea", ".vscode"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if not tok:
        sys.exit(
            "缺少 GITHUB_TOKEN。\n"
            "在 https://github.com/settings/tokens 生成一个带 repo 权限的 Token，然后：\n"
            "  set GITHUB_TOKEN=你的token"
        )
    return tok.strip()


def api(method: str, path: str, tok: str, body: dict | None = None) -> tuple[int, dict | list | None]:
    url = path if path.startswith("http") else f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "mcd-taste-portrait-publish",
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


def collect_files(root: str) -> list[tuple[str, bytes]]:
    """收集要上传的文件，返回 (相对路径, 内容)。"""
    out: list[tuple[str, bytes]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name in SKIP_FILES or name.endswith(".zip"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            with open(full, "rb") as fh:
                out.append((rel, fh.read()))
    out.sort(key=lambda t: t[0])
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    parser.add_argument("--repo", default="mcd-taste-portrait")
    parser.add_argument("--desc", default="把麦当劳订单流水变成一份关于你自己的口味人格报告")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--private", action="store_true", help="默认公开（比赛要求 Public）")
    args = parser.parse_args()

    tok = token()

    # 1. 身份
    code, me = api("GET", "/user", tok)
    if code != 200 or not isinstance(me, dict):
        print(f"[失败] 无法验证 Token（HTTP {code}）：{me}")
        return 1
    login = me["login"]
    print(f"  已认证：{login}")

    # 2. 收集文件 + 替换 README 占位符
    files = collect_files(args.root)
    for idx, (rel, content) in enumerate(files):
        if rel == "README.md":
            text = content.decode("utf-8")
            text = text.replace("<your-name>", login).replace("<YOUR_NAME>", login)
            files[idx] = (rel, text.encode("utf-8"))
    print(f"  待上传：{len(files)} 个文件")

    # 3. 建仓库（已存在则复用）
    code, repo = api(
        "POST", "/user/repos", tok,
        {"name": args.repo, "description": args.desc, "private": args.private, "auto_init": False},
    )
    if code == 201 and isinstance(repo, dict):
        print(f"  已创建仓库：{repo['html_url']}")
    elif code == 422:
        code2, repo = api("GET", f"/repos/{login}/{args.repo}", tok)
        if code2 != 200 or not isinstance(repo, dict):
            print(f"[失败] 仓库处理失败：{repo}")
            return 1
        print(f"  仓库已存在，复用：{repo['html_url']}")
    else:
        print(f"[失败] 创建仓库失败（HTTP {code}）：{repo}")
        return 1

    # 4. 空仓库需要先用 Contents API 打一个初始 commit
    #    否则 Git Data API 的 create-blob 会返回 409 "Git Repository is empty"
    code, info = api("GET", f"/repos/{login}/{args.repo}", tok)
    default_branch = (info or {}).get("default_branch") or args.branch if isinstance(info, dict) else args.branch
    args.branch = default_branch

    code, ref = api("GET", f"/repos/{login}/{args.repo}/git/ref/heads/{args.branch}", tok)
    # 空仓库上这个接口返回 409 "Git Repository is empty"（不是 404）
    if code in (404, 409) or (code == 200 and not (isinstance(ref, dict) and ref.get("object"))):
        seed = next((c for p, c in files if p == "README.md"), b"# mcd-taste-portrait\n")
        code, seeded = api(
            "PUT", f"/repos/{login}/{args.repo}/contents/README.md", tok,
            {
                "message": "初始化仓库",
                "content": base64.b64encode(seed).decode(),
                "branch": args.branch,
            },
        )
        if code not in (200, 201):
            print(f"[失败] 初始化空仓库：HTTP {code} {seeded}")
            return 1
        print(f"  已初始化空仓库（分支 {args.branch}）")
    else:
        print(f"  分支已存在（HTTP {code}），将追加提交")

    # 5. 逐个建 blob
    entries = []
    for rel, content in files:
        code, blob = api(
            "POST", f"/repos/{login}/{args.repo}/git/blobs", tok,
            {"content": base64.b64encode(content).decode(), "encoding": "base64"},
        )
        if code != 201 or not isinstance(blob, dict):
            print(f"[失败] 上传 {rel}：HTTP {code} {blob}")
            return 1
        entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    print(f"  已上传 {len(entries)} 个 blob")

    # 5. 建 tree
    code, tree = api("POST", f"/repos/{login}/{args.repo}/git/trees", tok, {"tree": entries})
    if code != 201 or not isinstance(tree, dict):
        print(f"[失败] 创建 tree：HTTP {code} {tree}")
        return 1
    print(f"  tree: {tree['sha'][:10]}")

    # 6. 建 commit（如果是空仓库，没有 parent）
    commit_body: dict = {"message": "麦门人格 · 口味年报：把麦当劳订单流水变成一份关于你自己的报告", "tree": tree["sha"]}
    code, ref = api("GET", f"/repos/{login}/{args.repo}/git/ref/heads/{args.branch}", tok)
    if code == 200 and isinstance(ref, dict):
        commit_body["parents"] = [ref["object"]["sha"]]
        print("  检测到已有分支，本次将追加提交")

    code, commit = api("POST", f"/repos/{login}/{args.repo}/git/commits", tok, commit_body)
    if code != 201 or not isinstance(commit, dict):
        print(f"[失败] 创建 commit：HTTP {code} {commit}")
        return 1
    print(f"  commit: {commit['sha'][:10]}")

    # 7. 建立/更新分支引用
    if "parents" in commit_body:
        code, res = api("PATCH", f"/repos/{login}/{args.repo}/git/refs/heads/{args.branch}", tok, {"sha": commit["sha"], "force": True})
    else:
        code, res = api("POST", f"/repos/{login}/{args.repo}/git/refs", tok, {"ref": f"refs/heads/{args.branch}", "sha": commit["sha"]})
    if code not in (200, 201):
        print(f"[失败] 更新分支：HTTP {code} {res}")
        return 1

    print("")
    print("  完成")
    print(f"  仓库地址  {repo['html_url']}")
    print(f"  Clone     https://github.com/{login}/{args.repo}.git")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
