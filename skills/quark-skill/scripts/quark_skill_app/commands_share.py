from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Any

from .api import (
    create_save_task,
    create_share_task,
    fetch_account_info,
    fetch_download_links,
    fetch_myshare_page,
    fetch_root_folders,
    fetch_share_detail,
    fetch_share_id,
    fetch_share_token,
    fetch_sorted_file_list,
    fetch_transfer_update_page,
    finalize_share,
    poll_task,
    stream_download_file,
)
from .browser import fetch_folder_context_via_browser
from .constants import DEFAULT_RETRY_FILE, DEFAULT_RETRY_SHARE_FILE, DEFAULT_SHARE_ERROR_FILE, DEFAULT_SHARE_FILE, DOWNLOADS_DIR, INSTALL_HINT
from .normalize import normalize_myshare_item, normalize_share_update_item
from .output import fail, ok
from .state import (
    build_nested_path,
    cookie_string_from_file,
    ensure_share_workspace,
    extract_folder_resource_id,
    extract_urls,
    find_missing_modules,
    parse_share_url,
    resolve_bound_target,
    resolve_repo_path,
    write_lines,
)


async def save_share(cookie: str, target_id: str, share_url: str) -> dict[str, Any]:
    pwd_id, password = parse_share_url(share_url)
    stoken = await fetch_share_token(cookie, pwd_id, password)
    if not stoken:
        return {"share_url": share_url, "pwd_id": pwd_id, "status": "failed", "reason": "分享链接无效、已失效，或提取码错误"}

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
        return {"share_url": share_url, "pwd_id": pwd_id, "status": "failed", "reason": "分享内容为空，无法转存"}

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
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    try:
        urls = extract_urls(args.urls, args.from_file)
    except FileNotFoundError as exc:
        return fail("missing_url_file", str(exc), "Pass an existing `--from-file` path, or provide URLs directly.")
    if not urls:
        return fail("missing_urls", "No share URLs were provided.", "Pass one or more URLs directly, or use `--from-file url.txt`.")

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
            results.append({"share_url": share_url, "status": "failed", "reason": str(exc)})

    saved = sum(1 for item in results if item["status"] == "saved")
    already_saved = sum(1 for item in results if item["status"] == "already_saved")
    failed_count = sum(1 for item in results if item["status"] == "failed")
    return ok(
        {
            "user": account.get("nickname", ""),
            "target": {"pdir_id": target_id, "dir_name": target_name},
            "summary": {"total": len(results), "saved": saved, "already_saved": already_saved, "failed": failed_count},
            "results": results,
        },
        f"Processed {len(results)} share links for {account.get('nickname', '')}: {saved} saved, {already_saved} already present, {failed_count} failed.",
    )


async def share_single_folder(
    cookie: str,
    fid: str,
    title: str,
    path_parts: list[str],
    *,
    url_type: int,
    expired_type: int,
    password: str,
    index: int,
) -> dict[str, Any]:
    last_error = ""
    for _ in range(3):
        try:
            task_id = await create_share_task(cookie, fid, title, url_type=url_type, expired_type=expired_type, password=password)
            share_id = await fetch_share_id(cookie, task_id)
            finalized = await finalize_share(cookie, share_id)
            return {
                "index": index,
                "status": "shared",
                "fid": fid,
                "title": finalized["title"],
                "path": path_parts,
                "share_url": finalized["share_url"],
            }
        except Exception as exc:
            last_error = str(exc)
            await __import__("asyncio").sleep(random.choice([0.5, 1.0, 1.5, 2.0]))
    return {"index": index, "status": "failed", "fid": fid, "title": title, "path": path_parts, "reason": last_error or "share failed"}


