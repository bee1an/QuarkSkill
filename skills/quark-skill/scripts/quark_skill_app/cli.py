from __future__ import annotations

import argparse
import asyncio

from .commands_auth import command_create_dir, command_folders, command_login, command_preflight, command_set_target
from .commands_drive import command_delete, command_list, command_move, command_rename, command_search, command_upload
from .commands_share import (
    command_download,
    command_list_myshare,
    command_list_transfer_updates,
    command_retry_share,
    command_save,
    command_share_size,
    command_share,
)
from .constants import DEFAULT_RETRY_FILE, DEFAULT_RETRY_SHARE_FILE, DEFAULT_SHARE_ERROR_FILE, DEFAULT_SHARE_FILE, DOWNLOADS_DIR, REPO_ROOT, SHARE_TYPE_CHOICES
from .output import fail


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Structured skill entrypoint for QuarkSkill.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("preflight", help="Check dependencies, login state, and default target.")
    subparsers.add_parser("login", help="Open a browser and capture fresh Quark cookies.")
    subparsers.add_parser("folders", help="List root folders and the current default target.")

    set_target_parser = subparsers.add_parser("set-target", help="Persist the default save target.")
    set_target_group = set_target_parser.add_mutually_exclusive_group(required=True)
    set_target_group.add_argument("--folder-id", help="Root-level folder id to use for future saves.")
    set_target_group.add_argument("--root", action="store_true", help="Reset the default target to the Quark root.")

    create_dir_parser = subparsers.add_parser("create-dir", help="Create a Quark folder.")
    create_dir_parser.add_argument("name", help="Folder name to create.")
    create_dir_parser.add_argument("--parent-id", default="0", help="Parent folder id. Defaults to the Quark root.")

    list_parser = subparsers.add_parser("list", help="List files from a Quark scope.")
    list_parser.add_argument("--scope", choices=["all", "recent", "video", "img", "doc", "music", "bt", "myshare"], default="all")
    list_parser.add_argument("--folder-id", help="Folder id for `all` scope. Defaults to root.")
    list_parser.add_argument("--page", type=int, default=1)
    list_parser.add_argument("--size", type=int, default=50)

    search_parser = subparsers.add_parser("search", help="Search files or shares.")
    search_parser.add_argument("keyword", help="Search keyword.")
    search_parser.add_argument("--scope", choices=["all", "myshare"], default="all")
    search_parser.add_argument("--page", type=int, default=1)
    search_parser.add_argument("--size", type=int, default=50)

    save_parser = subparsers.add_parser("save", help="Batch-save Quark share links.")
    save_parser.add_argument("urls", nargs="*", help="One or more share URLs.")
    save_parser.add_argument("--from-file", help="Read share URLs from a text file.")
    save_parser.add_argument("--target-id", help="Override the saved target folder id for this run only.")

    share_size_parser = subparsers.add_parser("share-size", help="Calculate the total size of one or more Quark share links.")
    share_size_parser.add_argument("urls", nargs="*", help="One or more share URLs.")
    share_size_parser.add_argument("--from-file", help="Read share URLs from a text file.")

    share_parser = subparsers.add_parser("share", help="Create Quark share links from a folder page URL or folder id.")
    share_parser.add_argument("resource", help="Quark folder page URL or folder id.")
    share_parser.add_argument("--private", action="store_true", help="Create password-protected share links.")
    share_parser.add_argument("--password", default="", help="Optional share password when using --private.")
    share_parser.add_argument("--expire", choices=["1d", "7d", "30d", "permanent"], default="30d", help="Share expiry.")
    share_parser.add_argument("--traverse-depth", type=int, choices=[0, 1, 2], default=0, help="0 shares the folder itself, 1 shares first-level subfolders, 2 shares second-level subfolders.")
    share_parser.add_argument("--output-file", default=str(DEFAULT_SHARE_FILE.relative_to(REPO_ROOT)), help="Where to write generated share URLs.")
    share_parser.add_argument("--retry-file", default=str(DEFAULT_RETRY_FILE.relative_to(REPO_ROOT)), help="Where to write retry entries for failed shares.")
    share_parser.add_argument("--error-file", default=str(DEFAULT_SHARE_ERROR_FILE.relative_to(REPO_ROOT)), help="Where to write failed share labels.")

    retry_share_parser = subparsers.add_parser("retry-share", help="Retry failed share entries from a retry file.")
    retry_share_parser.add_argument("--from-file", default=str(DEFAULT_RETRY_FILE.relative_to(REPO_ROOT)), help="Retry file produced by the share command.")
    retry_share_parser.add_argument("--private", action="store_true", help="Create password-protected share links.")
    retry_share_parser.add_argument("--password", default="", help="Optional share password when using --private.")
    retry_share_parser.add_argument("--expire", choices=["1d", "7d", "30d", "permanent"], default="30d", help="Share expiry.")
    retry_share_parser.add_argument("--output-file", default=str(DEFAULT_RETRY_SHARE_FILE.relative_to(REPO_ROOT)), help="Where to write successfully retried share URLs.")

    download_parser = subparsers.add_parser("download", help="Download files from Quark shares created from your own drive.")
    download_parser.add_argument("urls", nargs="*", help="One or more share URLs.")
    download_parser.add_argument("--from-file", help="Read share URLs from a text file.")
    download_parser.add_argument("--output-dir", default=str(DOWNLOADS_DIR.relative_to(REPO_ROOT)), help="Directory where downloaded files should be written.")

    move_parser = subparsers.add_parser("move", help="Move Quark files or folders.")
    move_parser.add_argument("fid", nargs="?", help="Single Quark file or folder id.")
    move_parser.add_argument("--from-file", help="Read file ids from a txt/jsonl file.")
    move_parser.add_argument("--to-folder", required=True, help="Destination folder id.")
    move_parser.add_argument("--dry-run", action="store_true", help="Show the move plan without applying it.")

    rename_parser = subparsers.add_parser("rename", help="Rename Quark files or folders.")
    rename_parser.add_argument("fid", nargs="?", help="Single Quark file or folder id.")
    rename_parser.add_argument("--name", help="New file name for single-item mode.")
    rename_parser.add_argument("--from-file", help="Read `fid<TAB>new_name` lines from a batch file.")
    rename_parser.add_argument("--dry-run", action="store_true", help="Show the rename plan without applying it.")

    delete_parser = subparsers.add_parser("delete", help="Delete Quark files or folders.")
    delete_parser.add_argument("fid", nargs="?", help="Single Quark file or folder id.")
    delete_parser.add_argument("--from-file", help="Read file ids from a txt/jsonl file.")
    delete_parser.add_argument("--yes", action="store_true", help="Actually delete the selected items.")
    delete_parser.add_argument("--dry-run", action="store_true", help="Show the delete plan without applying it.")

    list_myshare_parser = subparsers.add_parser("list-myshare", help="List the current account's Quark shares.")
    list_myshare_parser.add_argument("--type", choices=SHARE_TYPE_CHOICES, default="all")
    list_myshare_parser.add_argument("--page", type=int, default=1)
    list_myshare_parser.add_argument("--size", type=int, default=50)

    transfer_updates_parser = subparsers.add_parser("list-transfer-updates", help="List saved-share items that have upstream updates.")
    transfer_updates_parser.add_argument("--page", type=int, default=1)
    transfer_updates_parser.add_argument("--size", type=int, default=50)

    upload_parser = subparsers.add_parser("upload", help="Upload a local file to Quark via the logged-in browser session.")
    upload_parser.add_argument("local_path", help="Local file path to upload.")
    upload_parser.add_argument("--to-folder", help="Destination Quark folder id. Defaults to the saved target.")

    return parser


async def dispatch(args: argparse.Namespace) -> int:
    handlers = {
        "preflight": command_preflight,
        "login": command_login,
        "folders": command_folders,
        "set-target": command_set_target,
        "create-dir": command_create_dir,
        "list": command_list,
        "search": command_search,
        "save": command_save,
        "share-size": command_share_size,
        "share": command_share,
        "retry-share": command_retry_share,
        "download": command_download,
        "move": command_move,
        "rename": command_rename,
        "delete": command_delete,
        "list-myshare": command_list_myshare,
        "list-transfer-updates": command_list_transfer_updates,
        "upload": command_upload,
    }
    return await handlers[args.command](args)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(dispatch(args))
    except KeyboardInterrupt:
        return fail("interrupted", "Command interrupted by user", "Retry the command when ready.")
