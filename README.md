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

**Simulation de seeding**
- Upload de fichiers `.torrent` via l'interface web ou glisser-déposer
- Simulation de 10 clients différents : qBittorrent (5.1.3 → 4.3.2), uTorrent (3.5.5, 3.5.3), Deluge (2.1.1, 2.0.3), Transmission (3.0, 2.9.4), rTorrent (0.9.8)
- Peer-ID forgé au format exact de chaque client
- User-Agent correspondant au client choisi
- Envoi des événements `started` / `stopped` au tracker
- Gestion de plusieurs torrents actifs en simultané (slots configurables)

**Simulation réaliste**
- Vitesse d'upload avec dérive aléatoire ±8% à chaque tick (toutes les 2 s)
- Périodes d'inactivité aléatoires (5–30 min) simulant des moments sans leechers
- Jitter configurable sur l'intervalle d'announce pour éviter un timing robotique
- Plafond de ratio : la vitesse tombe automatiquement à ~0 KB/s une fois le ratio cible atteint

**Gestion des torrents**
- Pause / reprise individuelle par torrent
- Retrait propre avec envoi de l'événement `stopped` au tracker
- Persistance des sessions toutes les 30 secondes (l'upload survit aux redémarrages)
- Historique complet des torrents retirés (nom, taille, uploadé, ratio, durée)

**Indexeurs privés (UNIT3D)**
- Ajout d'indexeurs privés via API Key + cookie de session
- Affichage du **top 100 torrents** triés par seeders + leechers
- Barre de recherche par mot-clé (séries, films, jeux, anime…)
- Import en un clic : infoHash + URL announce → seed démarre instantanément, sans télécharger le fichier `.torrent`
- Affichage du **ratio réel du compte** sur le tracker directement dans l'interface (upload, download, ratio coloré)

**Interface**
- Dashboard avec stats globales (upload total, ratio moyen, torrents actifs)
- Design sombre responsive (mobile, tablette, desktop)
- Drag & drop de fichiers `.torrent`
- Notifications toast
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

- Un **Peer-ID** forgé au format du client choisi (ex: `-qB5130-XXXXXXXXXXXX`)
- Le **User-Agent** correspondant au client
- Les compteurs `uploaded`, `downloaded`, `left` attendus par le tracker

**Simulation de vitesse réaliste**

Pour éviter des stats robotiques, la vitesse ne monte pas à fond en permanence :

- La vitesse dérive de ±8% à chaque tick (toutes les 2 secondes) pour paraître organique
- Des **périodes d'inactivité** aléatoires simulent des moments où personne ne télécharge chez vous : la vitesse tombe à ~0–30 KB/s pendant 5 à 30 minutes, puis reprend normalement. C'est attendu.
- Un **jitter** configurable ajoute un délai aléatoire avant chaque announce pour ne pas arriver à heure fixe

**Plafond de ratio**

Si activé, dès que le ratio atteint la valeur configurée, la vitesse tombe à ~0 KB/s automatiquement — utile pour ne pas afficher un ratio de 500× qui attirerait l'attention.

**Import via indexeur (sans `.torrent`)**

Quand un indexeur UNIT3D est configuré avec son cookie de session et son URL announce, JokerSeed crée la session directement depuis l'infoHash retourné par l'API — sans jamais télécharger le fichier `.torrent`. Utile pour les trackers en mode restreint où le téléchargement direct est bloqué.

### Configuration

Tous les réglages sont disponibles dans l'interface (icône ⚙) :

| Paramètre | Défaut | Description |
|---|---|---|
| Vitesse min | 8 000 KB/s | Borne basse de la vitesse simulée |
| Vitesse max | 18 000 KB/s | Borne haute de la vitesse simulée |
| Seeds simultanés | 5 | Nombre de torrents actifs en même temps |
| Port annoncé | 49152 | Port déclaré aux trackers |
| Jitter | 120 s | Délai aléatoire max avant chaque announce |
| Client | qBittorrent 5.1.3 | Peer-ID + User-Agent envoyés |
| Proxy | *(vide)* | URL proxy HTTP |
| Plafond de ratio | *(désactivé)* | Réduit l'upload à ~0 au-delà de ce ratio |

### Indexeurs — configuration

Dans le panneau **Indexeurs**, ajoutez un tracker UNIT3D avec :

| Champ | Description |
|---|---|
| Nom | Nom affiché (ex: `c411`) |
| URL | URL de base du tracker (ex: `https://c411.org`) |
| API Key | Token API du tracker |

Pour l'import direct sans `.torrent`, éditez manuellement `data/indexers.json` pour ajouter :
- `"cookie"` : cookie de session du navigateur (pour les trackers en mode restreint)
- `"announce_url"` : URL announce avec passkey (ex: `https://tracker.tld/announce/PASSKEY`)

### API REST

| Méthode | Chemin | Description |
|---|---|---|
| `GET` | `/api/torrents` | Lister les torrents actifs |
| `POST` | `/api/torrents` | Ajouter un torrent (multipart `file`) |
| `DELETE` | `/api/torrents/<id>` | Retirer un torrent |
| `POST` | `/api/torrents/<id>/pause` | Mettre en pause |
| `POST` | `/api/torrents/<id>/resume` | Reprendre |
| `GET` | `/api/config` | Lire la config |
| `PUT` | `/api/config` | Modifier la config |
| `GET` | `/api/stats` | Stats globales |
| `GET` | `/api/history` | Historique |
| `DELETE` | `/api/history` | Effacer l'historique |
| `GET` | `/api/indexers` | Lister les indexeurs |
| `POST` | `/api/indexers` | Ajouter un indexeur |
| `DELETE` | `/api/indexers/<id>` | Supprimer un indexeur |
| `GET` | `/api/indexers/<id>/search?q=` | Rechercher des torrents |
| `POST` | `/api/indexers/<id>/import` | Importer un torrent |
| `GET` | `/api/indexers/<id>/user` | Ratio du compte sur le tracker |
| `GET` | `/healthz` | Health check |

---

## 🇬🇧 English

Self-hosted web app that simulates BitTorrent seeding by sending realistic announce requests to HTTP(S) trackers. Useful for maintaining ratio without keeping files on disk.

### Features

**Seeding simulation**
- Upload `.torrent` files via the web UI or drag & drop
- Simulates 10 different clients: qBittorrent (5.1.3 → 4.3.2), uTorrent (3.5.5, 3.5.3), Deluge (2.1.1, 2.0.3), Transmission (3.0, 2.9.4), rTorrent (0.9.8)
- Peer-ID forged to match the exact format of each client
- Matching User-Agent header per client
- Sends proper `started` / `stopped` announce events
- Configurable number of simultaneous active torrents

**Realistic simulation**
- Upload speed with ±8% random drift every tick (every 2 s)
- Random idle periods (5–30 min) simulating moments with no leechers
- Configurable jitter on announce interval to avoid robotic timing
- Ratio cap: speed automatically drops to ~0 KB/s once target ratio is reached

**Torrent management**
- Pause / resume individual torrents
- Clean removal with `stopped` event sent to tracker
- Session persistence every 30 seconds (uploaded survives restarts)
- Full history of removed torrents (name, size, uploaded, ratio, duration)

**Private indexers (UNIT3D)**
- Add private indexers via API Key + session cookie
- Browse the **top 100 torrents** sorted by seeders + leechers
- Search by keyword (series, movies, games, anime…)
- One-click import: infoHash + announce URL → seeding starts instantly, no `.torrent` download needed
- Displays your **real account ratio** on the tracker directly in the UI (upload, download, color-coded ratio)

**Interface**
- Dashboard with global stats (total uploaded, average ratio, active torrents)
- Responsive dark UI (mobile, tablet, desktop)
- Drag & drop `.torrent` files
- Toast notifications
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

- A forged **Peer-ID** matching the chosen client format (e.g. `-qB5130-XXXXXXXXXXXX`)
- The matching **User-Agent** header
- The `uploaded`, `downloaded`, `left` counters the tracker expects

**Realistic speed simulation**

To avoid robotic stats, the speed doesn't run at full throttle non-stop:

- Speed drifts ±8% every tick (every 2 seconds) to look organic
- Random **idle periods** simulate moments where nobody is downloading from you: speed drops to ~0–30 KB/s for 5 to 30 minutes, then resumes normally. This is expected behavior.
- A configurable **jitter** adds a random delay before each announce so requests don't arrive on a fixed schedule

**Ratio cap**

When enabled, once the ratio reaches the configured value, speed automatically drops to ~0 KB/s — useful to avoid displaying a 500× ratio that would raise suspicion.

**Indexer import (no `.torrent` needed)**

When a UNIT3D indexer is configured with its session cookie and announce URL, JokerSeed creates the session directly from the infoHash returned by the API — without ever downloading the `.torrent` file. This is especially useful for trackers in restricted mode where direct downloads are blocked.

### Configuration

All settings are available in the web UI (⚙ icon):

| Setting | Default | Description |
|---|---|---|
| Min speed | 8 000 KB/s | Lower bound of simulated upload speed |
| Max speed | 18 000 KB/s | Upper bound of simulated upload speed |
| Simultaneous seeds | 5 | Max torrents announcing at the same time |
| Announced port | 49152 | Port declared to trackers |
| Jitter | 120 s | Max random delay before each announce |
| Client | qBittorrent 5.1.3 | Peer-ID prefix + User-Agent sent |
| Proxy | *(empty)* | HTTP proxy URL |
| Ratio cap | *(off)* | Drop speed to ~0 once ratio exceeds this value |

### Indexers — setup

In the **Indexers** panel, add a UNIT3D tracker with:

| Field | Description |
|---|---|
| Name | Display name (e.g. `mytracker`) |
| URL | Base URL of the tracker (e.g. `https://tracker.tld`) |
| API Key | Tracker API token |

For direct import without `.torrent`, manually edit `data/indexers.json` to add:
- `"cookie"` : browser session cookie (for trackers in restricted mode)
- `"announce_url"` : announce URL with passkey (e.g. `https://tracker.tld/announce/PASSKEY`)

### REST API

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
| `GET` | `/api/indexers` | List indexers |
| `POST` | `/api/indexers` | Add an indexer |
| `DELETE` | `/api/indexers/<id>` | Delete an indexer |
| `GET` | `/api/indexers/<id>/search?q=` | Search torrents |
| `POST` | `/api/indexers/<id>/import` | Import a torrent |
| `GET` | `/api/indexers/<id>/user` | Account ratio on tracker |
| `GET` | `/healthz` | Health check |

---

## License

MIT
