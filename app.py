import os, hashlib, random, time, threading, uuid, json
import urllib.parse, urllib.request, urllib.error, ssl
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='static')

DATA_DIR       = os.environ.get('DATA_DIR', 'data')
SESSIONS_FILE  = os.path.join(DATA_DIR, 'sessions.json')
CONFIG_FILE    = os.path.join(DATA_DIR, 'config.json')
HISTORY_FILE   = os.path.join(DATA_DIR, 'history.json')
INDEXERS_FILE  = os.path.join(DATA_DIR, 'indexers.json')

def _qb(prefix, ver):
    return {
        'prefix': prefix, 'ua': f'qBittorrent/{ver}',
        'extra_params': {'corrupt': 0, 'no_peer_id': 1, 'supportcrypto': 1},
        'numwant_start': 200, 'numwant': 0,
        'headers': {'Accept-Encoding': 'gzip', 'Connection': 'close'},
    }

CLIENTS = {
    'qbittorrent-5.1.3': _qb(b'-qB5130-', '5.1.3'),
    'qbittorrent-5.0.5': _qb(b'-qB5050-', '5.0.5'),
    'qbittorrent-4.6.6': _qb(b'-qB4660-', '4.6.6'),
    'qbittorrent-4.5.5': _qb(b'-qB4550-', '4.5.5'),
    'qbittorrent-4.3.9': _qb(b'-qB4390-', '4.3.9'),
    'qbittorrent-4.3.2': _qb(b'-qB4320-', '4.3.2'),
    'utorrent-3.5.5': {
        'prefix': b'-UT3550-', 'ua': 'uTorrent/3550',
        'extra_params': {'corrupt': 0, 'no_peer_id': 1, 'supportcrypto': 1, 'redundant': 0},
        'numwant_start': 200, 'numwant': 0,
        'headers': {'Accept-Encoding': 'gzip', 'Connection': 'close'},
    },
    'utorrent-3.5.3': {
        'prefix': b'-UT3530-', 'ua': 'uTorrent/3530',
        'extra_params': {'corrupt': 0, 'no_peer_id': 1, 'supportcrypto': 1, 'redundant': 0},
        'numwant_start': 200, 'numwant': 0,
        'headers': {'Accept-Encoding': 'gzip', 'Connection': 'close'},
    },
    'deluge-2.1.1': {
        'prefix': b'-DE2110-', 'ua': 'Deluge/2.1.1 libtorrent/1.2.14',
        'extra_params': {'corrupt': 0, 'no_peer_id': 1, 'supportcrypto': 1},
        'numwant_start': 200, 'numwant': 0,
        'headers': {'Accept-Encoding': 'gzip', 'Connection': 'close'},
    },
    'deluge-2.0.3': {
        'prefix': b'-DE2030-', 'ua': 'Deluge/2.0.3 libtorrent/1.1.14',
        'extra_params': {'corrupt': 0, 'no_peer_id': 1, 'supportcrypto': 1},
        'numwant_start': 200, 'numwant': 0,
        'headers': {'Accept-Encoding': 'gzip', 'Connection': 'close'},
    },
    'transmission-3.00': {
        'prefix': b'-TR3000-', 'ua': 'Transmission/3.00',
        'extra_params': {},
        'numwant_start': 80, 'numwant': 80,
        'headers': {'Accept-Encoding': 'deflate, gzip;q=1.0, *;q=0.5'},
    },
    'transmission-2.94': {
        'prefix': b'-TR2940-', 'ua': 'Transmission/2.94',
        'extra_params': {},
        'numwant_start': 80, 'numwant': 80,
        'headers': {'Accept-Encoding': 'deflate, gzip;q=1.0, *;q=0.5'},
    },
    'rtorrent-0.9.8': {
        'prefix': b'-lt0D80-', 'ua': 'rtorrent/0.9.8',
        'extra_params': {'corrupt': 0, 'no_peer_id': 1, 'supportcrypto': 1},
        'numwant_start': 100, 'numwant': 100,
        'headers': {'Accept-Encoding': 'gzip', 'Connection': 'close'},
    },
}

