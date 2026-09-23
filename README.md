# Bracketer

A small single-elimination bracket website with owner-controlled results, optional public voting, and optional Love Live song links.

## Run

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

Open `http://127.0.0.1:5000`. Data is stored in `instance/bracketer.sqlite3`.

The owner link contains a secret token. Keep it private; anyone with it can control the bracket. The public link and QR code are usable by visitors when the bracket is published. To let people on other devices connect, set `BRACKETER_HOST=0.0.0.0` when starting the server, then open the owner page using the computer's reachable LAN address before sharing its QR code.

The Love Live catalog is a local copy of the [supplied song data](https://github.com/hamproductions/the-sorter/blob/main/data/song-info.json). Names are matched case-insensitively against `name` and `englishName`. Ambiguous names are left unmatched so the owner can supply a YouTube video ID.

Anonymous ballots are limited to one per browser cookie per matchup. Clearing cookies or using another browser can bypass that limit; without voter accounts, it is not a unique-person guarantee.
