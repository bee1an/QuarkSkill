#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import asyncio
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_DIR.parents[1]
CONFIG_DIR = REPO_ROOT / "config"
COOKIES_FILE = CONFIG_DIR / "cookies.txt"
TARGET_FILE = CONFIG_DIR / "config.json"
INSTALL_HINT = (
    f"Run `pip install -r {REPO_ROOT / 'requirements.txt'}` and "
    "`python -m playwright install firefox` first."
)
REQUIRED_MODULES = [
    "httpx",
    "playwright.sync_api",
]
DEFAULT_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36 "
        "Core/1.94.225.400 QQBrowser/12.2.5544.400"
    ),
    "origin": "https://pan.quark.cn",
    "referer": "https://pan.quark.cn/",
    "accept-language": "zh-CN,zh;q=0.9",
}

os.chdir(REPO_ROOT)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def ok(results: dict[str, Any], hint: str) -> int:
    emit({"status": "ok", "hint": hint, "results": results})
    return 0


def fail(code: str, message: str, hint: str, recoverable: bool = True) -> int:
    emit(
        {
            "error": code,
            "message": message,
            "hint": hint,
            "recoverable": recoverable,
        }
    )
    return 1 if recoverable else 2


def find_missing_modules() -> list[str]:
    import importlib

    missing: list[str] = []
    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(module_name)
    return missing


def cookie_string_from_file() -> str | None:
    if not COOKIES_FILE.exists():
        return None

    content = COOKIES_FILE.read_text(encoding="utf-8").strip()
    if not content:
        return None

    if not content.startswith("["):
        return content

    try:
        cookies = ast.literal_eval(content)
    except Exception:
        return None

    parts: list[str] = []
    for cookie in cookies:
        if "quark" not in str(cookie.get("domain", "")):
            continue
        parts.append(f"{cookie['name']}={cookie['value']}")
    return "; ".join(parts) if parts else None


def random_dt(minimum: int = 100, maximum: int = 9999) -> int:
    return random.randint(minimum, maximum)


def timestamp_ms() -> int:
    return int(time.time() * 1000)


def parse_share_url(raw: str) -> tuple[str, str]:
    text = raw.strip()
    if "/s/" not in text:
        raise ValueError(f"invalid share url: {raw}")

    pwd_id = text.split("?", 1)[0].split("/s/")[-1].split("#", 1)[0]
    password_match = re.search(r"pwd=([^&#]+)", text)
    password = password_match.group(1) if password_match else ""
    return pwd_id, password


def extract_urls(values: list[str], from_file: str | None) -> list[str]:
    url_pattern = re.compile(r"https?://[^\s<>\"']+")
    urls: list[str] = []

    def collect(text: str) -> None:
        matches = url_pattern.findall(text)
        if matches:
            urls.extend(matches)
        elif text.strip():
            urls.append(text.strip())

    for value in values:
        collect(value)

    if from_file:
        file_path = Path(from_file).expanduser()
        if not file_path.is_absolute():
            file_path = REPO_ROOT / file_path
        for line in file_path.read_text(encoding="utf-8").splitlines():
            collect(line)

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            deduped.append(url)
            seen.add(url)
    return deduped


def read_target_config() -> dict[str, str]:
    if not TARGET_FILE.exists():
        return {"user": "", "pdir_id": "0", "dir_name": "根目录"}

    try:
        data = json.loads(TARGET_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"user": "", "pdir_id": "0", "dir_name": "根目录"}

    return {
        "user": str(data.get("user", "")),
        "pdir_id": str(data.get("pdir_id", "0") or "0"),
        "dir_name": str(data.get("dir_name", "根目录") or "根目录"),
    }