def bdecode(data: bytes):
    def _d(pos):
        tok = data[pos:pos+1]
        if tok == b'd':
            r, pos2 = {}, pos + 1
            while data[pos2:pos2+1] != b'e':
                k, pos2 = _d(pos2)
                v, pos2 = _d(pos2)
                r[k] = v
            return r, pos2 + 1
        if tok == b'l':
            r, pos2 = [], pos + 1
            while data[pos2:pos2+1] != b'e':
                i, pos2 = _d(pos2)
                r.append(i)
            return r, pos2 + 1
        if tok == b'i':
            e = data.index(b'e', pos + 1)
            return int(data[pos+1:e]), e + 1
        c = data.index(b':', pos)
        n = int(data[pos:c])
        return data[c+1:c+1+n], c + 1 + n
    return _d(0)[0]

def bencode(obj) -> bytes:
    if isinstance(obj, bytes): return str(len(obj)).encode() + b':' + obj
    if isinstance(obj, str):   return bencode(obj.encode())
    if isinstance(obj, int):   return b'i' + str(obj).encode() + b'e'
    if isinstance(obj, list):  return b'l' + b''.join(map(bencode, obj)) + b'e'
    if isinstance(obj, dict):
        s = sorted(obj.items(), key=lambda x: x[0] if isinstance(x[0], bytes) else x[0].encode())
        return b'd' + b''.join(bencode(k) + bencode(v) for k, v in s) + b'e'

def parse_torrent(raw: bytes) -> dict:
    d    = bdecode(raw)
    info = d[b'info']
    ih   = hashlib.sha1(bencode(info)).digest()
    name = info.get(b'name', b'Unknown').decode('utf-8', errors='replace')
    size = (info[b'length'] if b'length' in info
            else sum(f[b'length'] for f in info.get(b'files', [])))
    urls = []
    if b'announce' in d:
        urls.append(d[b'announce'].decode('utf-8', errors='replace'))
    for tier in d.get(b'announce-list', []):
        for u in tier:
            dec = u.decode('utf-8', errors='replace')
            if dec not in urls:
                urls.append(dec)
    urls = [u for u in urls if u.startswith('http')]
    if not urls:
        raise ValueError('Aucune URL announce HTTP/HTTPS trouvée')
    return {'info_hash': ih, 'name': name, 'size': size, 'announce_url': urls[0]}

def gen_peer_id(client_key: str) -> bytes:
    prefix = CLIENTS.get(client_key, CLIENTS['qbittorrent-4.3.9'])['prefix']
    pool   = b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    return prefix + bytes(random.choice(pool) for _ in range(12))

def gen_key() -> str:
    return '%08X' % random.randint(0, 0xFFFFFFFF)

def _default_config() -> dict:
    return {
        'min_rate':          8000,
        'max_rate':          18000,
        'simultaneous':      5,
        'client':            'qbittorrent-4.3.9',
        'port':              49152,
        'jitter':            120,
        'proxy':             '',
        'max_ratio':         5.0,
        'lifetime_uploaded': 0,
    }

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return {**_default_config(), **json.load(f)}
    return _default_config()

