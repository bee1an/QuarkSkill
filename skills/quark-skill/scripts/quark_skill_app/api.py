from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Any

from .constants import DEFAULT_HEADERS
from .state import random_code, random_dt, timestamp_ms


def ensure_ok(result: dict[str, Any], default_message: str) -> dict[str, Any]:
    if result.get("code") not in (0, None):
        raise RuntimeError(str(result.get("message") or default_message))
    return result


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


async def api_post(url: str, cookie: str, *, params: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
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
    result = await api_get("https://pan.quark.cn/account/info", cookie, params={"fr": "pc", "platform": "pc"})
    data = result.get("data")
    if not data:
        raise RuntimeError(result.get("message", "unable to verify quark account"))
    return data


async def fetch_sorted_file_list(
    cookie: str,
    pdir_fid: str = "0",
    page: str = "1",
    size: str = "100",
    fetch_total: str = "false",
    sort: str = "",
    fetch_sub_dirs: str = "1",
) -> dict[str, Any]:
    return ensure_ok(
        await api_get(
            "https://drive-pc.quark.cn/1/clouddrive/file/sort",
            cookie,
            params={
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "pdir_fid": pdir_fid,
                "_page": page,
                "_size": size,
                "_fetch_total": fetch_total,
                "_fetch_sub_dirs": fetch_sub_dirs,
                "_sort": sort,
                "fetch_all_file": "1",
                "fetch_risk_file_name": "1",
                "__dt": random_dt(),
                "__t": timestamp_ms(),
            },
        ),
        "failed to fetch file list",
    )


async def fetch_root_folders(cookie: str) -> list[dict[str, str]]:
    result = await fetch_sorted_file_list(cookie, pdir_fid="0", page="1", size="100", fetch_total="false", sort="", fetch_sub_dirs="1")
    folders: list[dict[str, str]] = []
    for item in result.get("data", {}).get("list", []):
        if item.get("dir"):
            folders.append({"fid": item["fid"], "file_name": item["file_name"]})
    return folders


async def fetch_category_list(cookie: str, category: str, page: int, size: int) -> dict[str, Any]:
    return ensure_ok(
        await api_get(
            "https://drive-pc.quark.cn/1/clouddrive/file/category",
            cookie,
            params={
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "cat": category,
                "_page": str(page),
                "_size": str(size),
                "_fetch_total": "1",
                "_sort": "file_type:asc,updated_at:desc",
            },
        ),
        "failed to fetch category list",
    )


async def fetch_recent_list(cookie: str, item_size: int) -> dict[str, Any]:
    return ensure_ok(
        await api_get(
            "https://drive-pc.quark.cn/1/clouddrive/behavior/recent/list",
            cookie,
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": "", "item_size": str(item_size)},
        ),
        "failed to fetch recent list",
    )


async def fetch_search_list(cookie: str, keyword: str, page: int, size: int) -> dict[str, Any]:
    return ensure_ok(
        await api_get(
            "https://drive-pc.quark.cn/1/clouddrive/file/search",
            cookie,
            params={
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "q": keyword,
                "_page": str(page),
                "_size": str(size),
                "_fetch_total": "1",
                "_sort": "file_type:desc,updated_at:desc",
                "_is_hl": "1",
            },
        ),
        "failed to search files",
    )


async def fetch_myshare_page(cookie: str, page: int, size: int) -> dict[str, Any]:
    return ensure_ok(
        await api_get(
            "https://drive-pc.quark.cn/1/clouddrive/share/mypage/detail",
            cookie,
            params={
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "_page": str(page),
                "_size": str(size),
                "_order_field": "created_at",
                "_order_type": "desc",
                "_fetch_total": "1",
                "_fetch_notify_follow": "1",
            },
        ),
        "failed to fetch myshare list",
    )


async def fetch_transfer_update_page(cookie: str, page: int, size: int) -> dict[str, Any]:
    return ensure_ok(
        await api_post(
            "https://drive-pc.quark.cn/1/clouddrive/share/update_list",
            cookie,
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
            payload={
                "page": page,
                "needTotalNum": 1,
                "share_read_statues": [0, 1],
                "fetch_total": 1,
                "fetch_max_file_update_pos": 1,
                "fetch_update_files": 1,
                "page_size": size,
            },
        ),
        "failed to fetch transfer updates",
    )


async def create_remote_dir(cookie: str, file_name: str, pdir_fid: str = "0") -> dict[str, Any]:
    return await api_post(
        "https://drive-pc.quark.cn/1/clouddrive/file",
        cookie,
        params={"pr": "ucpro", "fr": "pc", "uc_param_str": "", "__dt": random_dt(), "__t": timestamp_ms()},
        payload={"pdir_fid": pdir_fid, "file_name": file_name, "dir_path": "", "dir_init_lock": False},
    )


async def rename_remote_file(cookie: str, fid: str, file_name: str) -> dict[str, Any]:
    return ensure_ok(
        await api_post(
            "https://drive-pc.quark.cn/1/clouddrive/file/rename",
            cookie,
            params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
            payload={"fid": fid, "file_name": file_name},
        ),
        "failed to rename file",
    )


async def move_remote_files(cookie: str, fids: list[str], to_folder_id: str) -> dict[str, Any]:
    return await api_post(
        "https://drive-pc.quark.cn/1/clouddrive/file/move",
        cookie,
        params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
        payload={"action_type": 1, "to_pdir_fid": to_folder_id, "filelist": fids, "exclude_fids": []},
    )


async def delete_remote_files(cookie: str, fids: list[str]) -> dict[str, Any]:
    return await api_post(
        "https://drive-pc.quark.cn/1/clouddrive/file/delete",
        cookie,
        params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
        payload={"action_type": 2, "filelist": fids, "exclude_fids": []},
    )


async def fetch_share_token(cookie: str, pwd_id: str, password: str) -> str:
    result = await api_post(
        "https://drive-pc.quark.cn/1/clouddrive/share/sharepage/token",
        cookie,
        params={"pr": "ucpro", "fr": "pc", "uc_param_str": "", "__dt": random_dt(), "__t": timestamp_ms()},
        payload={"pwd_id": pwd_id, "passcode": password},
    )
    return str((result.get("data") or {}).get("stoken", ""))


async def fetch_share_detail(cookie: str, pwd_id: str, stoken: str, pdir_fid: str = "0") -> tuple[int, list[dict[str, Any]]]:
    file_list: list[dict[str, Any]] = []
    page = 1
    is_owner = 0
    while True:
        result = ensure_ok(
            await api_get(
                "https://drive-h.quark.cn/1/clouddrive/share/sharepage/detail",
                cookie,
                params={
                    "pr": "ucpro",
                    "fr": "pc",
                    "uc_param_str": "",
                    "ver": "2",
                    "pwd_id": pwd_id,
                    "stoken": stoken,
                    "pdir_fid": pdir_fid,
                    "force": "0",
                    "_page": str(page),
                    "_size": "50",
                    "_fetch_banner": "1",
                    "_fetch_share": "1",
                    "fetch_relate_conversation": "1",
                    "_fetch_total": "1",
                    "_sort": "file_type:asc,file_name:asc",
                },
            ),
            "failed to fetch share detail",
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
                    "size": item.get("size"),
                    "include_items": item.get("include_items", 0),
                    "share_fid_token": item["share_fid_token"],
                }
            )
        total = int(metadata.get("_total", 0))
        page_size = int(metadata.get("_size", 50) or 50)
        count = int(metadata.get("_count", len(items)) or len(items))
        if total <= page_size or count < page_size:
            break
        page += 1
    return is_owner, file_list


