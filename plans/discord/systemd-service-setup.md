# systemd Service Setup

Use a user-level `systemd` service on Debian to keep the bot running and restart it automatically after failures.

## Why
- Runs the bot in the background without keeping a shell open.
- Restarts the process automatically if it exits unexpectedly.
- Makes status and logs available through `systemctl` and `journalctl`.

## Config Prerequisites
Create a local `.env` from the example file before enabling the service:

```bash
cd ~/code/hots-update-bot
cp .env.example .env
```

Typical GCP-backed setup:

```bash
BOT_CONFIG_SOURCE=gcp
GCP_PROJECT_ID=your-gcp-project-id
BOOTSTRAP_SYNC_ON_EMPTY=true
BOOTSTRAP_SYNC_FORCE=false
BOOTSTRAP_SYNC_SKIP=false
```

## Example Unit File
Create `~/.config/systemd/user/hots-update-bot.service`:

```ini
[Unit]
Description=HOTS Update Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/code/hots-update-bot
EnvironmentFile=-%h/code/hots-update-bot/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=%h/code/hots-update-bot/scripts/start_bot.sh
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

Adjust the paths if the repository lives somewhere else.

The startup script can:
- bootstrap local cache on first run if required files are missing
- skip bootstrap when cache already exists
- start the bot only after the bootstrap decision completes

Current startup flow:
1. `systemd` starts `scripts/start_bot.sh`
2. `start_bot.sh` evaluates bootstrap rules from `.env`
3. if bootstrap is needed, it runs `./scripts/update_cache.sh both`
4. after bootstrap completes, it launches `bot/run.py`

## Enable And Start
```bash
systemctl --user daemon-reload
systemctl --user enable --now hots-update-bot.service
```

## Common Commands
Check whether the service is installed, enabled, and currently running:

```bash
systemctl --user status hots-update-bot.service
```

Start the service without changing enablement:

```bash
systemctl --user start hots-update-bot.service
```

Restart the service after code or config changes:

```bash
systemctl --user restart hots-update-bot.service
```

Stop the service:

```bash
systemctl --user stop hots-update-bot.service
```

Disable it so it no longer starts automatically for the user session:

```bash
systemctl --user disable hots-update-bot.service
```

Reload unit definitions after editing the service file:

```bash
systemctl --user daemon-reload
```

Recommended after changing unit or startup scripts:

```bash
systemctl --user daemon-reload
systemctl --user restart hots-update-bot.service
```

## Logs
Follow logs live:

```bash
journalctl --user -u hots-update-bot.service -f
```

Show the most recent log lines:

```bash
journalctl --user -u hots-update-bot.service -n 100 --no-pager
```

Show logs since the last boot:

```bash
journalctl --user -u hots-update-bot.service -b --no-pager
```

Filter logs by time:

```bash
journalctl --user -u hots-update-bot.service --since "2026-03-20 04:00:00" --no-pager
```

What you should expect in logs on first run:
- `Evaluating bootstrap sync state`
- a message explaining whether bootstrap was skipped, forced, or required
- news update logs
- HeroesProfile update logs
- `Starting Discord bot`

## Start On Boot Before Login
If the bot should keep running after reboots even when the user has not logged in yet:

```bash
sudo loginctl enable-linger "$USER"
```

## GCP Notes
- Keep `BOT_CONFIG_SOURCE=gcp` and `GCP_PROJECT_ID=...` in `.env`.
- The bot will read `BOT_TOKEN`, `GUILD_ID`, `NEWS_CHANNEL_ID`, and optional `DAILY_UPDATE_CRON` from GCP Secret Manager.
- The host still needs working Google application default credentials or another supported authentication path for Secret Manager access.

## Manual Cache Updates
Use the wrapper script from the repo root:

```bash
cd ~/code/hots-update-bot
./scripts/update_cache.sh
./scripts/update_cache.sh news --months 3
./scripts/update_cache.sh heroes --only heroes,talents
```

Notes:
- no service stop is required before running manual cache updates
- default mode is `both`
- extra updater arguments are only supported for `news` or `heroes`, not `both`

## Bootstrap Flags
Optional `.env` flags for service startup:

```bash
BOOTSTRAP_SYNC_ON_EMPTY=true
BOOTSTRAP_SYNC_FORCE=false
BOOTSTRAP_SYNC_SKIP=false
```

Precedence:
- `BOOTSTRAP_SYNC_SKIP=true` skips bootstrap entirely
- otherwise `BOOTSTRAP_SYNC_FORCE=true` always runs bootstrap
- otherwise `BOOTSTRAP_SYNC_ON_EMPTY=true` runs bootstrap only when `news/index.json` or `heroesprofile/manifest.json` is missing
- otherwise startup skips bootstrap and launches the bot directly
