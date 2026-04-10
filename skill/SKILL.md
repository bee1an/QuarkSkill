---
name: quarkpan-tool
description: Use when the user wants to log into Quark cloud drive, inspect root folders, set a default save directory, or batch-save Quark share links with the forked QuarkPanTool workflow. Prefer the structured wrapper before falling back to the original interactive script.
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

- If dependencies are missing, install them with `pip install -r ${SKILL_PATH}/../requirements.txt` and `python -m playwright install firefox`.
- If `ready` is `false` because login is missing or expired, run the login command next.
- If `ready` is `true`, continue with structured commands.

## Structured Commands

Prefer the wrapper script because it returns machine-readable JSON:

- `python3 ${SKILL_PATH}/scripts/quark_skill.py login`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py folders`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py set-target --folder-id FOLDER_ID`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py set-target --root`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py save "https://pan.quark.cn/s/..."`
- `python3 ${SKILL_PATH}/scripts/quark_skill.py save --from-file url.txt`

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