async def command_share(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        account = await fetch_account_info(cookie)
        folder_id = extract_folder_resource_id(args.resource)
    except Exception as exc:
        return fail("invalid_resource", str(exc), "Pass a valid Quark folder page URL or folder id.")

    ensure_share_workspace()
    url_type = 2 if args.private else 1
    expire_map = {"1d": 2, "7d": 3, "30d": 4, "permanent": 1}
    expired_type = expire_map[args.expire]
    entries: list[dict[str, Any]] = []
    retry_lines: list[str] = []
    error_lines: list[str] = []
    output_lines: list[str] = []
    try:
        folder_context = await fetch_folder_context_via_browser(folder_id)
    except Exception as exc:
        return fail(
            "quark_api_error",
            str(exc),
            "Confirm the folder exists, the browser session can open it, and then try again.",
        )

    if args.traverse_depth == 0:
        entries.append(
            await share_single_folder(
                cookie,
                folder_id,
                folder_context["file_name"],
                folder_context["path"],
                url_type=url_type,
                expired_type=expired_type,
                password=args.password,
                index=1,
            )
        )
    else:
        first_page = 1
        index = 0
        while True:
            page_data = await fetch_sorted_file_list(
                cookie,
                pdir_fid=folder_id,
                page=str(first_page),
                size="50",
                fetch_total="1",
                sort="file_type:asc,file_name:asc",
                fetch_sub_dirs="0",
            )
            for item in page_data.get("data", {}).get("list", []):
                if not item.get("dir"):
                    continue
                first_dir = item["file_name"]
                if args.traverse_depth == 1:
                    index += 1
                    entries.append(
                        await share_single_folder(
                            cookie,
                            item["fid"],
                            first_dir,
                            [first_dir],
                            url_type=url_type,
                            expired_type=expired_type,
                            password=args.password,
                            index=index,
                        )
                    )
                    continue
                second_page = 1
                while True:
                    nested_data = await fetch_sorted_file_list(
                        cookie,
                        pdir_fid=item["fid"],
                        page=str(second_page),
                        size="50",
                        fetch_total="1",
                        sort="file_type:asc,file_name:asc",
                        fetch_sub_dirs="0",
                    )
                    for nested in nested_data.get("data", {}).get("list", []):
                        if not nested.get("dir"):
                            continue
                        index += 1
                        entries.append(
                            await share_single_folder(
                                cookie,
                                nested["fid"],
                                nested["file_name"],
                                [first_dir, nested["file_name"]],
                                url_type=url_type,
                                expired_type=expired_type,
                                password=args.password,
                                index=index,
                            )
                        )
                    metadata = nested_data.get("metadata") or {}
                    total = int(metadata.get("_total", 0))
                    size = int(metadata.get("_size", 50) or 50)
                    page = int(metadata.get("_page", second_page) or second_page)
                    if size * page >= total:
                        break
                    second_page += 1
            metadata = page_data.get("metadata") or {}
            total = int(metadata.get("_total", 0))
            size = int(metadata.get("_size", 50) or 50)
            page = int(metadata.get("_page", first_page) or first_page)
            if size * page >= total:
                break
            first_page += 1

    for entry in entries:
        if entry["status"] == "shared":
            output_lines.append(" | ".join([str(entry["index"]), *entry["path"], entry["share_url"]]))
        else:
            error_lines.append(f"{entry['index']}. {'/'.join(entry['path'])}")
            retry_lines.append(" | ".join([str(entry["index"]), *entry["path"], entry["fid"]]))

    output_path = resolve_repo_path(args.output_file)
    retry_path = resolve_repo_path(args.retry_file)
    error_path = resolve_repo_path(args.error_file)
    write_lines(output_path, output_lines)
    write_lines(retry_path, retry_lines)
    write_lines(error_path, error_lines)

    shared = sum(1 for entry in entries if entry["status"] == "shared")
    failed_count = sum(1 for entry in entries if entry["status"] == "failed")
    return ok(
        {
            "user": account.get("nickname", ""),
            "summary": {"total": len(entries), "shared": shared, "failed": failed_count},
            "output_file": str(output_path.resolve()),
            "retry_file": str(retry_path.resolve()),
            "error_file": str(error_path.resolve()),
            "results": entries,
        },
        f"Processed {len(entries)} folders for sharing: {shared} shared, {failed_count} failed.",
    )


async def command_retry_share(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    retry_path = resolve_repo_path(args.from_file)
    if not retry_path.exists():
        return fail("missing_retry_file", f"Retry file not found: {retry_path}", "Run `share` first or pass an existing retry file.")

    url_type = 2 if args.private else 1
    expire_map = {"1d": 2, "7d": 3, "30d": 4, "permanent": 1}
    expired_type = expire_map[args.expire]
    entries: list[dict[str, Any]] = []
    remaining_retry_lines: list[str] = []
    output_lines: list[str] = []

    for line in [line.strip() for line in retry_path.read_text(encoding="utf-8").splitlines() if line.strip()]:
        parts = [part.strip() for part in line.split(" | ")]
        if len(parts) < 3:
            continue
        index = int(parts[0]) if parts[0].isdigit() else len(entries) + 1
        fid = parts[-1]
        path_parts = parts[1:-1]
        title = path_parts[-1] if path_parts else "分享"
        result = await share_single_folder(
            cookie,
            fid,
            title,
            path_parts,
            url_type=url_type,
            expired_type=expired_type,
            password=args.password,
            index=index,
        )
        entries.append(result)
        if result["status"] == "shared":
            output_lines.append(" | ".join([str(result["index"]), *result["path"], result["share_url"]]))
        else:
            remaining_retry_lines.append(line)

    output_path = resolve_repo_path(args.output_file)
    write_lines(output_path, output_lines)
    write_lines(retry_path, remaining_retry_lines)

    shared = sum(1 for entry in entries if entry["status"] == "shared")
    failed_count = sum(1 for entry in entries if entry["status"] == "failed")
    return ok(
        {
            "summary": {"total": len(entries), "shared": shared, "failed": failed_count},
            "output_file": str(output_path.resolve()),
            "retry_file": str(retry_path.resolve()),
            "results": entries,
        },
        f"Retried {len(entries)} pending share entries: {shared} shared, {failed_count} still failing.",
    )


async def collect_download_items(
    cookie: str,
    pwd_id: str,
    stoken: str,
    items: list[dict[str, Any]],
    folders_map: dict[str, dict[str, str]],
    parent_fid: str = "0",
) -> list[str]:
    file_fids: list[str] = []
    for item in items:
        if item["dir"]:
            folders_map[item["fid"]] = {"file_name": item["file_name"], "pdir_fid": parent_fid}
            nested_owner, nested_items = await fetch_share_detail(cookie, pwd_id, stoken, pdir_fid=item["fid"])
            if nested_owner != 1:
                continue
            file_fids.extend(await collect_download_items(cookie, pwd_id, stoken, nested_items, folders_map, parent_fid=item["fid"]))
        else:
            file_fids.append(item["fid"])
    return file_fids


async def command_download(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    try:
        urls = extract_urls(args.urls, args.from_file)
    except FileNotFoundError as exc:
        return fail("missing_url_file", str(exc), "Pass an existing `--from-file` path, or provide URLs directly.")
    if not urls:
        return fail("missing_urls", "No share URLs were provided.", "Pass one or more URLs directly, or use `--from-file url.txt`.")

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    output_dir = resolve_repo_path(args.output_dir)
    results: list[dict[str, Any]] = []
    for share_url in urls:
        try:
            pwd_id, password = parse_share_url(share_url)
            stoken = await fetch_share_token(cookie, pwd_id, password)
            if not stoken:
                results.append({"share_url": share_url, "status": "failed", "reason": "invalid share or password"})
                continue
            is_owner, root_items = await fetch_share_detail(cookie, pwd_id, stoken)
            if is_owner != 1:
                results.append(
                    {
                        "share_url": share_url,
                        "status": "failed",
                        "reason": "download only works for shares created from your own Quark drive files",
                    }
                )
                continue
            folders_map: dict[str, dict[str, str]] = {}
            file_fids = await collect_download_items(cookie, pwd_id, stoken, root_items, folders_map)
            download_entries = await fetch_download_links(cookie, file_fids)
            downloaded_files: list[str] = []
            for entry in download_entries:
                relative_dir = build_nested_path(str(entry.get("pdir_fid", "")), folders_map)
                save_path = output_dir / relative_dir / str(entry["file_name"])
                await stream_download_file(cookie, str(entry["download_url"]), save_path)
                downloaded_files.append(str(save_path))
            results.append(
                {
                    "share_url": share_url,
                    "status": "downloaded",
                    "files_count": len(downloaded_files),
                    "output_dir": str(output_dir.resolve()),
                    "files": downloaded_files,
                }
            )
        except Exception as exc:
            results.append({"share_url": share_url, "status": "failed", "reason": str(exc)})

    downloaded = sum(1 for item in results if item["status"] == "downloaded")
    failed_count = sum(1 for item in results if item["status"] == "failed")
    return ok(
        {
            "summary": {"total": len(results), "downloaded": downloaded, "failed": failed_count},
            "output_dir": str(output_dir.resolve()),
            "results": results,
        },
        f"Processed {len(results)} download requests: {downloaded} downloaded, {failed_count} failed.",
    )


async def command_list_myshare(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        matched: list[dict[str, Any]] = []
        page = 1
        total_remote = 0
        while True:
            result = await fetch_myshare_page(cookie, page, 100)
            raw_items = result.get("data", {}).get("list", [])
            total_remote = int((result.get("metadata") or {}).get("_total", len(raw_items)) or len(raw_items))
            for raw_item in raw_items:
                normalized = normalize_myshare_item(raw_item)
                if args.type != "all" and normalized["type"] != args.type:
                    continue
                matched.append(normalized)
            if len(matched) >= args.page * args.size or page * 100 >= total_remote:
                break
            page += 1
        start = (args.page - 1) * args.size
        items = matched[start : start + args.size]
        total = len(matched)
    except Exception as exc:
        return fail("quark_api_error", str(exc), "Refresh login and try again.")

    return ok(
        {"page": args.page, "size": args.size, "type": args.type, "total": total, "items": items},
        f"Listed {len(items)} myshare items for type `{args.type}`.",
    )


async def command_list_transfer_updates(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        result = await fetch_transfer_update_page(cookie, args.page, args.size)
        items = [normalize_share_update_item(item) for item in result.get("data", {}).get("list", [])]
        metadata = result.get("metadata") or {}
        total = int(metadata.get("_total", len(items)) or len(items))
    except Exception as exc:
        return fail("quark_api_error", str(exc), "Refresh login and try again.")

    return ok(
        {"page": args.page, "size": args.size, "total": total, "items": items},
        f"Listed {len(items)} transfer update items.",
    )
