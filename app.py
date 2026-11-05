import os
import time
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "multiverso_secret_key_2026")

DATABASE_URL = os.environ.get("DATABASE_URL")
LINK_DESCARGA_BOT = "https://drive.google.com/uc?export=download&id=TU_ID_DE_GOOGLE_DRIVE"
FOLDER_DRIVE_ID = os.environ.get("DRIVE_FOLDER_ID", "1nSqaWKAsEc7s6BYT8xg22MoITXLT7IIK")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

DATA_FILE = "timers_data.json"
USERS_FILE = "users_data.json"
DONACIONES_FILE = "donaciones_data.json"
MAPAS_FILE = "mapas_data.json"
MIEMBROS_FILE = "miembros_data.json"

BOSSES_MANUALES = [
    "Red Dragon", "Yellow Goblin", "Blue Goblin", 
    "Red Goblin", "Santa", "White Wizard", "Skeleton King"
]

# Diccionario maestro de mapeo de nombres conocidos de las capturas de tu Drive
NOMBRES_CONOCIDOS = {
    "265": "Excellent Sphinx Armor",
    "264": "Excellent Legendary Pants",
    "260": "Excellent Black Dragon Pants",
    "258": "Excellent Sphinx Gloves",
    "253": "Excellent Light Plate Pants",
    "252": "Excellent Bronze Helm",
    "250": "Excellent Bill of Balrog",
    "248": "Excellent Legendary Shield",
    "247": "Excellent Sphinx Armor",
    "246": "Excellent Bronze Gloves",
    "244": "Excellent Book of Samut",
    "242": "Excellent Red Winged Gloves",
    "241": "Excellent Pad Armor",
    "240": "Excellent Violent Wind Pants",
    "239": "Excellent Epic Silver Bow",
    "238": "Excellent Guardian Pants",
    "237": "Excellent Aquagold Crossbow",
    "236": "Excellent Sacred Claw",
    "235": "Excellent Ancient Helm",
    "234": "Excellent Bronze Pants",
    "232": "Excellent Brass Gloves",
    "231": "Excellent Buckler",
    "230": "Excellent Sacred Fire Armor",
    "229": "Excellent Skeleton Two-Hand Staff",
    "228": "Excellent Wind Armor",
    "226": "Excellent Legendary Armor",
    "225": "Excellent Dragon Pants",
    "223": "Excellent Legendary Shield",
    "222": "Excellent Epic Kriss",
    "219": "Excellent Dragon Helm",
    "218": "Excellent Bill of Balrog",
    "217": "Excellent Wind Gloves",
    "216": "Excellent Bill of Balrog",
    "215": "Excellent Large Round Shield",
    "213": "Excellent Dragon Armor",
    "212": "Excellent Lighting Sword"
}

def cargar_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                d = json.load(f)
                if d is not None: return d
        except Exception: pass
    return default_val

def guardar_json(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando {filepath}: {e}")

status_timers = cargar_json(DATA_FILE, {"Server 1": {}, "Server 2": {}, "Server 3": {}, "Server 20": {}})
status_mapas = cargar_json(MAPAS_FILE, {"1": {}, "2": {}, "3": {}})
usuarios_db = cargar_json(USERS_FILE, {"pinion": {"password": "pass123", "rol": "admin", "requiere_cambio": False}})
donaciones_db = cargar_json(DONACIONES_FILE, [])
miembros_clan_db = cargar_json(MIEMBROS_FILE, [])

tarjetas_ocultas_global = set()
heartbeats = {}
ultimas_pcs = {}
ultimos_pjs = {}
ultimos_kills_recientes = {}

def get_db():
    if not DATABASE_URL:
        return None
    try:
        db_url = DATABASE_URL
        if "sslmode" not in db_url:
            db_url += "?sslmode=require" if "?" not in db_url else "&sslmode=require"
        return psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=4)
    except Exception:
        return None

def normalizar_campo_json(valor, default_tipo):
    if valor is None: return default_tipo
    if isinstance(valor, (list, dict)): return valor
    if isinstance(valor, str):
        try: return json.loads(valor)
        except Exception: return default_tipo
    return default_tipo

