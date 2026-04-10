# Commands

Run commands through the skill entrypoint.

## Install

```bash
pip install -r ${SKILL_PATH}/../../requirements.txt
python -m playwright install firefox
```

## Preflight

```bash
python3 ${SKILL_PATH}/scripts/quark_skill.py preflight
```

Success shape:

```json
{
  "status": "ok",
  "hint": "Ready. Logged into Quark as ...",
  "results": {
    "ready": true,
    "dependencies": {
      "httpx": "ok",
      "playwright.sync_api": "ok"
    },
    "auth": {
      "logged_in": true,
      "nickname": "..."
    },
    "target": {
      "user": "...",
      "pdir_id": "0",
      "dir_name": "根目录"
    }
  }
}
```

## Login

```bash
python3 ${SKILL_PATH}/scripts/quark_skill.py login
```

This opens Firefox, waits for the user to finish login, then stores cookies in `${SKILL_PATH}/../../config/cookies.txt`.

## Inspect Folders

```bash
python3 ${SKILL_PATH}/scripts/quark_skill.py folders
```

## Set Default Target

```bash
python3 ${SKILL_PATH}/scripts/quark_skill.py set-target --folder-id YOUR_FOLDER_ID
python3 ${SKILL_PATH}/scripts/quark_skill.py set-target --root
```

## Create Folder

```bash
python3 ${SKILL_PATH}/scripts/quark_skill.py create-dir "来自：分享"
python3 ${SKILL_PATH}/scripts/quark_skill.py create-dir "子目录" --parent-id YOUR_FOLDER_ID
```

## Batch Save

```bash
python3 ${SKILL_PATH}/scripts/quark_skill.py save "https://pan.quark.cn/s/..."
python3 ${SKILL_PATH}/scripts/quark_skill.py save "https://pan.quark.cn/s/one" "https://pan.quark.cn/s/two?pwd=1234"
python3 ${SKILL_PATH}/scripts/quark_skill.py save --from-file url.txt
python3 ${SKILL_PATH}/scripts/quark_skill.py save --from-file url.txt --target-id YOUR_FOLDER_ID
```

Per-link statuses are:

- `saved`
- `already_saved`
- `failed`

## Share

```bash
python3 ${SKILL_PATH}/scripts/quark_skill.py share QUARK_FOLDER_URL --traverse-depth 0
python3 ${SKILL_PATH}/scripts/quark_skill.py share QUARK_FOLDER_URL --traverse-depth 1 --expire permanent
python3 ${SKILL_PATH}/scripts/quark_skill.py share QUARK_FOLDER_URL --traverse-depth 2 --private --password 1234
```

Default output files:

- `share/share_url.txt`
- `share/retry.txt`
- `share/share_error.txt`

## Retry Share

```bash
python3 ${SKILL_PATH}/scripts/quark_skill.py retry-share
python3 ${SKILL_PATH}/scripts/quark_skill.py retry-share --from-file share/retry.txt
```

## Download

```bash
python3 ${SKILL_PATH}/scripts/quark_skill.py download "https://pan.quark.cn/s/..."
python3 ${SKILL_PATH}/scripts/quark_skill.py download --from-file url.txt
python3 ${SKILL_PATH}/scripts/quark_skill.py download --from-file url.txt --output-dir downloads
```