def save_config(cfg: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

def load_sessions() -> dict:
    if not os.path.exists(SESSIONS_FILE):
        return {}
    with open(SESSIONS_FILE) as f:
        rows = json.load(f)
    out = {}
    for r in rows:
        r['info_hash'] = bytes.fromhex(r.pop('info_hash_hex'))
        r['peer_id']   = bytes.fromhex(r.pop('peer_id_hex'))
        r.setdefault('last_announce', 0)
        r.setdefault('key', gen_key())
        r.setdefault('trackerid', '')
        r.setdefault('ratio_baseline', r.get('uploaded', 0))
        r.setdefault('added_at', 0)
        if r.get('paused'):
            r['status'] = 'paused'
        elif r.get('status') == 'seeding':
            r['status'] = 'seeding'
        else:
            r['status'] = 'waiting'
        r['speed'] = 0.0
        r['error'] = None
        out[r['id']] = r
    return out

def save_sessions(sess: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    rows = []
    for s in sess.values():
        r = {k: v for k, v in s.items() if k not in ('info_hash', 'peer_id') and not k.startswith('_')}
        r['info_hash_hex'] = s['info_hash'].hex()
        r['peer_id_hex']   = s['peer_id'].hex()
        rows.append(r)
    with open(SESSIONS_FILE, 'w') as f:
        json.dump(rows, f, indent=2)

def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE) as f:
        return json.load(f)

def save_history(hist: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HISTORY_FILE, 'w') as f:
        json.dump(hist, f, indent=2)

def load_indexers() -> dict:
    if not os.path.exists(INDEXERS_FILE):
        return {}
    with open(INDEXERS_FILE) as f:
        return json.load(f)

def save_indexers(idx: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(INDEXERS_FILE, 'w') as f:
        json.dump(idx, f, indent=2)

config   = load_config()
sessions = load_sessions()
history  = load_history()
indexers = load_indexers()

# One-time migration: seed lifetime_uploaded from existing history
if config.get('lifetime_uploaded', 0) == 0 and history:
    config['lifetime_uploaded'] = sum(h.get('uploaded', 0) for h in history)
    save_config(config)
lock     = threading.RLock()
executor = ThreadPoolExecutor(max_workers=20)
ssl_ctx  = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode    = ssl.CERT_NONE

def public(s: dict) -> dict:
    return {k: v for k, v in s.items() if k not in ('info_hash', 'peer_id')}

def announce_one(sid: str):
    with lock:
        s = sessions.get(sid)
        if not s or s.get('paused'):
            return
        is_new = s['uploaded'] == 0 and s['last_announce'] == 0
        event  = 'started' if is_new else ''

        client = CLIENTS.get(config['client'], CLIENTS['qbittorrent-4.3.9'])
        nw = client.get('numwant_start', 200) if event == 'started' else client.get('numwant', 0)
        params = {
            'port':       config['port'],
            'uploaded':   s['uploaded'],
            'downloaded': s['size'],
            'left':       0,
            'key':        s.get('key', gen_key()),
            'numwant':    nw,
            'compact':    1,
        }
        params.update(client.get('extra_params', {}))
        if event:
            params['event'] = event
        if s.get('trackerid'):
            params['trackerid'] = s['trackerid']
        q   = urllib.parse.urlencode(params)
        q  += '&info_hash=' + urllib.parse.quote(s['info_hash'], safe='')
        q  += '&peer_id='   + urllib.parse.quote(s['peer_id'],   safe='')
        sep = '&' if '?' in s['announce_url'] else '?'
        url = s['announce_url'] + sep + q
        hdrs = {'User-Agent': client['ua']}
        hdrs.update(client.get('headers', {}))
        proxy = config.get('proxy', '').strip()

    jitter = config.get('jitter', 0)
    if jitter > 0 and not is_new:
        time.sleep(random.uniform(0, jitter))

    try:
        if proxy:
            handler = urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
            opener  = urllib.request.build_opener(handler)
        else:
            opener  = urllib.request.build_opener()

        req = urllib.request.Request(url, headers=hdrs)
        res = opener.open(req, timeout=20)
        d   = bdecode(res.read())

        with lock:
            s = sessions.get(sid)
            if not s:
                return
            s['interval']      = int(d.get(b'interval', 1800))
            s['seeders']       = int(d.get(b'complete', 0))
            s['leechers']      = int(d.get(b'incomplete', 0))
            s['last_announce'] = time.time()
            s['status']        = 'seeding'
            s['error']         = None
            if b'tracker id' in d:
                s['trackerid'] = d[b'tracker id'].decode('utf-8', errors='replace')
        save_sessions(sessions)

    except Exception as e:
        with lock:
            s = sessions.get(sid)
            if s:
                s['status']        = 'error'
                s['error']         = str(e)
                s['speed']         = 0.0
                s['last_announce'] = time.time()

def _send_stopped(snap: dict):
    if snap.get('last_announce', 0) == 0:
        return
    client = CLIENTS.get(config['client'], CLIENTS['qbittorrent-4.3.9'])
    params = {
        'port':       config['port'],
        'uploaded':   snap['uploaded'],
        'downloaded': snap['size'],
        'left':       0,
        'key':        snap.get('key', ''),
        'event':      'stopped',
        'numwant':    0,
        'compact':    1,
    }
    params.update(client.get('extra_params', {}))
    if snap.get('trackerid'):
        params['trackerid'] = snap['trackerid']
    q   = urllib.parse.urlencode(params)
    q  += '&info_hash=' + urllib.parse.quote(snap['info_hash'], safe='')
    q  += '&peer_id='   + urllib.parse.quote(snap['peer_id'],   safe='')
    sep = '&' if '?' in snap['announce_url'] else '?'
    url = snap['announce_url'] + sep + q
    hdrs = {'User-Agent': client['ua']}
    hdrs.update(client.get('headers', {}))
    proxy = config.get('proxy', '').strip()
    try:
        if proxy:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
        else:
            opener = urllib.request.build_opener()
        opener.open(urllib.request.Request(url, headers=hdrs), timeout=10)
    except Exception:
        pass

def announcer_loop():
    while True:
        try:
            time.sleep(5)
            to_announce = []
            with lock:
                now  = time.time()
                pool = sorted(
                    [s for s in sessions.values()
                     if s['status'] in ('seeding', 'waiting') and not s.get('paused')],
                    key=lambda s: s['last_announce']
                )[:config['simultaneous']]
                for s in pool:
                    due = s['last_announce'] == 0 or (now - s['last_announce'] >= s['interval'] - 30)
                    if due:
                        to_announce.append(s['id'])
            for sid in to_announce:
                executor.submit(announce_one, sid)
        except Exception:
            pass

def stats_updater_loop():
    interval  = 2
    last_save = 0
    while True:
        try:
            time.sleep(interval)
            with lock:
                mn, mx    = config['min_rate'], config['max_rate']
                max_ratio = config.get('max_ratio', 5.0)
                now       = time.time()
                for s in list(sessions.values()):
                    if s['status'] != 'seeding' or s.get('paused'):
                        continue

                    net   = s['uploaded'] - s.get('ratio_baseline', 0)
                    ratio = net / s['size'] if s['size'] > 0 else 0
                    if max_ratio > 0 and ratio >= max_ratio:
                        spd = round(random.uniform(0, 30), 1)
                        s['uploaded'] += int(spd * 1024 * interval)
                        s['speed']     = spd
                        continue

                    if now < s.get('_idle_until', 0):
                        spd = round(random.uniform(0, 30), 1)
                        s['uploaded'] += int(spd * 1024 * interval)
                        s['speed']     = spd
                        continue

                    if random.random() < 0.001:
                        s['_idle_until'] = now + random.uniform(300, 1800)
                        spd = round(random.uniform(0, 30), 1)
                        s['uploaded'] += int(spd * 1024 * interval)
                        s['speed']     = spd
                        continue

                    cur = s['speed'] if mn <= s['speed'] <= mx else random.uniform(mn, mx)
                    new = cur + cur * random.uniform(-0.08, 0.08)
                    new = max(mn, min(mx, new))
                    s['uploaded'] += int(new * 1024 * interval)
                    s['speed']     = round(new, 1)

                if now - last_save >= 30:
                    save_sessions(sessions)
                    last_save = now
        except Exception:
            pass

threading.Thread(target=announcer_loop,     daemon=True, name='announcer').start()
threading.Thread(target=stats_updater_loop, daemon=True, name='stats-updater').start()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')

@app.route('/api/clients', methods=['GET'])
def list_clients():
    return jsonify(list(CLIENTS.keys()))

@app.route('/api/torrents', methods=['GET'])
def list_torrents():
    with lock:
        return jsonify([public(s) for s in sessions.values()])

@app.route('/api/torrents', methods=['POST'])
def add_torrent():
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'Fichier manquant'}), 400
    try:
        info = parse_torrent(f.read())
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    sid = str(uuid.uuid4())
    s   = {
        'id': sid, 'name': info['name'], 'size': info['size'],
        'info_hash': info['info_hash'],
        'peer_id':   gen_peer_id(config['client']),
        'key':       gen_key(),
        'trackerid': '',
        'ratio_baseline': 0,
        'announce_url': info['announce_url'],
        'uploaded': 0, 'speed': 0.0, 'seeders': 0, 'leechers': 0,
        'status': 'waiting', 'paused': False,
        'error': None, 'interval': 1800, 'last_announce': 0,
        'added_at': time.time(),
    }
    with lock:
        sessions[sid] = s
    save_sessions(sessions)
    return jsonify(public(s)), 201

