# JokerSeed

> **Disclaimer / Avertissement**
>
> 🇫🇷 Cet outil est destiné **uniquement** à rétablir un ratio proche de 1 sur un tracker privé lorsque vous n'avez pas eu la possibilité de seeder normalement (connexion limitée, fichier supprimé, etc.). N'en abusez pas — respectez les règles de votre tracker.
>
> 🇬🇧 This tool is intended **only** to restore a ratio close to 1 on a private tracker when you were genuinely unable to seed normally (limited connection, deleted file, etc.). Do not abuse it — respect your tracker's rules.

---

## 🇫🇷 Français

Application web auto-hébergée qui simule du seeding BitTorrent en envoyant des requêtes announce réalistes aux trackers HTTP(S). Utile pour maintenir son ratio sans garder les fichiers sur disque.

### Fonctionnalités

- Upload de fichiers `.torrent` via l'interface web ou glisser-déposer
- Simulation de plusieurs clients (qBittorrent, uTorrent, Deluge, Transmission, rTorrent)
- Vitesse d'upload simulée avec dérive aléatoire et périodes d'inactivité
- Plafond de ratio configurable pour éviter des stats suspectes
- Pause / reprise par torrent
- Envoi des événements `started` / `stopped` au tracker
- Support proxy HTTP optionnel
- Persistance des sessions entre les redémarrages
- Historique des torrents retirés
- Prêt pour Docker

### Démarrage rapide

**Avec Docker Compose (recommandé) :**

```bash
docker compose up -d
```

L'app est accessible sur `http://localhost:5080`.  
Les données (config + sessions + historique) sont stockées dans `./data/`.

**Sans Docker :**

```bash
pip install -r requirements.txt
python app.py
```

### Configuration

Tous les réglages sont disponibles dans l'interface (icône ⚙) :

| Paramètre | Défaut | Description |
|---|---|---|
| Vitesse min | 8 000 KB/s | Borne basse de la vitesse simulée |
| Vitesse max | 18 000 KB/s | Borne haute de la vitesse simulée |
| Seeds simultanés | 5 | Nombre de torrents actifs en même temps |
| Port annoncé | 49152 | Port déclaré aux trackers |
| Jitter | 120 s | Délai aléatoire avant chaque announce |
| Client | qBittorrent 4.3.9 | Peer-ID + User-Agent envoyés |
| Proxy | *(vide)* | URL proxy HTTP |
| Plafond de ratio | *(désactivé)* | Réduit l'upload à ~0 au-delà de ce ratio |

---

## 🇬🇧 English

Self-hosted web app that simulates BitTorrent seeding by sending realistic announce requests to HTTP(S) trackers. Useful for maintaining ratio without keeping files on disk.

### Features

- Upload `.torrent` files via the web UI or drag & drop
- Simulates multiple torrent clients (qBittorrent, uTorrent, Deluge, Transmission, rTorrent)
- Realistic upload speed simulation with random drift and idle periods
- Configurable ratio cap to avoid suspicious stats
- Pause / resume individual torrents
- Sends proper `started` / `stopped` announce events
- Optional HTTP proxy support
- Persists state across restarts
- Seeding history log
- Docker-ready

### Quick start

**With Docker Compose (recommended):**

```bash
docker compose up -d
```

Available at `http://localhost:5080`.  
Data (config + sessions + history) is stored in `./data/`.

**Without Docker:**

```bash
pip install -r requirements.txt
python app.py
```

### Configuration

All settings are available in the web UI (⚙ icon):

| Setting | Default | Description |
|---|---|---|
| Min speed | 8 000 KB/s | Lower bound of simulated upload speed |
| Max speed | 18 000 KB/s | Upper bound of simulated upload speed |
| Simultaneous seeds | 5 | Max torrents announcing at the same time |
| Announced port | 49152 | Port declared to trackers |
| Jitter | 120 s | Max random delay before each announce |
| Client | qBittorrent 4.3.9 | Peer-ID prefix + User-Agent sent |
| Proxy | *(empty)* | HTTP proxy URL |
| Ratio cap | *(off)* | Drop speed to ~0 once ratio exceeds this value |

### API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/torrents` | List active torrents |
| `POST` | `/api/torrents` | Add a torrent (multipart `file`) |
| `DELETE` | `/api/torrents/<id>` | Remove a torrent |
| `POST` | `/api/torrents/<id>/pause` | Pause |
| `POST` | `/api/torrents/<id>/resume` | Resume |
| `GET` | `/api/config` | Get config |
| `PUT` | `/api/config` | Update config |
| `GET` | `/api/stats` | Global stats |
| `GET` | `/api/history` | Seeding history |
| `DELETE` | `/api/history` | Clear history |
| `GET` | `/healthz` | Health check |

---

## License

MIT
