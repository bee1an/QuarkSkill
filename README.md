# QuarkSkill

QuarkSkill is a standalone repository for a Codex skill that works with Quark cloud drive.

It provides:

- a structured skill entrypoint for readiness checks, login, folder inspection, folder creation, batch save, batch share, retry-share, and local download
- a `skills/quark-skill/` directory that can be consumed as a Codex skill

## Repository Layout

```text
.
├── skills/quark-skill/     # Codex skill metadata, docs, and structured wrapper
├── requirements.txt
└── LICENSE
```

`config/` is created locally at runtime and is not tracked by Git.

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
python -m playwright install firefox
```

Run a preflight check:

```bash
python3 skills/quark-skill/scripts/quark_skill.py preflight
```

Log into Quark:

```bash
python3 skills/quark-skill/scripts/quark_skill.py login
```

Inspect folders and set a default target:

```bash
python3 skills/quark-skill/scripts/quark_skill.py folders
python3 skills/quark-skill/scripts/quark_skill.py set-target --folder-id YOUR_FOLDER_ID
python3 skills/quark-skill/scripts/quark_skill.py create-dir "来自：分享"
```

Batch-save share links:

```bash
python3 skills/quark-skill/scripts/quark_skill.py save "https://pan.quark.cn/s/..."
python3 skills/quark-skill/scripts/quark_skill.py save --from-file url.txt
```

Create share links from your own Quark folders:

```bash
python3 skills/quark-skill/scripts/quark_skill.py share QUARK_FOLDER_URL --traverse-depth 0
python3 skills/quark-skill/scripts/quark_skill.py retry-share
```

Download files from your own Quark shares:

```bash
python3 skills/quark-skill/scripts/quark_skill.py download "https://pan.quark.cn/s/..."
python3 skills/quark-skill/scripts/quark_skill.py download --from-file url.txt
```

## Upstream Attribution

This repository is an independent project, not a GitHub fork.

Its implementation is adapted from ideas and workflow in [ihmily/QuarkPanTool](https://github.com/ihmily/QuarkPanTool). The original project is licensed under Apache-2.0, and this repository keeps the Apache-2.0 license in [LICENSE](/Users/bee/j/Quark-skill/LICENSE).

The new skill wrapper and repository-specific changes are also distributed under Apache-2.0.
