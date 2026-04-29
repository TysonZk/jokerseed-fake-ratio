# CLAUDE.md — JokerSeed

## Contexte projet

Application web auto-hébergée qui simule du seeding BitTorrent en envoyant des requêtes announce HTTP(S) aux trackers privés. Aucun fichier n'est transféré. Utile pour maintenir son ratio sans garder les fichiers sur disque.

- **Repo GitHub** : https://github.com/TysonZk/jokerseed-fake-ratio
- **Port** : 5080
- **Données** : `./data/` (monté en volume Docker sur `/data`)
- **Démarrage** : `docker compose up -d`

---

## Structure des fichiers

```
app.py                  — backend Flask, toute la logique
static/index.html       — frontend single-file (CSS + HTML + JS vanilla)
data/config.json        — configuration persistante
data/sessions.json      — sessions de seeding actives
data/history.json       — historique des torrents retirés
data/indexers.json      — indexeurs privés configurés
Dockerfile              — build 2 stages, Python 3.11-slim, gunicorn
docker-compose.yml      — network_mode: host, volume ./data:/data
requirements.txt        — flask==3.0.3, gunicorn==22.0.0
```

---

## Architecture backend (app.py)

### Globals

```python
config    # dict chargé depuis data/config.json
sessions  # dict {sid: session_dict} — torrents actifs en mémoire
history   # list de dicts — torrents retirés
indexers  # dict {iid: indexer_dict}
lock      # threading.RLock — protège sessions/config/history/indexers
executor  # ThreadPoolExecutor(max_workers=20)
ssl_ctx   # ssl context avec CERT_NONE (trackers avec certs auto-signés)
```

### Threads background

- **`announcer_loop()`** : toutes les 5s, envoie les announces dues aux trackers (basé sur `s['interval']` et `s['last_announce']`)
- **`stats_updater_loop()`** : toutes les 2s, met à jour la vitesse simulée de chaque session + détecte ratio cap + sauvegarde sessions toutes les 30s

### Config par défaut

```python
{
    'min_rate':          8000,    # KB/s
    'max_rate':          18000,   # KB/s
    'simultaneous':      5,       # torrents actifs max
    'client':            'qbittorrent-4.3.9',
    'port':              49152,
    'jitter':            120,     # secondes
    'proxy':             '',
    'max_ratio':         5.0,     # 0 = désactivé
    'lifetime_uploaded': 0,       # accumulateur persistant (bytes)
    'disable_idle':      False,   # désactiver les périodes à ~0 KB/s
    'webhook_url':       '',
}
```

### Session dict

```python
{
    'id':             str (uuid4),
    'name':           str,
    'size':           int (bytes),
    'info_hash':      bytes,
    'peer_id':        bytes,
    'key':            str,
    'trackerid':      str,
    'ratio_baseline': int,        # uploaded au moment de l'ajout (pour calcul net ratio)
    'announce_url':   str,
    'uploaded':       int (bytes),
    'speed':          float (KB/s),
    'seeders':        int,
    'leechers':       int,
    'status':         'waiting'|'seeding'|'error'|'paused',
    'paused':         bool,
    'error':          str|None,
    'interval':       int (secondes),
    'last_announce':  float (timestamp),
    'added_at':       float (timestamp),
    '_idle_until':    float (timestamp, optionnel),
    '_cap_notified':  bool (optionnel),
}
```

### Logique de vitesse (stats_updater_loop)

1. Si `max_ratio > 0` et `net_ratio >= max_ratio` → vitesse ~0–30 KB/s (cap), notif Discord une fois
2. Si `disable_idle=False` et `now < _idle_until` → vitesse ~0–30 KB/s (période idle)
3. Si `disable_idle=False` et `random() < 0.001` → déclenche idle pour 5–30 min
4. Sinon → vitesse dérive de ±8% dans [min_rate, max_rate]

### Clients simulés