@app.route('/api/torrents/<sid>', methods=['DELETE'])
def del_torrent(sid):
    with lock:
        if sid not in sessions:
            return jsonify({'error': 'Introuvable'}), 404
        snap = dict(sessions[sid])
        del sessions[sid]
        history.append({
            'id':          snap['id'],
            'name':        snap['name'],
            'size':        snap['size'],
            'uploaded':    snap['uploaded'],
            'ratio':       round(snap['uploaded'] / snap['size'], 2) if snap['size'] > 0 else 0,
            'added_at':    snap.get('added_at', 0),
            'removed_at':  time.time(),
            'announce_url': snap['announce_url'],
        })
        config['lifetime_uploaded'] = config.get('lifetime_uploaded', 0) + snap['uploaded']
    save_sessions(sessions)
    save_history(history)
    save_config(config)
    executor.submit(_send_stopped, snap)
    return '', 204

@app.route('/api/torrents/<sid>/pause', methods=['POST'])
def pause_torrent(sid):
    with lock:
        s = sessions.get(sid)
        if not s:
            return jsonify({'error': 'Introuvable'}), 404
        snap = dict(s)
        s['paused'] = True
        s['status'] = 'paused'
        s['speed']  = 0.0
    save_sessions(sessions)
    executor.submit(_send_stopped, snap)
    return jsonify(public(s))