# --- LECTURA EN VIVO DIRECTAMENTE DESDE LA CARPETA DE GOOGLE DRIVE ---
def leer_items_directo_drive():
    archivos = []

    # 1. Intentar por API Key oficial si existe
    if GOOGLE_API_KEY:
        try:
            q = urllib.parse.quote(f"'{FOLDER_DRIVE_ID}' in parents and trashed=false")
            url = f"https://www.googleapis.com/drive/v3/files?q={q}&key={GOOGLE_API_KEY}&fields=files(id,name,mimeType)&pageSize=1000"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for f in data.get('files', []):
                    if 'image' in f.get('mimeType', ''):
                        archivos.append({"id": f['id'], "name": f['name']})
        except Exception as e:
            print(f"Aviso Drive API: {e}")

    # 2. Si no hay API Key o falló, leer la vista pública embebida
    if not archivos:
        try:
            url_folder = f"https://drive.google.com/embeddedfolderview?id={FOLDER_DRIVE_ID}#grid"
            req = urllib.request.Request(url_folder, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                ids = re.findall(r'https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', html)
                vistos = set()
                for fid in ids:
                    if fid not in vistos:
                        vistos.add(fid)
                        archivos.append({"id": fid, "name": f"{fid[:6]}.png"})
        except Exception as e:
            print(f"Aviso lectura web Drive: {e}")

    # Si Drive no responde o demora, asegurar los ítems conocidos
    if not archivos:
        archivos = [
            {"id": "1BC0k90uaW4rHp1dQM1Y-pxLwE1KfnLku", "name": "247.png"},
            {"id": "1Jmjh8YltzfO2xBhBDGX0oYxr-WMdG4xK", "name": "264.png"},
            {"id": "1iHHVi5Fr0KKdjWX1luSpI9CzuPAK5Aq5", "name": "260.png"},
            {"id": "1SD_eAIslC4Le3N1PuIBrF1fFB2V5mIZE", "name": "258.png"},
            {"id": "134KbPtgfHsEJsso7bM7bBWeiC5qt3VY4", "name": "253.png"},
            {"id": "1TuHbtxMsonvbMfdAvR18aO7oYJTiVWxd", "name": "252.png"},
            {"id": "14Ufrcc1tRoI5OD1weZ7Ag1opgm-djCIm", "name": "250.png"},
            {"id": "1uNOlQGiHDxzszBHLYFBqLra-c6Vy2Qe1", "name": "248.png"},
            {"id": "1u0mZvM_JmyY3NABCGCf35dj6rGVqrFHh", "name": "246.png"},
            {"id": "1f5VMBmH8o4CdKIblTkW382mnxkzj7s2U", "name": "244.png"},
            {"id": "1T3RcyL2SCS4_a20q2ymcOwu4FpDdW6Hi", "name": "242.png"},
            {"id": "1Z1YEGk78j_3qZtNUHqFasLqq6_EMKUdW", "name": "241.png"},
            {"id": "1euLQrkH0g0i7L9ugmRk10QRlqgwnmYCY", "name": "240.png"},
            {"id": "1vp4qyg0Idn9OXgijU7RMAuj9NeUGXkDS", "name": "239.png"},
            {"id": "1PFjrFglCCrOxtVLmSqftJQGX7TjuxYXN", "name": "238.png"},
            {"id": "1Q9-7z5UIjQE47WN-iB68S4AItMitA-U-", "name": "237.png"},
            {"id": "1_SlZm5z7Kt_tPnTLDE7cqQmpJvWAl71E", "name": "236.png"},
            {"id": "1IRlyMhgUDoOnaFb1WeINDem_g8w-eW_1", "name": "235.png"},
            {"id": "1iS3vLcZtCi3QULyH9FP12KX3gy3f05in", "name": "234.png"},
            {"id": "14jkj6gYmmDrFzDDxjOYxVzo9x3RE44Xh", "name": "232.png"},
            {"id": "1dKoBcHU0jPDRHl4uTzdZJYBTC_mxyrfn", "name": "231.png"},
            {"id": "19si3IDRhUCfTtsj_PFPnkJrKJ6EGZY7_", "name": "230.png"},
            {"id": "1sTWx5jbjXBertKCRapkICwBoK4g_-4Q5", "name": "229.png"},
            {"id": "1YjKaPoCXFLBcWL7Lz9Goj0lrRarDeTL3", "name": "228.png"},
            {"id": "1Eb2WLe_9yynGaicJ095iPibmXsX8vVKg", "name": "226.png"},
            {"id": "1UMnuuoHNYatk8Cxh_e3dswaJuVdkU8mF", "name": "225.png"},
            {"id": "1wxfC56ZrHQ_QsV-sV_pmKFpQc4z7FEBD", "name": "223.png"},
            {"id": "1_A4LY4mAC3TpekrAV9do_vBitSkHvLtL", "name": "222.png"},
            {"id": "1DH475s9jM4v-_7tZQJ8rqaWjYWEz9Ypr", "name": "219.png"},
            {"id": "19KmlyqOG4dTu1XtpxweZlS15XYaUk0wM", "name": "218.png"},
            {"id": "1JBod02qFAHYOgvqrJLYfeGFbb5lHP1Ub", "name": "217.png"},
            {"id": "1NgioKMuE78VpXFjZh0075HZQyHAtsXe3", "name": "216.png"},
            {"id": "1RSuRbaL6Vkdu7voi5B8CzizCCtBk42TR", "name": "215.png"},
            {"id": "1rA7sasV87YnLlkeiXO4vIR7Ek3yW9q0Q", "name": "213.png"},
            {"id": "1myQ5xRo8IsjT2ykowGABfq476ccUI1Uh", "name": "212.png"}
        ]

    items_resultado = []
    for idx, f in enumerate(archivos):
        nombre_archivo = f['name']
        numero_str = re.sub(r'\D', '', nombre_archivo)
        item_id = int(numero_str) if numero_str else (1000 + idx)

        # Detectar el nombre comercial
        nombre_comercial = NOMBRES_CONOCIDOS.get(numero_str)
        if not nombre_comercial:
            nombre_comercial = re.sub(r'\.[a-zA-Z0-9]+$', '', nombre_archivo).replace('_', ' ')

        # Deducir clases según el tipo de ítem
        nombre_lower = nombre_comercial.lower()
        clases = []
        if any(w in nombre_lower for w in ["dragon", "balrog", "brass", "lighting"]):
            clases.extend(["Dark Knight", "Magic Gladiator"])
        if any(w in nombre_lower for w in ["sphinx", "legendary", "pad", "staff"]):
            clases.extend(["Dark Wizard", "Magic Gladiator"])
        if any(w in nombre_lower for w in ["bow", "crossbow", "wind", "guardian"]):
            clases.extend(["Elf"])
        if any(w in nombre_lower for w in ["light plate", "dark lord"]):
            clases.append("Dark Lord")
        if any(w in nombre_lower for w in ["samut", "red winged", "violent wind", "ancient"]):
            clases.append("Summoner")
        if any(w in nombre_lower for w in ["claw", "sacred fire"]):
            clases.append("Rage Fighter")
        if any(w in nombre_lower for w in ["shield", "kriss", "buckler"]):
            clases.extend(["Dark Knight", "Dark Wizard", "Elf", "Magic Gladiator", "Dark Lord", "Summoner", "Rage Fighter"])
        
        if not clases:
            clases = ["Dark Knight", "Dark Wizard", "Elf", "Magic Gladiator", "Dark Lord", "Summoner", "Rage Fighter"]

        # Opciones deducidas de los datos
        opciones = []
        if any(w in nombre_lower for w in ["shield", "pants", "armor", "helm", "gloves"]):
            opciones.extend(["[Rare] Damage decrease +3%", "[Rare] Reflect damage +3%"])
            if "sphinx" in nombre_lower or "guardian" in nombre_lower or "buckler" in nombre_lower:
                opciones.append("[Legendary] Increases maximum life +4%")
            if "bronze" in nombre_lower or "legendary" in nombre_lower:
                opciones.append("[Rare] Increases maximum SD +3%")
        if any(w in nombre_lower for w in ["bow", "crossbow", "sword", "claw", "staff", "kriss", "balrog"]):
            opciones.extend(["[Legendary] Excellent damage rate +8%", "[Epic] Critical damage rate +10%"])

        items_resultado.append({
            "id": item_id,
            "nombre": nombre_comercial,
            "archivo": nombre_archivo,
            "clases": list(set(clases)),
            "opciones": opciones if opciones else ["[General] Item Excellent"],
            "bonus_excelente": ["Bonus Extra"],
            "drive_id": f['id']
        })

    # Ordenar de mayor a menor por ID
    items_resultado.sort(key=lambda x: x['id'], reverse=True)
    return items_resultado

# --- VISTAS ---
@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)