10 clients disponibles : qBittorrent 5.1.3/5.0.5/4.6.6/4.5.5/4.3.9/4.3.2, uTorrent 3.5.5/3.5.3, Deluge 2.1.1/2.0.3, Transmission 3.0/2.9.4, rTorrent 0.9.8.
Chacun a un `prefix` bytes pour le Peer-ID et un `ua` (User-Agent).

---

## Routes API complètes

| Méthode | Route | Description |
|---|---|---|
| GET | `/` | Sert `static/index.html` |
| GET | `/favicon.ico` | Favicon |
| GET | `/healthz` | Health check → `ok` |
| GET | `/api/clients` | Liste des clients disponibles |
| GET | `/api/torrents` | Liste des sessions actives (filtrées via `public()`) |
| POST | `/api/torrents` | Ajouter un `.torrent` (multipart `file`) |
| DELETE | `/api/torrents/<sid>` | Retirer torrent + stopped event + notif Discord |
| POST | `/api/torrents/<sid>/pause` | Pause |
| POST | `/api/torrents/<sid>/resume` | Reprise |
| GET | `/api/config` | Config complète |
| PUT | `/api/config` | Mise à jour config |
| POST | `/api/webhook/test` | Envoyer un message test Discord (`{"url":"..."}` optionnel) |
| GET | `/api/stats` | `{speed, uploaded, active, total, lifetime_uploaded}` |
| GET | `/api/history` | Historique (ordre inverse) |
| DELETE | `/api/history` | Effacer historique (lifetime_uploaded non affecté) |
| GET | `/api/indexers` | Liste des indexeurs |
| POST | `/api/indexers` | Ajouter indexeur `{name, url, api_key, type}` |
| DELETE | `/api/indexers/<iid>` | Supprimer indexeur |
| GET | `/api/indexers/<iid>/search?q=` | Recherche top 100 seeders+leechers (q= optionnel) |
| POST | `/api/indexers/<iid>/import` | Importer un torrent `{info_hash, name, size, download_url}` |
| GET | `/api/indexers/<iid>/user` | Ratio/upload/download du compte sur le tracker |

---

## Indexeurs (UNIT3D)

### Structure indexer_dict

```python
{
    'id':           str (uuid4),
    'name':         str,
    'url':          str,          # ex: https://c411.org
    'api_key':      str,
    'type':         'unit3d',
    'cookie':       str,          # cookie de session navigateur (pour trackers restreints)
    'announce_url': str,          # https://tracker.tld/announce/PASSKEY
}
```

`cookie` et `announce_url` ne sont pas exposés dans le formulaire UI — à éditer manuellement dans `data/indexers.json`.

### Endpoint user (ratio tracker)

Essaie `/api/auth/me` (avec cookie) puis `/api/user?api_token=` (fallback).
Pour c411, `/api/auth/me` retourne `user.uploaded`, `user.downloaded`, `user.ratio`.

### Import sans .torrent

Si `info_hash` non vide ET `idx['announce_url']` présent → crée la session directement.
Sinon → télécharge le `.torrent` depuis `download_url` (avec cookie si restreint).

### Recherche

UNIT3D : `GET /api/torrents?api_token=...&perPage=50&page=N&sortField=seeders&sortDirection=desc&name=QUERY`
Récupère 2 pages (sans query) ou 1 page (avec query), trie par `seeders+leechers` desc, retourne top 100.

---

## Discord Webhook

Fonction `_discord(title, description, color, fields, url)` :
- Envoie un embed Discord via webhook
- **Nécessite `User-Agent: JokerSeed/1.0`** (sinon Discord retourne 403)
- Non bloquant : appelé via `executor.submit()`

Événements :
- `🏁 Plafond de ratio atteint` (jaune `0xF0A830`) — une fois par session (`_cap_notified`)
- `🛑 Torrent retiré` (violet `0x9B6DFF`) — avec uploadé, ratio final, durée
- `❌ Erreur tracker` (rouge `0xFF5F57`) — une fois par transition vers état error