@app.route('/api/torrents/<sid>/resume', methods=['POST'])
def resume_torrent(sid):
    with lock:
        s = sessions.get(sid)
        if not s:
            return jsonify({'error': 'Introuvable'}), 404
        s['paused'] = False
        s['status'] = 'waiting'
    save_sessions(sessions)
    return jsonify(public(s))

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(config)

@app.route('/api/config', methods=['PUT'])
def put_config():
    d = request.get_json(force=True) or {}
    with lock:
        for k, cast in [('min_rate', int), ('max_rate', int), ('simultaneous', int),
                        ('port', int), ('jitter', int), ('max_ratio', float)]:
            if k in d:
                config[k] = cast(d[k])
        for k in ('client', 'proxy'):
            if k in d:
                config[k] = str(d[k])
    save_config(config)
    return jsonify(config)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    with lock:
        spd      = sum(s['speed']    for s in sessions.values() if s['status'] == 'seeding')
        up       = sum(s['uploaded'] for s in sessions.values())
        act      = sum(1 for s in sessions.values() if s['status'] == 'seeding')
        lifetime = config.get('lifetime_uploaded', 0) + up
    return jsonify({'speed': round(spd, 1), 'uploaded': up,
                    'active': act, 'total': len(sessions),
                    'lifetime_uploaded': lifetime})