def write_target_config(user: str, pdir_id: str, dir_name: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TARGET_FILE.write_text(
        json.dumps(
            {"user": user, "pdir_id": pdir_id, "dir_name": dir_name},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


async def get_httpx():
    import httpx

    return httpx


async def api_get(url: str, cookie: str, *, params: dict[str, Any]) -> dict[str, Any]:
    httpx = await get_httpx()
    headers = {**DEFAULT_HEADERS, "cookie": cookie}
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params=params,
            headers=headers,
            timeout=httpx.Timeout(60.0, connect=60.0),
        )
    return response.json()


async def api_post(
    url: str,
    cookie: str,
    *,
    params: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    httpx = await get_httpx()
    headers = {**DEFAULT_HEADERS, "cookie": cookie}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=payload,
            params=params,
            headers=headers,
            timeout=httpx.Timeout(60.0, connect=60.0),
        )
    return response.json()


async def fetch_account_info(cookie: str) -> dict[str, Any]:
    result = await api_get(
        "https://pan.quark.cn/account/info",
        cookie,
        params={"fr": "pc", "platform": "pc"},
    )
    data = result.get("data")
    if not data:
        raise RuntimeError(result.get("message", "unable to verify quark account"))
    return data


async def fetch_root_folders(cookie: str) -> list[dict[str, str]]:
    result = await api_get(
        "https://drive-pc.quark.cn/1/clouddrive/file/sort",
        cookie,
        params={
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "pdir_fid": "0",
            "_page": "1",
            "_size": "100",
            "_fetch_total": "false",
            "_fetch_sub_dirs": "1",
            "_sort": "",
            "__dt": random_dt(),
            "__t": timestamp_ms(),
        },
    )
    folders: list[dict[str, str]] = []
    for item in result.get("data", {}).get("list", []):
        if item.get("dir"):
            folders.append({"fid": item["fid"], "file_name": item["file_name"]})
    return folders


async def fetch_share_token(cookie: str, pwd_id: str, password: str) -> str:
    result = await api_post(
        "https://drive-pc.quark.cn/1/clouddrive/share/sharepage/token",
        cookie,
        params={
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "__dt": random_dt(),
            "__t": timestamp_ms(),
        },
        payload={"pwd_id": pwd_id, "passcode": password},
    )
    data = result.get("data") or {}
    return str(data.get("stoken", ""))


async def fetch_share_detail(
    cookie: str,
    pwd_id: str,
    stoken: str,
    pdir_fid: str = "0",
) -> tuple[int, list[dict[str, Any]]]:
    file_list: list[dict[str, Any]] = []
    page = 1
    is_owner = 0

    while True:
        result = await api_get(
            "https://drive-pc.quark.cn/1/clouddrive/share/sharepage/detail",
            cookie,
            params={
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": pdir_fid,
                "force": "0",
                "_page": str(page),
                "_size": "50",
                "_sort": "file_type:asc,updated_at:desc",
                "__dt": random_dt(200, 9999),
                "__t": timestamp_ms(),
            },
        )

        data = result.get("data") or {}
        metadata = result.get("metadata") or {}
        is_owner = int(data.get("is_owner", 0))
        items = data.get("list") or []

        for item in items:
            file_list.append(
                {
                    "fid": item["fid"],
                    "file_name": item["file_name"],
                    "dir": bool(item["dir"]),
                    "include_items": item.get("include_items", 0),
                    "share_fid_token": item["share_fid_token"],
                }
            )

        total = int(metadata.get("_total", 0))
        size = int(metadata.get("_size", 50) or 50)
        count = int(metadata.get("_count", len(items)) or len(items))
        if total <= size or count < size:
            break
        page += 1

    return is_owner, file_list


async def create_save_task(
    cookie: str,
    pwd_id: str,
    stoken: str,
    items: list[dict[str, Any]],
    target_id: str,
) -> str:
    result = await api_post(
        "https://drive.quark.cn/1/clouddrive/share/sharepage/save",
        cookie,
        params={
            "pr": "ucpro",
            "fr": "pc",
            "uc_param_str": "",
            "__dt": random_dt(600, 9999),
            "__t": timestamp_ms(),
        },
        payload={
            "fid_list": [item["fid"] for item in items],
            "fid_token_list": [item["share_fid_token"] for item in items],
            "to_pdir_fid": target_id,
            "pwd_id": pwd_id,
            "stoken": stoken,
            "pdir_fid": "0",
            "scene": "link",
        },
    )
    data = result.get("data") or {}
    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError(result.get("message", "failed to create save task"))
    return str(task_id)


async def poll_task(cookie: str, task_id: str, retries: int = 50) -> dict[str, Any]:
    for retry_index in range(retries):
        await asyncio.sleep(random.randint(500, 1000) / 1000)
        result = await api_get(
            "https://drive-pc.quark.cn/1/clouddrive/task",
            cookie,
            params={
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "task_id": task_id,
                "retry_index": retry_index,
                "__dt": 21192,
                "__t": timestamp_ms(),
            },
        )
        if result.get("message") == "ok" and (result.get("data") or {}).get("status") == 2:
            return result

        if result.get("code") == 32003 and "capacity limit" in str(result.get("message", "")):
            raise RuntimeError("网盘容量不足")
        if result.get("code") == 41013:
            raise RuntimeError("保存目录不存在，请重新设置目标目录")

    raise TimeoutError("save task timed out")


def resolve_bound_target(user: str) -> dict[str, str]:
    config = read_target_config()
    if config["user"] != user:
        config = {"user": user, "pdir_id": "0", "dir_name": "根目录"}
        write_target_config(**config)
    return config


async def command_preflight(_: argparse.Namespace) -> int:
    missing = find_missing_modules()
    dependencies = {
        module_name: "ok" if module_name not in missing else "missing"
        for module_name in REQUIRED_MODULES
    }

    if missing:
        return fail(
            "missing_dependencies",
            f"Missing Python modules: {', '.join(missing)}",
            INSTALL_HINT,
        )

    cookie = cookie_string_from_file()
    if not cookie:
        return ok(
            {
                "ready": False,
                "dependencies": dependencies,
                "auth": {"logged_in": False},
                "target": read_target_config(),
            },
            "Dependencies are installed, but Quark is not logged in yet. Run the login command next.",
        )

    try:
        account = await fetch_account_info(cookie)
    except Exception as exc:
        return ok(
            {
                "ready": False,
                "dependencies": dependencies,
                "auth": {"logged_in": False, "reason": str(exc)},
                "target": read_target_config(),
            },
            "Cookies exist but no longer work. Run the login command to refresh them.",
        )

    target = resolve_bound_target(str(account.get("nickname", "")))
    return ok(
        {
            "ready": True,
            "dependencies": dependencies,
            "auth": {
                "logged_in": True,
                "nickname": account.get("nickname", ""),
            },
            "target": target,
        },
        f"Ready. Logged into Quark as {account.get('nickname', '')} and saving to {target['dir_name']}.",
    )


async def command_folders(_: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail(
            "missing_dependencies",
            f"Missing Python modules: {', '.join(missing)}",
            INSTALL_HINT,
        )

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        account = await fetch_account_info(cookie)
        folders = await fetch_root_folders(cookie)
    except Exception as exc:
        return fail("quark_api_error", str(exc), "Refresh login and try again.")

    target = resolve_bound_target(str(account.get("nickname", "")))
    return ok(
        {
            "user": account.get("nickname", ""),
            "target": target,
            "folders": folders,
        },
        f"Found {len(folders)} root folders for {account.get('nickname', '')}.",
    )


async def command_set_target(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail(
            "missing_dependencies",
            f"Missing Python modules: {', '.join(missing)}",
            INSTALL_HINT,
        )

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        account = await fetch_account_info(cookie)
        user = str(account.get("nickname", ""))
        folder_id = "0" if args.root else str(args.folder_id)
        folder_name = "根目录"
        if folder_id != "0":
            folders = await fetch_root_folders(cookie)
            match = next((item for item in folders if item["fid"] == folder_id), None)
            if not match:
                return fail(
                    "unknown_folder",
                    f"Folder `{folder_id}` was not found under the Quark root directory.",
                    "Run the folders command to inspect available folder ids.",
                )
            folder_name = match["file_name"]
        write_target_config(user=user, pdir_id=folder_id, dir_name=folder_name)
    except Exception as exc:
        return fail("quark_api_error", str(exc), "Refresh login and try again.")

    return ok(
        {"user": user, "target": {"user": user, "pdir_id": folder_id, "dir_name": folder_name}},
        f"Default save target updated to {folder_name}.",
    )


async def save_share(cookie: str, target_id: str, share_url: str) -> dict[str, Any]:
    pwd_id, password = parse_share_url(share_url)
    stoken = await fetch_share_token(cookie, pwd_id, password)
    if not stoken:
        return {
            "share_url": share_url,
            "pwd_id": pwd_id,
            "status": "failed",
            "reason": "分享链接无效、已失效，或提取码错误",
        }

    is_owner, items = await fetch_share_detail(cookie, pwd_id, stoken)
    files_count = sum(1 for item in items if not item["dir"])
    folders_count = sum(1 for item in items if item["dir"])

    if is_owner == 1:
        return {
            "share_url": share_url,
            "pwd_id": pwd_id,
            "status": "already_saved",
            "files_count": files_count,
            "folders_count": folders_count,
            "total_count": len(items),
        }

    if not items:
        return {
            "share_url": share_url,
            "pwd_id": pwd_id,
            "status": "failed",
            "reason": "分享内容为空，无法转存",
        }

    task_id = await create_save_task(cookie, pwd_id, stoken, items, target_id)
    result = await poll_task(cookie, task_id)
    save_as = (result.get("data") or {}).get("save_as") or {}
    return {
        "share_url": share_url,
        "pwd_id": pwd_id,
        "status": "saved",
        "task_id": task_id,
        "files_count": files_count,
        "folders_count": folders_count,
        "total_count": len(items),
        "target_name": save_as.get("to_pdir_name", "根目录"),
    }


async def command_save(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail(
            "missing_dependencies",
            f"Missing Python modules: {', '.join(missing)}",
            INSTALL_HINT,
        )

    try:
        urls = extract_urls(args.urls, args.from_file)
    except FileNotFoundError as exc:
        return fail(
            "missing_url_file",
            str(exc),
            "Pass an existing `--from-file` path, or provide URLs directly.",
        )
    if not urls:
        return fail(
            "missing_urls",
            "No share URLs were provided.",
            "Pass one or more URLs directly, or use `--from-file url.txt`.",
        )

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        account = await fetch_account_info(cookie)
    except Exception as exc:
        return fail("quark_api_error", str(exc), "Refresh login and try again.")

    target = resolve_bound_target(str(account.get("nickname", "")))
    target_id = "0" if args.target_id in (None, "0") else str(args.target_id)
    target_name = target["dir_name"]

    if target_id == "0":
        target_name = "根目录"
    elif target_id != target["pdir_id"]:
        folders = await fetch_root_folders(cookie)
        match = next((item for item in folders if item["fid"] == target_id), None)
        if not match:
            return fail(
                "unknown_folder",
                f"Folder `{target_id}` was not found under the Quark root directory.",
                "Run the folders command to inspect available folder ids, or omit `--target-id` to use the saved default.",
            )
        target_name = match["file_name"]

    results: list[dict[str, Any]] = []
    for share_url in urls:
        try:
            results.append(await save_share(cookie, target_id, share_url))
        except Exception as exc:
            results.append(
                {
                    "share_url": share_url,
                    "status": "failed",
                    "reason": str(exc),
                }
            )

    saved = sum(1 for item in results if item["status"] == "saved")
    already_saved = sum(1 for item in results if item["status"] == "already_saved")
    failed = sum(1 for item in results if item["status"] == "failed")
    return ok(
        {
            "user": account.get("nickname", ""),
            "target": {"pdir_id": target_id, "dir_name": target_name},
            "summary": {
                "total": len(results),
                "saved": saved,
                "already_saved": already_saved,
                "failed": failed,
            },
            "results": results,
        },
        f"Processed {len(results)} share links for {account.get('nickname', '')}: {saved} saved, {already_saved} already present, {failed} failed.",
    )


async def command_login(_: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail(
            "missing_dependencies",
            f"Missing Python modules: {', '.join(missing)}",
            INSTALL_HINT,
        )

    from playwright.sync_api import sync_playwright

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.firefox.launch_persistent_context(
            str(REPO_ROOT / "web_browser_data"),
            headless=False,
            slow_mo=0,
            args=["--start-maximized"],
            no_viewport=True,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://pan.quark.cn/")
            input("在弹出的夸克网页登录成功后，回到终端按 Enter 继续...")
            cookies = page.context.cookies()
        finally:
            context.close()

    COOKIES_FILE.write_text(str(cookies), encoding="utf-8")
    cookie = cookie_string_from_file()
    if not cookie:
        return fail("login_failed", "Cookies were not captured", "Retry the login flow.")

    try:
        account = await fetch_account_info(cookie)
    except Exception as exc:
        return fail("login_failed", str(exc), "Retry the login flow and confirm the account is fully logged in.")

    target = resolve_bound_target(str(account.get("nickname", "")))
    return ok(
        {
            "logged_in": True,
            "nickname": account.get("nickname", ""),
            "target": target,
        },
        f"Login succeeded for {account.get('nickname', '')}.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Structured skill entrypoint for QuarkPanTool.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("preflight", help="Check dependencies, login state, and default target.")
    subparsers.add_parser("login", help="Open a browser and capture fresh Quark cookies.")
    subparsers.add_parser("folders", help="List root folders and the current default target.")

    set_target_parser = subparsers.add_parser("set-target", help="Persist the default save target.")
    set_target_group = set_target_parser.add_mutually_exclusive_group(required=True)
    set_target_group.add_argument("--folder-id", help="Root-level folder id to use for future saves.")
    set_target_group.add_argument("--root", action="store_true", help="Reset the default target to the Quark root.")

    save_parser = subparsers.add_parser("save", help="Batch-save Quark share links.")
    save_parser.add_argument("urls", nargs="*", help="One or more share URLs.")
    save_parser.add_argument("--from-file", help="Read share URLs from a text file.")
    save_parser.add_argument("--target-id", help="Override the saved target folder id for this run only.")

    return parser


async def dispatch(args: argparse.Namespace) -> int:
    handlers = {
        "preflight": command_preflight,
        "login": command_login,
        "folders": command_folders,
        "set-target": command_set_target,
        "save": command_save,
    }
    return await handlers[args.command](args)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(dispatch(args))
    except KeyboardInterrupt:
        return fail("interrupted", "Command interrupted by user", "Retry the command when ready.")


if __name__ == "__main__":
    raise SystemExit(main())
