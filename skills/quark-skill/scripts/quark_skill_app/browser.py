from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from .constants import WEB_BROWSER_DATA_DIR
from .normalize import normalize_file_item
from .state import cookie_string_from_file


async def capture_login_cookies() -> list[dict[str, Any]]:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        context = await playwright.firefox.launch_persistent_context(
            str(WEB_BROWSER_DATA_DIR),
            headless=False,
            slow_mo=0,
            args=["--start-maximized"],
            no_viewport=True,
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto("https://pan.quark.cn/")
            input("在弹出的夸克网页登录成功后，回到终端按 Enter 继续...")
            return await page.context.cookies()
        finally:
            await context.close()


async def fetch_folder_context_via_browser(target_id: str) -> dict[str, Any]:
    from playwright.async_api import async_playwright

    target_url = "https://pan.quark.cn/list#/list/all" if target_id == "0" else f"https://pan.quark.cn/list#/list/all/{target_id}"

    async with async_playwright() as playwright:
        context = await playwright.firefox.launch_persistent_context(
            str(WEB_BROWSER_DATA_DIR),
            headless=True,
            slow_mo=0,
            no_viewport=True,
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(target_url, wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(1500)
            result = await page.evaluate(
                """async () => {
                    const response = await fetch("/1/clouddrive/share/sharepage/dir?pr=ucpro&fr=pc&uc_param_str=&aver=1", {
                        credentials: "include",
                    });
                    return await response.json();
                }"""
            )
        finally:
            await context.close()

    data = result.get("data") or {}
    directory = data.get("dir") or {}
    if str(directory.get("fid", "")) != target_id:
        raise RuntimeError(f"resolved folder context did not match target `{target_id}`")

    full_path = [str(item.get("file_name", "")).strip() for item in directory.get("full_path") or [] if str(item.get("file_name", "")).strip()]
    file_name = str(directory.get("file_name", "")).strip()
    if not file_name:
        raise RuntimeError(f"failed to resolve folder name for `{target_id}`")

    return {"fid": str(directory.get("fid", "")), "file_name": file_name, "path": full_path or [file_name]}


async def upload_file_via_browser(
    local_path: Path,
    target_id: str,
    *,
    find_items_in_folder_by_name,
    list_folder_items,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from playwright.async_api import async_playwright

    target_url = "https://pan.quark.cn/list#/list/all" if target_id == "0" else f"https://pan.quark.cn/list#/list/all/{target_id}"

    signals = {
        "upload_pre": False,
        "upload_auth_count": 0,
        "hash_updated": False,
        "hash_finish": False,
        "part_put_count": 0,
        "upload_finish": False,
        "target_sort_refreshed": False,
        "auto_renamed": False,
        "reused_existing_fid": False,
        "errors": [],
    }
    pending_requests: set[object] = set()
    sort_event = __import__("asyncio").Event()
    local_name = local_path.name
    file_size = local_path.stat().st_size
    upload_started_ms = 0

    def is_autorename_of_local(file_name: str) -> bool:
        if file_name == local_name:
            return False
        suffix = "".join(local_path.suffixes)
        stem = local_name[: -len(suffix)] if suffix and local_name.endswith(suffix) else local_name
        pattern = rf"^{re.escape(stem)}\(\d+\){re.escape(suffix)}$"
        return re.fullmatch(pattern, file_name) is not None

    def pick_uploaded_item(folder_items: list[dict[str, Any]], existing_fids: set[str]) -> tuple[dict[str, Any] | None, bool]:
        exact_name_new = [
            item
            for item in folder_items
            if str(item.get("fid", "")) not in existing_fids
            and str(item.get("file_name", "")) == local_name
            and int(item.get("size", -1) or -1) in {file_size, 0}
        ]
        if exact_name_new:
            return exact_name_new[0], False

        renamed_new = [
            item
            for item in folder_items
            if str(item.get("fid", "")) not in existing_fids
            and is_autorename_of_local(str(item.get("file_name", "")))
            and int(item.get("size", -1) or -1) in {file_size, 0}
            and max(int(item.get("updated_at", 0) or 0), int(item.get("created_at", 0) or 0)) >= upload_started_ms - 5000
        ]
        if len(renamed_new) == 1:
            return renamed_new[0], True

        return None, False

    def is_target_sort(url: str) -> bool:
        return "/1/clouddrive/file/sort" in url and f"pdir_fid={target_id}" in url

    def is_upload_request(url: str) -> bool:
        return any(
            marker in url
            for marker in [
                "/1/clouddrive/file/upload/pre",
                "/1/clouddrive/file/upload/auth",
                "/1/clouddrive/file/update/hash",
                "/1/clouddrive/file/upload/finish",
                ".pds.quark.cn/",
            ]
        )

    def on_request(request) -> None:
        if is_upload_request(request.url):
            pending_requests.add(request)

    async def on_response(response) -> None:
        request = response.request
        pending_requests.discard(request)
        url = response.url
        status = response.status
        if status >= 400 and (is_upload_request(url) or is_target_sort(url)):
            signals["errors"].append({"url": url, "status": status})
        if "/1/clouddrive/file/upload/pre" in url and status == 200:
            signals["upload_pre"] = True
        elif "/1/clouddrive/file/upload/auth" in url and status == 200:
            signals["upload_auth_count"] += 1
        elif "/1/clouddrive/file/update/hash" in url and status == 200:
            signals["hash_updated"] = True
            try:
                payload = await response.json()
            except Exception:
                payload = {}
            if (payload.get("data") or {}).get("finish") is True:
                signals["hash_finish"] = True
                signals["upload_finish"] = True
        elif ".pds.quark.cn/" in url and request.method == "PUT" and status == 200:
            signals["part_put_count"] += 1
        elif "/1/clouddrive/file/upload/finish" in url and status == 200:
            signals["upload_finish"] = True
        elif is_target_sort(url) and status == 200 and signals["upload_finish"]:
            signals["target_sort_refreshed"] = True
            sort_event.set()

    def on_request_failed(request) -> None:
        if is_upload_request(request.url):
            pending_requests.discard(request)
            signals["errors"].append({"url": request.url, "status": "failed"})

    async with async_playwright() as playwright:
        context = await playwright.firefox.launch_persistent_context(
            str(WEB_BROWSER_DATA_DIR),
            headless=False,
            slow_mo=0,
            args=["--start-maximized"],
            no_viewport=True,
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            page.on("request", on_request)
            page.on("response", on_response)
            page.on("requestfailed", on_request_failed)
            await page.goto(target_url, wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except PlaywrightTimeoutError:
                pass
            file_input = page.locator("input[type=file]").first
            await file_input.wait_for(state="attached", timeout=10000)
            cookie = cookie_string_from_file()
            if not cookie:
                raise RuntimeError("upload browser session did not preserve login cookies")
            existing_folder_items = await list_folder_items(cookie, target_id)
            existing_items = await find_items_in_folder_by_name(cookie, target_id, local_path.name, expected_size=file_size)
            existing_fids = {str(item.get("fid", "")) for item in existing_folder_items}
            upload_started_ms = int(time.time() * 1000)
            await file_input.set_input_files(str(local_path))

            started_at = time.time()
            while time.time() - started_at < timeout_seconds:
                if signals["errors"]:
                    raise RuntimeError(f"upload requests failed: {signals['errors']!r}")
                folder_items = await list_folder_items(cookie, target_id)
                if signals["upload_finish"]:
                    uploaded_item, auto_renamed = pick_uploaded_item(folder_items, existing_fids)
                    if uploaded_item:
                        signals["auto_renamed"] = auto_renamed
                        return {"remote": normalize_file_item(uploaded_item), "signals": signals}
                if signals["upload_finish"] and not pending_requests:
                    try:
                        await __import__("asyncio").wait_for(sort_event.wait(), timeout=5)
                    except TimeoutError:
                        pass
                    folder_items = await list_folder_items(cookie, target_id)
                    uploaded_item, auto_renamed = pick_uploaded_item(folder_items, existing_fids)
                    if uploaded_item:
                        signals["auto_renamed"] = auto_renamed
                        return {"remote": normalize_file_item(uploaded_item), "signals": signals}
                    candidates = await find_items_in_folder_by_name(cookie, target_id, local_path.name, expected_size=file_size)
                    existing_candidate_fids = {str(item.get("fid", "")) for item in existing_items}
                    candidate_fids = {str(item.get("fid", "")) for item in candidates}
                    if len(existing_candidate_fids) == 1 and candidate_fids == existing_candidate_fids:
                        signals["reused_existing_fid"] = True
                        return {"remote": normalize_file_item(existing_items[0]), "signals": signals}
                await __import__("asyncio").sleep(2)
        finally:
            await context.close()

    raise TimeoutError("upload timed out before the file appeared in Quark")
