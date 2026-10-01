# Bracketer

A small single-elimination bracket website with owner-controlled results, optional public voting, and optional Love Live song links.

Production deployment work is specified in the [WSGI and deployment implementation plan](planning/DEPLOYMENT_PLAN.md), including optional container packaging and acceptance checks for the implementing agent.

The Linux container setup and operator steps are in [the deployment runbook](docs/DEPLOYMENT.md). This setup has not passed the plan's production capacity gate.

## Run

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

Open `http://127.0.0.1:5000` to create a bracket. Data is stored in `instance/bracketer.sqlite3`.

The owner link contains a secret token. Keep it private; anyone with it can control the bracket. The owner page links to the published projector display. When public voting is enabled, that display keeps a QR code on screen for attendees; it opens a separate voting page on their devices. Revealed winners and both entry vote counts appear on the display.

To let attendees connect from other devices, start the server with `$env:BRACKETER_HOST = '0.0.0.0'`, then open the owner page using the computer's reachable LAN address before sharing the projector display. The QR code uses the display page's host address.

The Love Live catalog is a local copy of the [supplied song data](https://github.com/hamproductions/the-sorter/blob/main/data/song-info.json). Names are matched case-insensitively against `name` and `englishName`. Ambiguous names are left unmatched so the owner can supply a YouTube video ID.

Anonymous ballots are limited to one per browser cookie per matchup. Clearing cookies or using another browser can bypass that limit; without voter accounts, it is not a unique-person guarantee.
