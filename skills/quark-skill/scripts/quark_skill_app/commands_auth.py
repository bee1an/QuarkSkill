from __future__ import annotations

import argparse

from .api import create_remote_dir, fetch_account_info, fetch_root_folders
from .browser import capture_login_cookies
from .constants import CONFIG_DIR, COOKIES_FILE, INSTALL_HINT
from .output import fail, ok
from .state import (
    cookie_string_from_file,
    find_missing_modules,
    read_target_config,
    resolve_bound_target,
    write_target_config,
)


async def command_preflight(_: argparse.Namespace) -> int:
    missing = find_missing_modules()
    dependencies = {
        module_name: "ok" if module_name not in missing else "missing"
        for module_name in __import__("quark_skill_app.constants", fromlist=["REQUIRED_MODULES"]).REQUIRED_MODULES
    }
    if "socksio" in missing:
        dependencies["socksio"] = "missing"

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
            "auth": {"logged_in": True, "nickname": account.get("nickname", "")},
            "target": target,
        },
        f"Ready. Logged into Quark as {account.get('nickname', '')} and saving to {target['dir_name']}.",
    )


async def command_login(_: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cookies = await capture_login_cookies()
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
        {"logged_in": True, "nickname": account.get("nickname", ""), "target": target},
        f"Login succeeded for {account.get('nickname', '')}.",
    )


async def command_folders(_: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

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
        {"user": account.get("nickname", ""), "target": target, "folders": folders},
        f"Found {len(folders)} root folders for {account.get('nickname', '')}.",
    )


async def command_set_target(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

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


async def command_create_dir(args: argparse.Namespace) -> int:
    missing = find_missing_modules()
    if missing:
        return fail("missing_dependencies", f"Missing Python modules: {', '.join(missing)}", INSTALL_HINT)

    cookie = cookie_string_from_file()
    if not cookie:
        return fail("not_logged_in", "Quark is not logged in", "Run the login command first.")

    try:
        account = await fetch_account_info(cookie)
        result = await create_remote_dir(cookie, args.name.strip(), pdir_fid=str(args.parent_id))
    except Exception as exc:
        return fail("quark_api_error", str(exc), "Refresh login and try again.")

    if result.get("code") == 23008:
        return fail("name_conflict", "A folder with the same name already exists.", "Choose a different folder name.")
    if result.get("code") != 0:
        return fail("create_dir_failed", str(result.get("message", "failed to create folder")), "Retry with a different name.")

    data = result.get("data") or {}
    return ok(
        {
            "user": account.get("nickname", ""),
            "folder": {"fid": data.get("fid", ""), "file_name": args.name.strip(), "pdir_fid": str(args.parent_id)},
            "applied": True,
        },
        f"Created folder {args.name.strip()}.",
    )