@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify(list(reversed(history)))

@app.route('/api/history', methods=['DELETE'])
def clear_history():
    global history
    with lock:
        history.clear()
    save_history(history)
    return '', 204

@app.route('/api/indexers', methods=['GET'])
def list_indexers():
    return jsonify([{k: v for k, v in i.items() if k != 'api_key'} | {'api_key': '***' if i.get('api_key') else ''} for i in indexers.values()])

@app.route('/api/indexers', methods=['POST'])
def add_indexer():
    d   = request.get_json(force=True) or {}
    iid = str(uuid.uuid4())
    idx = {
        'id':           iid,
        'name':         str(d.get('name', '')).strip(),
        'url':          str(d.get('url', '')).rstrip('/'),
        'api_key':      str(d.get('api_key', '')).strip(),
        'type':         str(d.get('type', 'unit3d')),
        'cookie':       str(d.get('cookie', '')).strip(),
        'announce_url': str(d.get('announce_url', '')).strip(),
    }
    if not idx['name'] or not idx['url'] or not idx['api_key']:
        return jsonify({'error': 'Champs manquants'}), 400
    indexers[iid] = idx
    save_indexers(indexers)
    return jsonify({k: v for k, v in idx.items() if k != 'api_key'} | {'api_key': '***'}), 201

@app.route('/api/indexers/<iid>', methods=['DELETE'])
def del_indexer(iid):
    if iid not in indexers:
        return jsonify({'error': 'Introuvable'}), 404
    del indexers[iid]
    save_indexers(indexers)
    return '', 204

