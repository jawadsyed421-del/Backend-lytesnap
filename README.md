# LyteSnap AI — Backend

Backend engine and main process files for the LyteSnap AI desktop application.

## Structure

- `main.js` — Electron main process (Node.js backend orchestrator)
- `preload.js` — IPC bridge between main and renderer processes
- `config.json` — Default application configuration
- `forge.config.js` — Electron Forge build configuration
- `engine/` — Python backend (YouTube reshaping, feed scoring, auth)
- `lib/` — Crypto utilities
- `scripts/` — Build/deploy Node.js scripts
- `shell_scripts/` — Bash scripts for experiments and sessions
- `schedules/` — Schedule state persistence

## Engine (Python)

- `youtube_reshaper.py` — Core YouTube feed reshaping logic
- `score_feed.py` — Feed scoring algorithm
- `score_feed_weighted.py` — Weighted feed scoring variant
- `save_session.py` — Session persistence
- `setup_auth.py` — Google/YouTube OAuth setup
- `requirements.txt` — Python dependencies
