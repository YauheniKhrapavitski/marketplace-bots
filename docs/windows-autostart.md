# Windows Autostart

The TTN bot can run on this Windows computer by starting Docker Desktop and then the Docker Compose stack at user logon.

Autostart is configured through the current user's Startup folder:

```text
C:\Users\web_a\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\TTN Telegram Bot Autostart.lnk
```

## Files

- `scripts/start-bot.ps1` starts Docker Desktop if needed, stops any local `python -m ttn_bot.main` process, waits for Docker Engine, then runs `docker compose up -d`.
- `scripts/stop-bot.ps1` runs `docker compose down` and stops any local `python -m ttn_bot.main` process.
- `logs/autostart.log` contains autostart script checkpoints.
- `logs/compose-up.log` contains the latest `docker compose up -d` output.

## Useful Commands

Check containers:

```powershell
cd C:\Users\web_a\Documents\MarketPlace
docker compose ps
```

Start manually:

```powershell
powershell.exe -ExecutionPolicy Bypass -File C:\Users\web_a\Documents\MarketPlace\scripts\start-bot.ps1
```

Stop manually:

```powershell
powershell.exe -ExecutionPolicy Bypass -File C:\Users\web_a\Documents\MarketPlace\scripts\stop-bot.ps1
```

Remove autostart:

```powershell
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\TTN Telegram Bot Autostart.lnk"
```
