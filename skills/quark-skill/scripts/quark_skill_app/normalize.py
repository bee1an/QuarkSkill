from __future__ import annotations

from typing import Any


def share_type_label(item: dict[str, Any]) -> str:
    first_file = item.get("first_file") or {}
    name = str(first_file.get("file_name") or item.get("title") or "").lower()
    format_type = str(first_file.get("format_type", "")).lower()
    categories = [str(value).lower() for value in item.get("first_layer_file_categories") or []]
    if item.get("video_total", 0):
        return "video"
    if item.get("pic_total", 0) or item.get("is_all_image_file"):
        return "img"
    if "video" in format_type or "mp4" in name or "mkv" in name:
        return "video"
    if "audio" in format_type or name.endswith((".mp3", ".wav", ".flac", ".m4a")):
        return "music"
    if name.endswith((".zip", ".rar", ".7z", ".tar", ".gz")):
        return "archive"
    if "image" in format_type or name.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        return "img"
    if "pdf" in format_type or name.endswith((".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt", ".md")):
        return "doc"
    if "7" in categories:
        return "archive"
    if "1" in categories:
        return "video"
    if "2" in categories:
        return "music"
    if "3" in categories:
        return "img"
    if any(value in categories for value in ["4", "5", "6"]):
        return "doc"
    return "all"


def normalize_file_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "fid": str(item.get("fid", "")),
        "file_name": str(item.get("file_name", "")),
        "pdir_fid": str(item.get("pdir_fid", "")),
        "dir": bool(item.get("dir")),
        "file": bool(item.get("file", not item.get("dir", False))),
        "size": int(item.get("size", 0) or 0),
        "category": item.get("category"),
        "file_type": item.get("file_type"),
        "updated_at": item.get("updated_at"),
        "created_at": item.get("created_at"),
        "source": item.get("source"),
        "path_info": item.get("path_info", ""),
    }


def normalize_recent_item(item: dict[str, Any]) -> dict[str, Any]:
    files = [normalize_file_item(file_item) for file_item in item.get("files") or []]
    return {
        "record_id": str(item.get("record_id", "")),
        "source": str(item.get("source", "")),
        "platform": str(item.get("platform", "")),
        "short_title": str((item.get("titles") or {}).get("short_title", "")),
        "long_title": str((item.get("titles") or {}).get("long_title", "")),
        "total_files": int(item.get("total_files", len(files)) or len(files)),
        "items": files,
        "operated_at": files[0].get("updated_at") if files else None,
    }


def normalize_myshare_item(item: dict[str, Any]) -> dict[str, Any]:
    first_file = item.get("first_file") or {}
    passcode = str(item.get("passcode", ""))
    return {
        "share_id": str(item.get("share_id", "")),
        "pwd_id": str(item.get("pwd_id", "")),
        "share_url": str(item.get("share_url", "")),
        "title": str(item.get("title", "")),
        "first_fid": str(item.get("first_fid", "")),
        "first_file_name": str(first_file.get("file_name", "")),
        "path_info": str(item.get("path_info", "")),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "expired_at": item.get("expired_at"),
        "expired_type": item.get("expired_type"),
        "url_type": item.get("url_type"),
        "passcode_required": int(item.get("url_type", 1) or 1) == 2,
        "passcode": passcode,
        "file_num": int(item.get("file_num", 0) or 0),
        "status": item.get("status"),
        "type": share_type_label(item),
    }


def normalize_share_update_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "share_id": str(item.get("share_id", "")),
        "pwd_id": str(item.get("pwd_id", "")),
        "share_url": str(item.get("share_url", "")),
        "title": str(item.get("title", "")),
        "path_info": str(item.get("path_info", "")),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "file_update_at": item.get("file_update_at"),
        "update_file_cnt": int(item.get("update_file_cnt", len(item.get("update_files") or [])) or 0),
        "author_name": str((item.get("author") or {}).get("author_name", "")),
        "items": [normalize_file_item(file_item) for file_item in item.get("update_files") or []],
    }
