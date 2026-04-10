from __future__ import annotations

import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = SKILL_DIR.parents[1]
CONFIG_DIR = REPO_ROOT / "config"
COOKIES_FILE = CONFIG_DIR / "cookies.txt"
TARGET_FILE = CONFIG_DIR / "config.json"
SHARE_DIR = REPO_ROOT / "share"
DOWNLOADS_DIR = REPO_ROOT / "downloads"
DEFAULT_SHARE_FILE = SHARE_DIR / "share_url.txt"
DEFAULT_RETRY_FILE = SHARE_DIR / "retry.txt"
DEFAULT_RETRY_SHARE_FILE = SHARE_DIR / "retry_share_url.txt"
DEFAULT_SHARE_ERROR_FILE = SHARE_DIR / "share_error.txt"
WEB_BROWSER_DATA_DIR = REPO_ROOT / "web_browser_data"
INSTALL_HINT = (
    f"Run `pip install -r {REPO_ROOT / 'requirements.txt'}` and "
    "`python -m playwright install firefox` first."
)
REQUIRED_MODULES = [
    "httpx",
    "playwright.async_api",
    "tqdm",
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
CATEGORY_SCOPE_MAP = {
    "video": "video",
    "img": "img",
    "doc": "doc",
    "music": "music",
    "bt": "bt",
}
SHARE_TYPE_CHOICES = ["all", "video", "doc", "img", "archive", "music"]

os.chdir(REPO_ROOT)