@app.route('/items')
def vista_items():
    return render_template('items.html')

# --- API DE ITEMS (LECTURA EN VIVO DE DRIVE) ---
@app.route('/api/items', methods=['GET'])
def api_items():
    lista = leer_items_directo_drive()
    return jsonify(lista)

# --- API DE MIEMBROS DEL CLAN ---
@app.route('/api/miembros', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_miembros():
    global miembros_clan_db
    conn = get_db()

    if request.method == 'GET':
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, nombre_pj, raza, items_asignados, notas FROM public.miembros_clan ORDER BY id ASC;")
                    filas = cur.fetchall()
                    if filas:
                        miembros_clan_db = []
                        for r in filas:
                            miembros_clan_db.append({
                                "id": r['id'],
                                "nombre_pj": r['nombre_pj'],
                                "raza": r['raza'],
                                "items_asignados": normalizar_campo_json(r['items_asignados'], []),
                                "notas": r.get('notas', '')
                            })
                        guardar_json(MIEMBROS_FILE, miembros_clan_db)
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify(miembros_clan_db)

    if request.method == 'POST':
        data = request.json or {}
        nombre_pj = data.get('nombre_pj', '').strip()
        raza = data.get('raza', 'Dark Knight').strip()
        items_asignados = data.get('items_asignados', [])
        notas = data.get('notas', '').strip()

        if not nombre_pj:
            if conn: conn.close()
            return jsonify({"error": "Nombre de PJ requerido"}), 400

        nuevo_id = int(time.time() * 1000)
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.miembros_clan (nombre_pj, raza, items_asignados, notas)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (nombre_pj) DO UPDATE 
                        SET raza = EXCLUDED.raza, items_asignados = EXCLUDED.items_asignados, notas = EXCLUDED.notas
                        RETURNING id;
                    """, (nombre_pj, raza, json.dumps(items_asignados), notas))
                    r = cur.fetchone()
                    if r: nuevo_id = r['id']
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()

        miembro = {"id": nuevo_id, "nombre_pj": nombre_pj, "raza": raza, "items_asignados": items_asignados, "notas": notas}
        miembros_clan_db = [m for m in miembros_clan_db if m['nombre_pj'].lower() != nombre_pj.lower()]
        miembros_clan_db.append(miembro)
        guardar_json(MIEMBROS_FILE, miembros_clan_db)
        return jsonify({"status": "ok", "miembro": miembro}), 201

    if request.method == 'PUT':
        data = request.json or {}
        m_id = data.get('id')
        for m in miembros_clan_db:
            if m['id'] == m_id:
                m['nombre_pj'] = data.get('nombre_pj', m['nombre_pj'])
                m['raza'] = data.get('raza', m['raza'])
                m['items_asignados'] = data.get('items_asignados', m['items_asignados'])
                m['notas'] = data.get('notas', m['notas'])

        guardar_json(MIEMBROS_FILE, miembros_clan_db)
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE public.miembros_clan
                        SET nombre_pj = %s, raza = %s, items_asignados = %s, notas = %s
                        WHERE id = %s;
                    """, (data.get('nombre_pj'), data.get('raza'), json.dumps(data.get('items_asignados', [])), data.get('notas', ''), m_id))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