async def create_save_task(cookie: str, pwd_id: str, stoken: str, items: list[dict[str, Any]], target_id: str) -> str:
    result = await api_post(
        "https://drive.quark.cn/1/clouddrive/share/sharepage/save",
        cookie,
        params={"pr": "ucpro", "fr": "pc", "uc_param_str": "", "__dt": random_dt(600, 9999), "__t": timestamp_ms()},
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
    task_id = (result.get("data") or {}).get("task_id")
    if not task_id:
        raise RuntimeError(result.get("message", "failed to create save task"))
    return str(task_id)


async def create_share_task(cookie: str, fid: str, title: str, url_type: int = 1, expired_type: int = 2, password: str = "") -> str:
    payload: dict[str, Any] = {"fid_list": [fid], "title": title, "url_type": url_type, "expired_type": expired_type}
    if url_type == 2:
        payload["passcode"] = password or random_code()
    result = await api_post(
        "https://drive-pc.quark.cn/1/clouddrive/share",
        cookie,
        params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
        payload=payload,
    )
    task_id = (result.get("data") or {}).get("task_id")
    if not task_id:
        raise RuntimeError(result.get("message", "failed to create share task"))
    return str(task_id)


async def fetch_share_id(cookie: str, task_id: str) -> str:
    result = await api_get(
        "https://drive-pc.quark.cn/1/clouddrive/task",
        cookie,
        params={"pr": "ucpro", "fr": "pc", "uc_param_str": "", "task_id": task_id, "retry_index": "0"},
    )
    share_id = (result.get("data") or {}).get("share_id")
    if not share_id:
        raise RuntimeError(result.get("message", "failed to fetch share id"))
    return str(share_id)


async def finalize_share(cookie: str, share_id: str) -> dict[str, str]:
    result = await api_post(
        "https://drive-pc.quark.cn/1/clouddrive/share/password",
        cookie,
        params={"pr": "ucpro", "fr": "pc", "uc_param_str": ""},
        payload={"share_id": share_id},
    )
    data = result.get("data") or {}
    share_url = data.get("share_url")
    title = data.get("title")
    if not share_url or not title:
        raise RuntimeError(result.get("message", "failed to finalize share"))
    passcode = data.get("passcode")
    if passcode:
        share_url = f"{share_url}?pwd={passcode}"
    return {"share_url": str(share_url), "title": str(title)}


async def fetch_download_links(cookie: str, fids: list[str]) -> list[dict[str, Any]]:
    if not fids:
        return []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
        ),
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "accept-language": "zh-CN",
        "origin": "https://pan.quark.cn",
        "referer": "https://pan.quark.cn/",
        "cookie": cookie,
    }
    payload = {"fids": fids}
    params = {"pr": "ucpro", "fr": "pc", "sys": "win32", "ve": "2.5.56", "ut": "", "guid": ""}
    httpx = await get_httpx()
    for _ in range(2):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://drive-pc.quark.cn/1/clouddrive/file/download",
                json=payload,
                params=params,
                headers=headers,
                timeout=httpx.Timeout(60.0, connect=60.0),
            )
        result = response.json()
        if result.get("code") == 23018:
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) quark-cloud-drive/2.5.56 Chrome/100.0.4896.160 "
                "Electron/18.3.5.12-a038f7b798 Safari/537.36 Channel/pckk_other_ch"
            )
            continue
        if result.get("status") != 200:
            raise RuntimeError(result.get("message", "failed to fetch download urls"))
        return list(result.get("data") or [])
    raise RuntimeError("failed to fetch download urls")