---

## lifetime_uploaded

- Stocké dans `config['lifetime_uploaded']`
- Incrémenté dans `del_torrent()` de `snap['uploaded']`
- Migration au démarrage : si = 0 et historique non vide → initialisé depuis la somme de l'historique
- Dans `/api/stats` : `lifetime = config['lifetime_uploaded'] + sum(actives.uploaded)`
- Affiché dans l'en-tête du panneau Historique
- **Ne se remet jamais à zéro** même si l'historique est effacé

---

## Frontend (static/index.html)

Single-file : CSS variables + HTML + JS vanilla, aucune dépendance externe sauf Google Fonts.

### Variables globales JS importantes

```js
let _maxRate = 18000        // pour la barre de progression vitesse
let _maxRatio = 0           // pour l'indicateur de cap
let _currentIndexerId = null
let _searchResults = []     // résultats de recherche courants (évite JSON dans onclick)
```

### Fonctions clés

- `poll()` — toutes les 1500ms : fetch torrents + stats + history en parallèle
- `render(list)` — rendu du tableau des torrents actifs
- `renderHistory(list)` — rendu de l'historique
- `renderIndexers(list)` — rendu des indexeurs + appel `fetchIndexerRatio()` pour chacun
- `fetchIndexerRatio(iid)` — fetch `/api/indexers/<iid>/user` et affiche ratio coloré
- `loadCfg()` — charge la config et remplit le modal
- `saveCfg()` — sauvegarde + test webhook automatique si URL changée
- `testWebhook(url?)` — POST `/api/webhook/test`
- `openSearch(iid, name)` → `_fetchResults(iid, q)` — ouvre modal et charge résultats
- `runSearch()` — déclenche recherche avec le contenu du champ texte
- `importTorrent(iid, _searchResults[i], btn)` — importe via `/api/indexers/<iid>/import`

### Ratio display

```js
const ratio = t.size > 0 ? t.uploaded / t.size : 0  // ratio BRUT pour affichage
const net = t.uploaded - (t.ratio_baseline || 0)
const netRatio = t.size > 0 ? net / t.size : 0       // ratio NET pour plafond
```

### Piège connu : JSON dans onclick

Les données de recherche sont stockées dans `_searchResults[]` et référencées par index dans le HTML (`_searchResults[0]`, etc.) pour éviter le conflit entre guillemets JSON et attributs HTML.

---

## Docker

```dockerfile
# Build 2 stages : builder installe les dépendances, image finale légère
FROM python:3.11-slim
CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:5080", "--timeout", "120", "app:app"]
```

```yaml
# docker-compose.yml
network_mode: host    # accès direct aux trackers locaux/VPN
volumes:
  - ./data:/data      # persistance config/sessions/history/indexers
environment:
  - DATA_DIR=/data
```

Rebuild complet : `docker compose build --no-cache && docker compose up -d`

---

## Données sensibles dans data/indexers.json

Le fichier `data/indexers.json` contient les clés API, cookies de session et URLs announce avec passkey. Ne jamais commiter ce fichier — il est dans `.gitignore`.

---

## Points d'attention

- `save_sessions()` est appelé toutes les 30s dans `stats_updater_loop` (pas seulement à l'arrêt)
- `_send_stopped()` envoie l'event `stopped` au tracker lors du retrait d'un torrent
- `public(s)` filtre `info_hash` et `peer_id` (bytes non sérialisables) des sessions avant de les retourner en JSON
- Les sessions sont sauvegardées avec `info_hash_hex` et `peer_id_hex` (hex strings) puis rechargées en bytes
- `ratio_baseline` = valeur de `uploaded` au moment où le plafond serait activé (actuellement toujours 0 à la création)
- Le `jitter` est appliqué côté `announcer_loop` : un délai aléatoire `[0, jitter]` est ajouté avant chaque announce
