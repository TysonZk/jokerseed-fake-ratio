# JokerSeed

A self-hosted web app that simulates BitTorrent seeding by sending realistic announce requests to HTTP(S) trackers. Useful for maintaining ratio on private trackers without keeping files on disk.

## Features

- Upload `.torrent` files via the web UI or drag & drop
- Simulates multiple torrent clients (qBittorrent, uTorrent, Deluge, Transmission, rTorrent)
- Realistic upload speed simulation with random drift and idle periods
- Configurable ratio cap to avoid suspicious stats
- Pause / resume individual torrents
- Sends proper `started` / `stopped` announce events
- Optional HTTP proxy support
- Persists state across restarts
- Docker-ready with a two-stage build

## Stack

- **Backend**: Python 3.11, Flask, Gunicorn
- **Frontend**: Vanilla JS + CSS (single HTML file, no build step)
- **Deployment**: Docker / Docker Compose

## Quick start

### With Docker Compose (recommended)

```bash
docker compose up -d
```

The app will be available at `http://localhost:5082`.

Data (config + sessions) is stored in `./data/` on the host.

### Without Docker

```bash
pip install -r requirements.txt
python app.py
```

## Configuration

All settings are available in the web UI (gear icon):

| Setting | Default | Description |
|---|---|---|
| Min speed | 8 000 KB/s | Lower bound of the simulated upload speed |
| Max speed | 18 000 KB/s | Upper bound of the simulated upload speed |
| Simultaneous seeds | 5 | Max torrents announcing at the same time |
| Announced port | 49152 | Port declared to trackers |
| Jitter | 120 s | Max random delay before each announce (avoids robotic patterns) |
| Client | qBittorrent 4.3.9 | Peer-ID prefix + User-Agent sent to trackers |
| Proxy | *(empty)* | HTTP proxy URL (leave blank for direct / WireGuard) |
| Ratio cap | *(off)* | Drop speed to ~0 once ratio exceeds this value |

Settings are saved to `data/config.json`.

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/torrents` | List all torrents |
| `POST` | `/api/torrents` | Add a torrent (multipart `file`) |
| `DELETE` | `/api/torrents/<id>` | Remove a torrent (sends `stopped`) |
| `POST` | `/api/torrents/<id>/pause` | Pause (sends `stopped`) |
| `POST` | `/api/torrents/<id>/resume` | Resume |
| `GET` | `/api/config` | Get config |
| `PUT` | `/api/config` | Update config (JSON body) |
| `GET` | `/api/stats` | Global stats (speed, uploaded, counts) |
| `GET` | `/healthz` | Health check |

## License

MIT