async def stream_download_file(cookie: str, download_url: str, save_path: Path) -> None:
    httpx = await get_httpx()
    headers = {
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
        ),
        "origin": "https://pan.quark.cn",
        "referer": "https://pan.quark.cn/",
        "cookie": cookie,
    }
    save_path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", download_url, headers=headers, timeout=httpx.Timeout(60.0, connect=60.0)) as response:
            response.raise_for_status()
            with save_path.open("wb") as file_obj:
                async for chunk in response.aiter_bytes():
                    file_obj.write(chunk)


async def poll_task(cookie: str, task_id: str, retries: int = 50) -> dict[str, Any]:
    retry_gap_ms = 1000
    for retry_index in range(retries):
        if retry_index > 0:
            await asyncio.sleep(retry_gap_ms / 1000)
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
        data = result.get("data") or {}
        if result.get("code") in (0, None) and (data.get("status") == 2 or data.get("finish") is True):
            return result
        if result.get("code") == 32003 and "capacity limit" in str(result.get("message", "")):
            raise RuntimeError("网盘容量不足")
        if result.get("code") == 41013:
            raise RuntimeError("保存目录不存在，请重新设置目标目录")
        retry_gap_ms = int((result.get("metadata") or {}).get("tq_gap", retry_gap_ms) or retry_gap_ms)
    raise TimeoutError("task timed out")


async def wait_for_task_if_needed(cookie: str, result: dict[str, Any]) -> dict[str, Any]:
    if result.get("code") not in (0, None):
        raise RuntimeError(str(result.get("message") or "task failed"))
    data = result.get("data") or {}
    task_id = str(data.get("task_id", "") or "")
    if task_id and not data.get("finish", False):
        return await poll_task(cookie, task_id)
    return result
