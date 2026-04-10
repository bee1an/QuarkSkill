---
name: quark-skill
description: Use when the user wants to log into Quark cloud drive, inspect root folders, create folders, set a default save directory, batch-save Quark share links, generate Quark share links from folders, retry failed shares, or download files from their own Quark shares.
---

# QuarkPanTool Skill

Use this skill for Quark cloud drive operations with a structured local wrapper in this repository.

## Language

Match the user's language.

## Preflight First

Always start with:

```bash
python3 ${SKILL_PATH}/scripts/quark_skill.py preflight
```

Interpret the result before doing anything else:

- If dependencies are missing, install them with `pip install -r ${SKILL_PATH}/../../requirements.txt` and `python -m playwright install firefox`.
- If `ready` is `false` because login is missing or expired, run the login command next.
- If `ready` is `true`, continue with structured commands.

## Structured Commands

Prefer the wrapper script because it returns machine-readable JSON:

- `python3 ${SKILL_PATH}/scripts/quark_skill.py login`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py folders`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py set-target --folder-id FOLDER_ID`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py set-target --root`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py create-dir "文件夹名"`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py save "https://pan.quark.cn/s/..."`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py save --from-file url.txt`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py share QUARK_FOLDER_URL --traverse-depth 0`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py retry-share`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py download "https://pan.quark.cn/s/..."`

Read [references/commands.md](./references/commands.md) when you need concrete examples or output shapes.

## Login Flow

`login` is interactive:

1. Launch the command.
2. A Firefox window opens to Quark.
3. Ask the user to complete login in the browser.
4. After login completes, press Enter in the terminal.
5. Re-run `preflight` if you need to verify the account and target state again.

## Save Workflow

Preferred sequence:

1. Run `preflight`.
2. If needed, run `login`.
3. Run `folders` if you need a folder id.
4. Run `set-target` once for the destination folder.
5. Run `save` with one or more share URLs, or `--from-file`.

The wrapper returns a per-link status summary:

- `saved`
- `already_saved`
- `failed`

If the user wants a one-off destination without changing the saved default, pass `--target-id`.

## Share Workflow

Use `share` to generate share links from your own Quark folder page URL or folder id.

- `--traverse-depth 0` shares the folder itself
- `--traverse-depth 1` shares each first-level child folder
- `--traverse-depth 2` shares second-level child folders
- `--private` makes the generated links password-protected
- `retry-share` retries failed entries written by the last `share` run

Generated URLs and retry state are written under the repository `share/` directory by default.

## Download Workflow

Use `download` for share links created from your own Quark drive files.

- It writes files under the repository `downloads/` directory by default
- It can take direct URLs or `--from-file`
- It fails fast for third-party shares that are not owned by the logged-in account
