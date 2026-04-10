from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any

from .api import (
    delete_remote_files,
    fetch_account_info,
    fetch_category_list,
    fetch_myshare_page,
    fetch_recent_list,
    fetch_search_list,
    fetch_sorted_file_list,
    move_remote_files,
    rename_remote_file,
    wait_for_task_if_needed,
)
from .browser import upload_file_via_browser
from .constants import CATEGORY_SCOPE_MAP, INSTALL_HINT
from .normalize import normalize_file_item, normalize_myshare_item, normalize_recent_item
from .output import fail, ok
from .state import (
    cookie_string_from_file,
    find_missing_modules,
    parse_id_batch_file,
    parse_rename_batch_file,
    read_target_config,
    resolve_repo_path,
)


async def find_items_in_folder_by_name(cookie: str, folder_id: str, file_name: str, expected_size: int | None = None) -> list[dict[str, Any]]:
    items = await list_folder_items(cookie, folder_id)
    matches = []
    for item in items:
        if str(item.get("file_name", "")) != file_name:
            continue
        if expected_size is not None and int(item.get("size", -1) or -1) not in {expected_size, 0}:
            continue
        matches.append(item)
    matches.sort(key=lambda item: (int(item.get("updated_at", 0) or 0), int(item.get("created_at", 0) or 0)), reverse=True)
    return matches


async def list_folder_items(cookie: str, folder_id: str) -> list[dict[str, Any]]:
    page = 1
    items_out: list[dict[str, Any]] = []
    while True:
        result = await fetch_sorted_file_list(
            cookie,
            pdir_fid=folder_id,
            page=str(page),
            size="100",
            fetch_total="1",
            sort="file_type:asc,updated_at:desc",
            fetch_sub_dirs="0",
        )
        items = result.get("data", {}).get("list", [])
        items_out.extend(items)
        metadata = result.get("metadata") or {}
        total = int(metadata.get("_total", 0) or 0)
        size = int(metadata.get("_size", 100) or 100)
        if size * page >= total:
            break
        page += 1
    items_out.sort(key=lambda item: (int(item.get("updated_at", 0) or 0), int(item.get("created_at", 0) or 0)), reverse=True)
    return items_out