def _tracker_request(url, headers=None):
    h = {'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        res = urllib.request.urlopen(req, context=ssl_ctx, timeout=15)
        return json.loads(res.read()), None
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
            msg  = body.get('message') or body.get('error') or str(e)
        except Exception:
            msg = f'HTTP {e.code}: {e.reason}'
        return None, msg
    except Exception as e:
        return None, str(e)

@app.route('/api/indexers/<iid>/search', methods=['GET'])
def search_indexer(iid):
    idx = indexers.get(iid)
    if not idx:
        return jsonify({'error': 'Introuvable'}), 404

    if idx.get('type') == 'prowlarr':
        url = (f"{idx['url']}/api/v1/search"
               f"?query=&indexerIds=-2&type=search&limit=100&offset=0")
        data, err = _tracker_request(url, headers={'X-Api-Key': idx['api_key']})
        if err:
            return jsonify({'error': err}), 502
        results = []
        for t in (data if isinstance(data, list) else []):
            dl = t.get('downloadUrl', '')
            if not dl:
                continue
            results.append({
                'name':         t.get('title', ''),
                'size':         t.get('size', 0),
                'seeders':      t.get('seeders', 0),
                'leechers':     t.get('leechers', 0),
                'download_url': dl,
            })
        results.sort(key=lambda x: x['leechers'], reverse=True)
        return jsonify(results[:50])

    query = request.args.get('q', '').strip()
    all_results = []
    page = 1
    max_pages = 1 if query else 2
    while page <= max_pages:
        url = (f"{idx['url']}/api/torrents"
               f"?api_token={idx['api_key']}"
               f"&perPage=50&page={page}&sortField=seeders&sortDirection=desc")
        if query:
            url += f"&name={urllib.parse.quote(query)}"
        extra = {}
        if idx.get('cookie'):
            extra['Cookie'] = idx['cookie']
        data, err = _tracker_request(url, headers=extra)
        if err:
            if not all_results:
                return jsonify({'error': err}), 502
            break
        batch = data.get('data') or []
        if not batch:
            break
        for t in batch:
            attr      = t.get('attributes') or t
            tid       = t.get('id')
            info_hash = (t.get('attributes') or {}).get('infoHash') or t.get('infoHash') or attr.get('info_hash', '')
            all_results.append({
                'name':         attr.get('name', ''),
                'size':         attr.get('size', 0),
                'seeders':      int(attr.get('seeders', 0)),
                'leechers':     int(attr.get('leechers', 0)),
                'info_hash':    info_hash,
                'download_url': f"{idx['url']}/api/torrents/{tid}/download?api_token={idx['api_key']}",
            })
        if len(batch) < 50:
            break
        page += 1
    all_results.sort(key=lambda x: x['seeders'] + x['leechers'], reverse=True)
    return jsonify(all_results[:100])

@app.route('/api/indexers/<iid>/user', methods=['GET'])
def indexer_user(iid):
    idx = indexers.get(iid)
    if not idx:
        return jsonify({'error': 'Introuvable'}), 404
    candidates = [
        (f"{idx['url']}/api/auth/me",   {'Cookie': idx['cookie']} if idx.get('cookie') else {}),
        (f"{idx['url']}/api/user?api_token={idx['api_key']}", {'Cookie': idx['cookie']} if idx.get('cookie') else {}),
    ]
    for url, headers in candidates:
        data, err = _tracker_request(url, headers=headers)
        if err:
            continue
        u = data.get('user') or data.get('data', {}).get('attributes') or data.get('attributes') or data
        upload   = u.get('uploaded',   u.get('upload',   0)) or 0
        download = u.get('downloaded', u.get('download', 0)) or 0
        ratio    = u.get('ratio') or (round(upload / download, 3) if download else None)
        if upload or download:
            return jsonify({'upload': upload, 'download': download, 'ratio': ratio})
    return jsonify({'error': 'Aucun endpoint utilisateur disponible'}), 502

@app.route('/api/indexers/<iid>/import', methods=['POST'])
def import_torrent(iid):
    idx = indexers.get(iid)
    if not idx:
        return jsonify({'error': 'Introuvable'}), 404
    d = request.get_json(force=True) or {}

    info_hash_hex = d.get('info_hash', '').strip()
    if info_hash_hex and idx.get('announce_url'):
        try:
            info = {
                'info_hash':    bytes.fromhex(info_hash_hex),
                'name':         d.get('name', 'Unknown'),
                'size':         int(d.get('size', 0)),
                'announce_url': idx['announce_url'],
            }
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    else:
        url = d.get('download_url', '').strip()
        if not url:
            return jsonify({'error': 'announce_url manquant dans l\'indexeur ou download_url absent'}), 400
        extra_headers = {}
        if idx.get('type') == 'prowlarr':
            extra_headers['X-Api-Key'] = idx['api_key']
        elif idx.get('cookie'):
            extra_headers['Cookie'] = idx['cookie']
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', **extra_headers})
            res = urllib.request.urlopen(req, context=ssl_ctx, timeout=15)
            raw = res.read()
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read())
                msg  = body.get('message') or body.get('error') or str(e)
            except Exception:
                msg = f'HTTP {e.code}: {e.reason}'
            return jsonify({'error': msg}), 502
        except Exception as e:
            return jsonify({'error': str(e)}), 502
        try:
            info = parse_torrent(raw)
        except Exception as e:
            return jsonify({'error': str(e)}), 400
    sid = str(uuid.uuid4())
    s   = {
        'id': sid, 'name': info['name'], 'size': info['size'],
        'info_hash': info['info_hash'],
        'peer_id':   gen_peer_id(config['client']),
        'key':       gen_key(),
        'trackerid': '',
        'ratio_baseline': 0,
        'announce_url': info['announce_url'],
        'uploaded': 0, 'speed': 0.0, 'seeders': 0, 'leechers': 0,
        'status': 'waiting', 'paused': False,
        'error': None, 'interval': 1800, 'last_announce': 0,
        'added_at': time.time(),
    }
    with lock:
        sessions[sid] = s
    save_sessions(sessions)
    return jsonify(public(s)), 201

@app.route('/healthz')
def health():
    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5080, debug=False, threaded=True)