# --- TIMERS Y BOTS ---
@app.route('/api/status_timers')
@app.route('/api/timers')
def get_status_timers():
    return jsonify({
        "timers": status_timers,
        "ocultos": list(tarjetas_ocultas_global),
        "heartbeats": heartbeats,
        "ultimas_pcs": ultimas_pcs,
        "ultimos_pjs": ultimos_pjs,
        "mapas": status_mapas
    })

@app.route('/api/kill', methods=['POST'])
def registrar_kill():
    data = request.json or {}
    server = data.get('server')
    boss_raw = data.get('boss', '').strip()
    pc_id = data.get('pc_id', 'Manual Web')
    pj_name = data.get('pj_name', 'Manual Web')

    if not server or not boss_raw: return jsonify({"error": "Faltan datos"}), 400
    boss = re.sub(r'\s+\d+$', '', boss_raw)
    es_manual_web = (pc_id == 'Manual Web') or ('user' in session)

    if boss in BOSSES_MANUALES and not es_manual_web:
        return jsonify({"status": "ignored", "message": f"El boss '{boss}' es manual."}), 200

    now_unix = int(time.time())
    clave_cartel = f"{server}_{boss}_{pj_name}"

    if pc_id != 'Manual Web':
        ultimo_registro = ultimos_kills_recientes.get(clave_cartel, 0)
        if (now_unix - ultimo_registro) < 120:
            return jsonify({"status": "ignored", "message": "Cartel duplicado ignorado."}), 200
        ultimos_kills_recientes[clave_cartel] = now_unix

    if server not in status_timers: status_timers[server] = {}
    status_timers[server][boss] = now_unix
    clave_card = f"{server}_{boss}"
    if clave_card in tarjetas_ocultas_global: tarjetas_ocultas_global.remove(clave_card)
    guardar_json(DATA_FILE, status_timers)

    if pc_id != 'Manual Web':
        heartbeats[server] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ultimas_pcs[server] = pc_id
        ultimos_pjs[server] = pj_name

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.timers_bosses (server, timers, last_pc, last_pj, last_heartbeat)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (server) DO UPDATE 
                    SET timers = EXCLUDED.timers, last_pc = EXCLUDED.last_pc, last_pj = EXCLUDED.last_pj, last_heartbeat = NOW();
                """, (server, json.dumps(status_timers.get(server, {})), pc_id, pj_name))
                conn.commit()
            conn.close()
        except Exception:
            if conn: conn.close()

    return jsonify({"status": "ok", "message": f"Kill de {boss} registrado"}), 200

@app.route('/api/reset_boss', methods=['POST'])
def reset_boss():
    data = request.json or {}
    server = data.get('server')
    boss = data.get('boss')

    if server and boss:
        clave_card = f"{server}_{boss}"
        tarjetas_ocultas_global.add(clave_card)
        keys_a_borrar = [k for k in ultimos_kills_recientes if k.startswith(f"{server}_{boss}_")]
        for k in keys_a_borrar: ultimos_kills_recientes.pop(k, None)

        if server in status_timers and boss in status_timers[server]:
            del status_timers[server][boss]
            guardar_json(DATA_FILE, status_timers)
            conn = get_db()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE public.timers_bosses SET timers = %s WHERE server = %s;", 
                                    (json.dumps(status_timers.get(server, {})), server))
                        conn.commit()
                    conn.close()
                except Exception:
                    if conn: conn.close()

        return jsonify({"status": "ok", "message": f"{boss} ocultado"}), 200
    return jsonify({"error": "Datos inválidos"}), 400

@app.route('/api/mapa_kill', methods=['POST'])
def mapa_kill():
    data = request.json or {}
    server_num = str(data.get('server', '1'))
    spot_id = str(data.get('spot_id'))

    if not spot_id: return jsonify({"error": "Spot requerido"}), 400
    if server_num not in status_mapas: status_mapas[server_num] = {}
    status_mapas[server_num][spot_id] = int(time.time() * 1000)
    guardar_json(MAPAS_FILE, status_mapas)
    return jsonify({"status": "ok", "mapas": status_mapas}), 200

@app.route('/api/mapa_reset', methods=['POST'])
def mapa_reset():
    data = request.json or {}
    server_num = str(data.get('server', '1'))
    spot_id = str(data.get('spot_id'))

    if server_num in status_mapas and spot_id in status_mapas[server_num]:
        del status_mapas[server_num][spot_id]
        guardar_json(MAPAS_FILE, status_mapas)
    return jsonify({"status": "ok", "mapas": status_mapas}), 200

@app.route('/api/heartbeat', methods=['POST'])
def registrar_heartbeat():
    data = request.json or {}
    server = data.get('server')
    pc_id = data.get('pc_id', 'Desconocido')
    pj_name = data.get('pj_name', 'Desconocido')

    if server:
        heartbeats[server] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ultimas_pcs[server] = pc_id
        ultimos_pjs[server] = pj_name
        conn = get_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.timers_bosses (server, last_pc, last_pj, last_heartbeat)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT (server) DO UPDATE 
                        SET last_pc = EXCLUDED.last_pc, last_pj = EXCLUDED.last_pj, last_heartbeat = NOW();
                    """, (server, pc_id, pj_name))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200
    return jsonify({"error": "Servidor requerido"}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username_raw = data.get('username', '').strip()
    username = username_raw.lower()
    password = data.get('password', '')

    user_info = usuarios_db.get(username)
    if not user_info:
        conn = get_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM public.usuarios WHERE LOWER(username) = %s;", (username,))
                    row = cur.fetchone()
                    if row:
                        user_info = {
                            "username": row['username'],
                            "password": row['password_hash'],
                            "rol": row.get('rol', 'encargado'),
                            "requiere_cambio": row.get('requiere_cambio_clave', False)
                        }
                        usuarios_db[username] = user_info
                conn.close()
            except Exception:
                if conn: conn.close()

    if user_info:
        stored_pass = user_info.get("password", "")
        if stored_pass.startswith("scrypt:") or stored_pass.startswith("pbkdf2:"):
            es_valido = check_password_hash(stored_pass, password)
        else:
            es_valido = (stored_pass == password)

        if es_valido:
            session['user'] = user_info.get('username', username_raw)
            session['rol'] = user_info.get("rol", "encargado")
            return jsonify({
                "status": "ok",
                "user": session['user'],
                "rol": session['rol'],
                "requiere_cambio": user_info.get("requiere_cambio", False)
            }), 200

    return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/session')
def api_session():
    if 'user' in session:
        return jsonify({
            "logged_in": True,
            "user": session['user'],
            "rol": session.get('rol', 'encargado'),
            "requiere_cambio": False
        })
    return jsonify({"logged_in": False})

@app.route('/api/cambiar_clave', methods=['POST'])
def cambiar_clave():
    if 'user' not in session: return jsonify({"error": "No autorizado"}), 401
    data = request.json or {}
    nueva_clave = data.get('nueva_clave')
    if not nueva_clave or len(nueva_clave) < 4: return jsonify({"error": "Mínimo 4 caracteres"}), 400

    username = session['user']
    new_hash = generate_password_hash(nueva_clave)
    u_key = username.lower()
    if u_key in usuarios_db:
        usuarios_db[u_key]["password"] = new_hash
        usuarios_db[u_key]["requiere_cambio"] = False
        guardar_json(USERS_FILE, usuarios_db)

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE public.usuarios SET password_hash = %s, requiere_cambio_clave = FALSE WHERE LOWER(username) = %s;", 
                            (new_hash, u_key))
                conn.commit()
            conn.close()
        except Exception:
            if conn: conn.close()

    return jsonify({"status": "ok", "message": "Contraseña actualizada"}), 200

