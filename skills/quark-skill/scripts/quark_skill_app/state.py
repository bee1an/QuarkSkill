from __future__ import annotations

import ast
import importlib
import json
import os
import random
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from .constants import CONFIG_DIR, COOKIES_FILE, REQUIRED_MODULES, SHARE_DIR, TARGET_FILE, REPO_ROOT


def find_missing_modules() -> list[str]:
    missing: list[str] = []
    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(module_name)

    proxy_env_names = ("ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "all_proxy", "https_proxy", "http_proxy")
    if any(str(os.environ.get(name, "")).startswith("socks") for name in proxy_env_names):
        try:
            importlib.import_module("socksio")
        except Exception:
            missing.append("socksio")
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


def random_code(length: int = 4) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(alphabet) for _ in range(length))


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
        file_path = resolve_repo_path(from_file)
        for line in file_path.read_text(encoding="utf-8").splitlines():
            collect(line)

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            deduped.append(url)
            seen.add(url)
    return deduped


def extract_folder_resource_id(raw: str) -> str:
    text = raw.strip()
    if re.fullmatch(r"[A-Za-z0-9]{8,64}", text):
        return text

    parsed = urlparse(text)
    candidates: list[str] = []
    for part in [*parsed.path.split("/"), *parsed.fragment.split("/")]:
        token = part.strip()
        if not token:
            continue
        token = token.split("?", 1)[0].split("#", 1)[0].split("-", 1)[0]
        if re.fullmatch(r"[A-Za-z0-9]{8,64}", token):
            candidates.append(token)

    if candidates:
        return candidates[-1]

    raise ValueError(f"Unable to extract a Quark folder id from: {raw}")


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
        json.dumps({"user": user, "pdir_id": pdir_id, "dir_name": dir_name}, ensure_ascii=False),
        encoding="utf-8",
    )


def resolve_bound_target(user: str) -> dict[str, str]:
    config = read_target_config()
    if config["user"] != user:
        config = {"user": user, "pdir_id": "0", "dir_name": "根目录"}
        write_target_config(**config)
    return config


def build_nested_path(pdir_fid: str, folders_map: dict[str, dict[str, str]]) -> Path:
    parts: list[str] = []
    current = pdir_fid
    while current in folders_map:
        folder = folders_map[current]
        parts.append(folder["file_name"])
        current = folder["pdir_fid"]
    return Path(*reversed(parts)) if parts else Path()


def ensure_share_workspace() -> None:
    SHARE_DIR.mkdir(parents=True, exist_ok=True)


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(lines)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def resolve_repo_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


def parse_id_batch_file(raw: str) -> list[str]:
    file_path = resolve_repo_path(raw)
    ids: list[str] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith("{"):
            data = json.loads(text)
            ids.append(str(data["fid"]))
        else:
            ids.append(text)
    return ids


def parse_rename_batch_file(raw: str) -> list[dict[str, str]]:
    file_path = resolve_repo_path(raw)
    mappings: list[dict[str, str]] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        text = line.rstrip("\n")
        if not text.strip():
            continue
        if "\t" not in text:
            raise ValueError("rename batch file must use `fid<TAB>new_name` format")
        fid, new_name = text.split("\t", 1)
        mappings.append({"fid": fid.strip(), "new_name": new_name.strip()})
    return mappings