async def command_list(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        if args.scope == "all":
            result = await fetch_sorted_file_list(
                cookie,
                pdir_fid=str(args.folder_id or "0"),
                page=str(args.page),
                size=str(args.size),
                fetch_total="1",
                sort="file_type:asc,updated_at:desc",
                fetch_sub_dirs="0",
            )
            items = [normalize_file_item(item) for item in result.get("data", {}).get("list", [])]
            total = int((result.get("metadata") or {}).get("_total", len(items)) or len(items))
        elif args.scope == "recent":
            result = await fetch_recent_list(cookie, item_size=args.page * args.size)
            raw_items = result.get("data", {}).get("list", [])
            start = (args.page - 1) * args.size
            items = [normalize_recent_item(item) for item in raw_items[start : start + args.size]]
            total = len(raw_items)
        elif args.scope in CATEGORY_SCOPE_MAP:
            result = await fetch_category_list(cookie, CATEGORY_SCOPE_MAP[args.scope], args.page, args.size)
            items = [normalize_file_item(item) for item in result.get("data", {}).get("list", [])]
            total = int((result.get("metadata") or {}).get("_total", len(items)) or len(items))
        else:
            result = await fetch_myshare_page(cookie, args.page, args.size)
            items = [normalize_myshare_item(item) for item in result.get("data", {}).get("list", [])]
            total = int((result.get("metadata") or {}).get("_total", len(items)) or len(items))
    except Exception as exc:
        return fail("quark_api_error", str(exc), "Refresh login and try again.")

    return ok(
        {
            "scope": args.scope,
            "folder_id": str(args.folder_id or "0"),
            "page": args.page,
            "size": args.size,
            "total": total,
            "items": items,
        },
        f"Listed {len(items)} items from scope `{args.scope}`.",
    )


async def command_search(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        if args.scope == "all":
            result = await fetch_search_list(cookie, args.keyword, args.page, args.size)
            items = []
            for item in result.get("data", {}).get("list", []):
                normalized = normalize_file_item(item)
                normalized["highlighted_name"] = html.unescape(str(item.get("hl_file_name", "")))
                items.append(normalized)
            total = int((result.get("metadata") or {}).get("_total", len(items)) or len(items))
        else:
            matched: list[dict[str, Any]] = []
            page = 1
            total_remote = 0
            while True:
                result = await fetch_myshare_page(cookie, page, 100)
                raw_items = result.get("data", {}).get("list", [])
                total_remote = int((result.get("metadata") or {}).get("_total", len(raw_items)) or len(raw_items))
                for raw_item in raw_items:
                    normalized = normalize_myshare_item(raw_item)
                    haystack = " ".join(
                        [
                            normalized["title"],
                            normalized["first_file_name"],
                            normalized["path_info"],
                            normalized["share_url"],
                        ]
                    ).lower()
                    if args.keyword.lower() in haystack:
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
        {
            "scope": args.scope,
            "keyword": args.keyword,
            "page": args.page,
            "size": args.size,
            "total": total,
            "items": items,
        },
        f"Found {len(items)} results for `{args.keyword}` in scope `{args.scope}`.",
    )


async def command_move(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)
    if not args.fid and not args.from_file:
        return fail("missing_fids", "No file ids were provided.", "Pass a fid directly or use `--from-file`.")

    try:
        fids = [str(args.fid)] if args.fid else parse_id_batch_file(args.from_file)
    except Exception as exc:
        return fail("invalid_batch_file", str(exc), "Use a txt/jsonl file that contains Quark fids.")

    if args.dry_run:
        return ok(
            {
                "planned": True,
                "applied": False,
                "to_folder": str(args.to_folder),
                "items": [{"fid": fid, "status": "planned"} for fid in fids],
            },
            f"Prepared move plan for {len(fids)} items.",
        )

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        result = await move_remote_files(cookie, fids, str(args.to_folder))
        await wait_for_task_if_needed(cookie, result)
    except Exception as exc:
        return fail("quark_api_error", str(exc), "Refresh login and try again.")

    return ok(
        {
            "planned": False,
            "applied": True,
            "to_folder": str(args.to_folder),
            "items": [{"fid": fid, "status": "moved"} for fid in fids],
        },
        f"Moved {len(fids)} items to folder `{args.to_folder}`.",
    )


async def command_rename(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    try:
        if args.from_file:
            items = parse_rename_batch_file(args.from_file)
        elif args.fid and args.name:
            items = [{"fid": str(args.fid), "new_name": args.name.strip()}]
        else:
            return fail("missing_rename_args", "Missing rename input.", "Use `rename FID --name NEW_NAME` or `--from-file`.")
    except Exception as exc:
        return fail("invalid_batch_file", str(exc), "Use a tab-separated batch file with `fid<TAB>new_name`.")

    if args.dry_run:
        return ok(
            {
                "planned": True,
                "applied": False,
                "items": [{"fid": item["fid"], "new_name": item["new_name"], "status": "planned"} for item in items],
            },
            f"Prepared rename plan for {len(items)} items.",
        )

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    results: list[dict[str, Any]] = []
    for item in items:
        try:
            await rename_remote_file(cookie, item["fid"], item["new_name"])
            results.append({"fid": item["fid"], "new_name": item["new_name"], "status": "renamed"})
        except Exception as exc:
            results.append({"fid": item["fid"], "new_name": item["new_name"], "status": "failed", "reason": str(exc)})

    failed_count = sum(1 for item in results if item["status"] == "failed")
    return ok(
        {"planned": False, "applied": failed_count == 0, "items": results},
        f"Processed rename for {len(results)} items with {failed_count} failures.",
    )


async def command_delete(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)
    if not args.fid and not args.from_file:
        return fail("missing_fids", "No file ids were provided.", "Pass a fid directly or use `--from-file`.")

    try:
        fids = [str(args.fid)] if args.fid else parse_id_batch_file(args.from_file)
    except Exception as exc:
        return fail("invalid_batch_file", str(exc), "Use a txt/jsonl file that contains Quark fids.")

    if not args.yes:
        return ok(
            {
                "planned": True,
                "applied": False,
                "items": [{"fid": fid, "status": "pending_confirmation"} for fid in fids],
            },
            "Delete is blocked by default. Re-run with `--yes` to actually delete the selected items.",
        )

    if args.dry_run:
        return ok(
            {
                "planned": True,
                "applied": False,
                "items": [{"fid": fid, "status": "planned"} for fid in fids],
            },
            f"Prepared delete plan for {len(fids)} items.",
        )

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        result = await delete_remote_files(cookie, fids)
        await wait_for_task_if_needed(cookie, result)
    except Exception as exc:
        return fail("quark_api_error", str(exc), "Refresh login and try again.")

    return ok(
        {"planned": False, "applied": True, "items": [{"fid": fid, "status": "deleted"} for fid in fids]},
        f"Deleted {len(fids)} items.",
    )


async def command_upload(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    local_path = resolve_repo_path(args.local_path)
    if not local_path.exists():
        return fail("missing_local_file", f"Local file not found: {local_path}", "Pass an existing file path.")
    if not local_path.is_file():
        return fail("invalid_local_file", f"Upload only supports files in v1: {local_path}", "Pass a regular file path.")

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        account = await fetch_account_info(cookie)
        target = read_target_config() if not args.to_folder else {"pdir_id": str(args.to_folder), "dir_name": ""}
        if not args.to_folder and target["user"] != str(account.get("nickname", "")):
            target = {"pdir_id": "0", "dir_name": "根目录"}
        upload_result = await upload_file_via_browser(
            local_path,
            target["pdir_id"],
            find_items_in_folder_by_name=find_items_in_folder_by_name,
            list_folder_items=list_folder_items,
        )
    except Exception as exc:
        return fail("upload_failed", str(exc), "Confirm Quark is logged in, the page can load, and the upload button is available.")

    return ok(
        {
            "planned": False,
            "applied": True,
            "target": {"pdir_id": target["pdir_id"], "dir_name": target["dir_name"]},
            "items": [
                {
                    "local_path": str(Path(local_path).resolve()),
                    "status": "uploaded",
                    "remote": upload_result["remote"],
                    "signals": upload_result["signals"],
                }
            ],
        },
        f"Uploaded `{Path(local_path).name}` to Quark.",
    )