@app.route('/api/usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'user' not in session or session.get('rol') != 'admin': return jsonify({"error": "Acceso denegado"}), 403
    conn = get_db()
    if request.method == 'GET':
        lista = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT username, rol, requiere_cambio_clave, creado_por FROM public.usuarios ORDER BY id ASC;")
                    for r in cur.fetchall():
                        lista.append({
                            "username": r['username'],
                            "rol": r.get('rol', 'encargado'),
                            "requiere_cambio_clave": r.get('requiere_cambio_clave', False),
                            "creado_por": r.get('creado_por', 'Sistema')
                        })
                conn.close()
                return jsonify(lista)
            except Exception:
                if conn: conn.close()

        for u, val in usuarios_db.items():
            lista.append({
                "username": val.get("username", u),
                "rol": val.get("rol", "encargado"),
                "requiere_cambio_clave": val.get("requiere_cambio", False),
                "creado_por": val.get("creado_por", "Sistema")
            })
        return jsonify(lista)

    if request.method == 'POST':
        data = request.json or {}
        new_user = data.get('username', '').strip()
        new_pass = data.get('password', '')
        new_rol = data.get('rol', 'encargado')
        if not new_user or not new_pass:
            if conn: conn.close()
            return jsonify({"error": "Faltan campos"}), 400

        u_key = new_user.lower()
        p_hash = generate_password_hash(new_pass)
        usuarios_db[u_key] = {
            "username": new_user, "password": p_hash,
            "rol": new_rol, "requiere_cambio": True, "creado_por": session['user']
        }
        guardar_json(USERS_FILE, usuarios_db)
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.usuarios (username, password_hash, rol, requiere_cambio_clave, creado_por)
                        VALUES (%s, %s, %s, TRUE, %s)
                        ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash, rol = EXCLUDED.rol;
                    """, (new_user, p_hash, new_rol, session['user']))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok", "message": f"Usuario {new_user} creado"}), 201

@app.route('/api/donaciones', methods=['GET', 'POST'])
def donaciones():
    if request.method == 'GET':
        return jsonify(donaciones_db)
    if request.method == 'POST':
        if 'user' not in session: return jsonify({"error": "No autorizado"}), 401
        data = request.json or {}
        pj_name = data.get('pj_name')
        tipo_donacion = data.get('tipo_donacion')
        cantidad = data.get('cantidad', 1)
        if not pj_name or not tipo_donacion: return jsonify({"error": "Faltan datos"}), 400

        nueva_donacion = {
            "id": int(time.time() * 1000), "pj_name": pj_name, "tipo_donacion": tipo_donacion,
            "cantidad": int(cantidad), "registrado_por": session['user'],
            "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modificado_por": None, "fecha_modificacion": None
        }
        donaciones_db.insert(0, nueva_donacion)
        guardar_json(DONACIONES_FILE, donaciones_db)

        conn = get_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.donaciones (pj_name, tipo_donacion, cantidad, registrado_por)
                        VALUES (%s, %s, %s, %s);
                    """, (pj_name, tipo_donacion, int(cantidad), session['user']))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok", "donacion": nueva_donacion}), 201

@app.route('/api/donaciones/<int:donacion_id>', methods=['PUT'])
def editar_donacion(donacion_id):
    if 'user' not in session: return jsonify({"error": "No autorizado"}), 401
    data = request.json or {}
    for don in donaciones_db:
        if don['id'] == donacion_id:
            don['pj_name'] = data.get('pj_name', don['pj_name'])
            don['tipo_donacion'] = data.get('tipo_donacion', don['tipo_donacion'])
            don['cantidad'] = int(data.get('cantidad', don['cantidad']))
            don['modificado_por'] = session['user']
            don['fecha_modificacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            guardar_json(DONACIONES_FILE, donaciones_db)
            conn = get_db()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE public.donaciones 
                            SET pj_name = %s, tipo_donacion = %s, cantidad = %s, 
                                modificado_por = %s, fecha_modificacion = NOW()
                            WHERE id = %s;
                        """, (don['pj_name'], don['tipo_donacion'], don['cantidad'], session['user'], donacion_id))
                        conn.commit()
                    conn.close()
                except Exception:
                    if conn: conn.close()
            return jsonify({"status": "ok", "donacion": don}), 200
    return jsonify({"error": "Donación no encontrada"}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
