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

### Comment ça fonctionne

JokerSeed ne transfère aucun fichier. Il envoie uniquement des requêtes HTTP announce au tracker, exactement comme le ferait un vrai client BitTorrent, avec :

- Un **Peer-ID** forgé au format du client choisi (ex: `-qB4390-XXXXXXXXXXXX`)
- Le **User-Agent** correspondant au client
- Les compteurs `uploaded`, `downloaded`, `left` attendus par le tracker

**Simulation de vitesse réaliste**

Pour éviter des stats robotiques, la vitesse ne monte pas à fond en permanence :

- La vitesse dérive de ±8% à chaque tick (toutes les 2 secondes) pour paraître organique
- Des **périodes d'inactivité** aléatoires simulent des moments où personne ne télécharge chez vous : la vitesse tombe à ~0–30 KB/s pendant 5 à 30 minutes, puis reprend normalement. C'est attendu.
- Un **jitter** configurable ajoute un délai aléatoire avant chaque announce pour ne pas arriver à heure fixe

**Plafond de ratio**

Si activé, dès que le ratio atteint la valeur configurée, la vitesse tombe à ~0 KB/s automatiquement — utile pour ne pas afficher un ratio de 500× qui attirerait l'attention.

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

### How it works

JokerSeed transfers no files. It only sends HTTP announce requests to the tracker, exactly like a real BitTorrent client would, with:

- A forged **Peer-ID** matching the chosen client format (e.g. `-qB4390-XXXXXXXXXXXX`)
- The matching **User-Agent** header
- The `uploaded`, `downloaded`, `left` counters the tracker expects

**Realistic speed simulation**

To avoid robotic stats, the speed doesn't run at full throttle non-stop:

- Speed drifts ±8% every tick (every 2 seconds) to look organic
- Random **idle periods** simulate moments where nobody is downloading from you: speed drops to ~0–30 KB/s for 5 to 30 minutes, then resumes normally. This is expected behavior.
- A configurable **jitter** adds a random delay before each announce so requests don't arrive on a fixed schedule

**Ratio cap**

When enabled, once the ratio reaches the configured value, speed automatically drops to ~0 KB/s — useful to avoid displaying a 500× ratio that would raise suspicion.

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
