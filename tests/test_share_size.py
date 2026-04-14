from __future__ import annotations

import json
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/quark-skill/scripts"))

from quark_skill_app import commands_share  # noqa: E402
from quark_skill_app.cli import build_parser  # noqa: E402


class ShareSizeTests(unittest.IsolatedAsyncioTestCase):
    async def test_collect_share_size_recurses(self) -> None:
        async def fake_fetch_share_detail(_: str, __: str, ___: str, pdir_fid: str = "0"):
            mapping = {
                "0": (
                    0,
                    [
                        {"fid": "folder-a", "file_name": "folder-a", "dir": True, "size": None},
                        {"fid": "file-root", "file_name": "root.bin", "dir": False, "size": 1024},
                    ],
                ),
                "folder-a": (
                    0,
                    [
                        {"fid": "file-child", "file_name": "child.bin", "dir": False, "size": 3},
                        {"fid": "folder-b", "file_name": "folder-b", "dir": True, "size": None},
                    ],
                ),
                "folder-b": (
                    0,
                    [
                        {"fid": "file-grandchild", "file_name": "grandchild.bin", "dir": False, "size": 5},
                    ],
                ),
            }
            return mapping[pdir_fid]

        with patch.object(commands_share, "fetch_share_detail", new=AsyncMock(side_effect=fake_fetch_share_detail)):
            summary = await commands_share.collect_share_size("cookie", "pwd", "stoken")

        self.assertEqual(
            summary,
            {"total_size_bytes": 1032, "files_count": 3, "folders_count": 2},
        )

    async def test_collect_share_size_supports_empty_share(self) -> None:
        with patch.object(commands_share, "fetch_share_detail", new=AsyncMock(return_value=(0, []))):
            summary = await commands_share.collect_share_size("cookie", "pwd", "stoken")

        self.assertEqual(
            summary,
            {"total_size_bytes": 0, "files_count": 0, "folders_count": 0},
        )

    async def test_collect_share_size_rejects_missing_file_size(self) -> None:
        with patch.object(
            commands_share,
            "fetch_share_detail",
            new=AsyncMock(
                return_value=(
                    0,
                    [{"fid": "file-1", "file_name": "broken.bin", "dir": False, "size": None}],
                )
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "missing size"):
                await commands_share.collect_share_size("cookie", "pwd", "stoken")

    async def test_command_share_size_reports_batch_results(self) -> None:
        args = Namespace(
            urls=[
                "https://pan.quark.cn/s/good",
                "https://pan.quark.cn/s/bad?pwd=1234",
            ],
            from_file=None,
        )

        async def fake_fetch_share_token(_: str, pwd_id: str, __: str) -> str:
            return "token" if pwd_id == "good" else ""

        async def fake_collect_share_size(_: str, pwd_id: str, __: str):
            self.assertEqual(pwd_id, "good")
            return {"total_size_bytes": 1536, "files_count": 2, "folders_count": 1}

        stdout = StringIO()
        with (
            patch.object(commands_share, "find_missing_modules", return_value=[]),
            patch.object(commands_share, "cookie_string_from_file", return_value="cookie"),
            patch.object(commands_share, "fetch_share_token", new=AsyncMock(side_effect=fake_fetch_share_token)),
            patch.object(commands_share, "collect_share_size", new=AsyncMock(side_effect=fake_collect_share_size)),
            redirect_stdout(stdout),
        ):
            exit_code = await commands_share.command_share_size(args)

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["results"]["summary"], {"total": 2, "sized": 1, "failed": 1})
        self.assertEqual(payload["results"]["results"][0]["total_size_bytes"], 1536)
        self.assertEqual(payload["results"]["results"][0]["total_size_human"], "1.50 KiB")
        self.assertEqual(payload["results"]["results"][1]["status"], "failed")

    async def test_command_share_size_dedupes_from_file_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            url_file = Path(temp_dir) / "urls.txt"
            url_file.write_text(
                "\n".join(
                    [
                        "https://pan.quark.cn/s/dup",
                        "https://pan.quark.cn/s/dup",
                        "https://pan.quark.cn/s/other",
                    ]
                ),
                encoding="utf-8",
            )
            args = Namespace(urls=["https://pan.quark.cn/s/dup"], from_file=str(url_file))
            seen_pwd_ids: list[str] = []
            stdout = StringIO()

            async def fake_fetch_share_token(_: str, pwd_id: str, __: str) -> str:
                seen_pwd_ids.append(pwd_id)
                return "token"

            async def fake_collect_share_size(_: str, __: str, ___: str):
                return {"total_size_bytes": 1, "files_count": 1, "folders_count": 0}

            with (
                patch.object(commands_share, "find_missing_modules", return_value=[]),
                patch.object(commands_share, "cookie_string_from_file", return_value="cookie"),
                patch.object(commands_share, "fetch_share_token", new=AsyncMock(side_effect=fake_fetch_share_token)),
                patch.object(commands_share, "collect_share_size", new=AsyncMock(side_effect=fake_collect_share_size)),
                redirect_stdout(stdout),
            ):
                exit_code = await commands_share.command_share_size(args)

        self.assertEqual(exit_code, 0)
        self.assertEqual(seen_pwd_ids, ["dup", "other"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["results"]["summary"], {"total": 2, "sized": 2, "failed": 0})

    def test_cli_parser_accepts_share_size(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["share-size", "https://pan.quark.cn/s/demo"])
        self.assertEqual(args.command, "share-size")
        self.assertEqual(args.urls, ["https://pan.quark.cn/s/demo"])
