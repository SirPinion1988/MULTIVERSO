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
ITEMS_FILE = "items_mu_data.json"
MIEMBROS_FILE = "miembros_data.json"

USUARIOS_AUTORIZADOS = ["pinion", "tolkien", "nasda"]

BOSSES_MANUALES = [
    "Red Dragon", "Yellow Goblin", "Blue Goblin", 
    "Red Goblin", "Santa", "White Wizard", "Skeleton King"
]

DEFAULT_ITEMS = [
    {"id": 1, "archivo_id": "1iAU8Va4", "nombre": "Excellent Morning Star", "clases": ["Dark Knight", "Magic Gladiator", "Dark Lord", "Rage Fighter"], "opciones": ["Falling Slash Skill", "Additional damage +60", "[Rare] Excellent damage rate +7%", "[Rare] Increases attack speed +28", "[Rare] Critical damage rate +7%"], "bonus_excelente": ["Increases Strength +128", "Increases Agility +147"], "drive_id": "1iAU8Va4", "asignado_a": None},
    {"id": 2, "archivo_id": "19MyVAmk", "nombre": "Excellent Assassin Sword", "clases": ["Dark Knight", "Magic Gladiator"], "opciones": ["Additional damage +30", "[Rare] Critical damage rate +7%"], "bonus_excelente": ["Increases Strength +132", "Increases Agility +133"], "drive_id": "19MyVAmk", "asignado_a": None},
    {"id": 3, "archivo_id": "1XcEYqEM", "nombre": "Excellent Leather Gloves", "clases": ["Dark Knight", "Magic Gladiator", "Dark Lord"], "opciones": ["Additional defense +30", "[Rare] Increases maximum SD +3%", "[Rare] Reflect damage +3%", "[Rare] Increases zen drop rate +21%"], "bonus_excelente": ["Increases Strength +36", "Increases Energy +39"], "drive_id": "1XcEYqEM", "asignado_a": None},
    {"id": 4, "archivo_id": "1kr-En", "nombre": "Excellent Vine Pants", "clases": ["Elf"], "opciones": ["Additional defense +30", "[Rare] Reflect damage +3%"], "bonus_excelente": ["Increases Agility +23", "Increases Energy +29"], "drive_id": "1kr-En", "asignado_a": None},
    {"id": 5, "archivo_id": "1ruk-H", "nombre": "Excellent Bluewing Crossbow", "clases": ["Elf"], "opciones": ["Additional damage +30", "[Rare] Increases physical damage +7%", "[Epic] Critical damage rate +10%"], "bonus_excelente": ["Increases Agility +141", "Increases Energy +178"], "drive_id": "1ruk-H", "asignado_a": None},
    {"id": 6, "archivo_id": "1zw2LP", "nombre": "Excellent Pad Boots", "clases": ["Dark Wizard", "Magic Gladiator"], "opciones": ["Additional defense +30", "[Rare] Increases maximum life +3%", "[Rare] Damage decrease +3%", "[Legendary] Reflect damage +4%"], "bonus_excelente": ["Increases Energy +37", "Increases Strength +26"], "drive_id": "1zw2LP", "asignado_a": None},
    {"id": 7, "archivo_id": "267.png", "nombre": "Excellent Scale Pants", "clases": ["Dark Knight", "Magic Gladiator", "Dark Lord", "Rage Fighter"], "opciones": ["Additional defense +30", "[Rare] Increases maximum life +3%", "[Epic] Damage decrease +5%"], "bonus_excelente": ["Increases Strength +30", "Increases Energy +31"], "drive_id": "267.png", "asignado_a": None},
    {"id": 8, "archivo_id": "265.png", "nombre": "Excellent Sphinx Armor", "clases": ["Dark Wizard", "Magic Gladiator"], "opciones": ["Additional defense +15", "[Legendary] Increases maximum life +4%", "[Rare] Increases zen drop rate +21%"], "bonus_excelente": ["Increases Energy +50", "Increases Vitality +41"], "drive_id": "1BC0k90uaW4rHp1dQM1Y-pxLwE1KfnLku", "asignado_a": None},
    {"id": 9, "archivo_id": "264.png", "nombre": "Excellent Legendary Pants", "clases": ["Dark Wizard", "Magic Gladiator"], "opciones": ["Additional defense +15", "[Epic] Reflect damage +5%", "[Epic] Critical damage resistance +10%"], "bonus_excelente": ["Increases Agility +98", "Increases Strength +110"], "drive_id": "1Jmjh8YltzfO2xBhBDGX0oYxr-WMdG4xK", "asignado_a": None},
    {"id": 10, "archivo_id": "260.png", "nombre": "Excellent Black Dragon Pants", "clases": ["Dark Knight"], "opciones": ["Additional defense +15", "[Legendary] Reflect damage +4%", "[Epic] Increases zen drop rate +30%"], "bonus_excelente": ["Increases Energy +101", "Increases Strength +145"], "drive_id": "1iHHVi5Fr0KKdjWX1luSpI9CzuPAK5Aq5", "asignado_a": None},
    {"id": 11, "archivo_id": "246.png", "nombre": "Excellent Bronze Gloves", "clases": ["Dark Knight", "Magic Gladiator", "Dark Lord"], "opciones": ["[Rare] Increases maximum SD +3%", "[Rare] Damage decrease +3%", "[Legendary] Critical damage resistance +8%"], "bonus_excelente": ["Increases Strength +30", "Increases Agility +26"], "drive_id": "1u0mZvM_JmyY3NABCGCf35dj6rGVqrFHh", "asignado_a": None},
    {"id": 12, "archivo_id": "244.png", "nombre": "Excellent Book of Samut", "clases": ["Summoner"], "opciones": ["Increases wizardry by 3%", "[Rare] Critical damage rate +7%"], "bonus_excelente": ["Increases Energy +146", "Increases Strength +200"], "drive_id": "1f5VMBmH8o4CdKIblTkW382mnxkzj7s2U", "asignado_a": None}
]

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
donaciones_db = cargar_json(DONACIONES_FILE, [])
items_mu_db = cargar_json(ITEMS_FILE, DEFAULT_ITEMS) or DEFAULT_ITEMS
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

def usuario_autorizado():
    return 'user' in session and session['user'].lower() in USUARIOS_AUTORIZADOS

def sincronizar_drive_continuo():
    global items_mu_db
    archivos_detectados = []

    if GOOGLE_API_KEY:
        try:
            q = urllib.parse.quote(f"'{FOLDER_DRIVE_ID}' in parents and trashed=false")
            url = f"https://www.googleapis.com/drive/v3/files?q={q}&key={GOOGLE_API_KEY}&fields=files(id,name,mimeType)"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for f in data.get('files', []):
                    if 'image' in f.get('mimeType', ''):
                        archivos_detectados.append({"id": f['id'], "name": f['name']})
        except Exception: pass

    if not archivos_detectados:
        try:
            url_folder = f"https://drive.google.com/embeddedfolderview?id={FOLDER_DRIVE_ID}#grid"
            req = urllib.request.Request(url_folder, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                ids = set(re.findall(r'https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', html))
                for fid in ids:
                    archivos_detectados.append({"id": fid, "name": fid[:8]})
        except Exception: pass

    existentes = {it.get('drive_id') for it in items_mu_db if it.get('drive_id')}
    existentes_arch = {it.get('archivo_id') for it in items_mu_db if it.get('archivo_id')}
    nuevos = 0
    for arch in archivos_detectados:
        fid = arch['id']
        fnom = arch['name']
        if fid not in existentes and fnom not in existentes_arch:
            nuevo_item = {
                "id": int(time.time() * 1000) + nuevos,
                "archivo_id": fnom,
                "nombre": fnom,
                "tipo": "General",
                "clases": ["Dark Knight", "Dark Wizard", "Elf", "Magic Gladiator", "Dark Lord", "Summoner", "Rage Fighter"],
                "opciones": ["[Auto] Captura detectada en Drive"],
                "bonus_excelente": [],
                "drive_id": fid,
                "asignado_a": None
            }
            items_mu_db.insert(0, nuevo_item)
            nuevos += 1

    if nuevos > 0:
        guardar_json(ITEMS_FILE, items_mu_db)

def obtener_todos_items():
    global items_mu_db
    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, archivo_id, nombre, tipo, clases, opciones, bonus_excelente, drive_id, asignado_a
                    FROM public.items_mu ORDER BY id ASC;
                """)
                filas = cur.fetchall()
                if filas and len(filas) > 0:
                    items_formateados = []
                    for r in filas:
                        items_formateados.append({
                            "id": r['id'],
                            "archivo_id": r.get('archivo_id') or str(r['id']),
                            "nombre": r.get('nombre') or 'Sin Nombre',
                            "tipo": r.get('tipo') or 'General',
                            "clases": normalizar_campo_json(r.get('clases'), []),
                            "opciones": normalizar_campo_json(r.get('opciones'), []),
                            "bonus_excelente": normalizar_campo_json(r.get('bonus_excelente'), []),
                            "drive_id": r.get('drive_id') or '',
                            "asignado_a": r.get('asignado_a')
                        })
                    items_mu_db = items_formateados
                    guardar_json(ITEMS_FILE, items_mu_db)
            conn.close()
        except Exception:
            try: conn.close()
            except Exception: pass

    if not items_mu_db:
        items_mu_db = DEFAULT_ITEMS

    try: sincronizar_drive_continuo()
    except Exception: pass

    return items_mu_db

@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)

@app.route('/items')
def vista_items():
    return render_template('items.html')

@app.route('/api/items', methods=['GET', 'PUT'])
def api_items():
    global items_mu_db
    if request.method == 'GET':
        return jsonify(obtener_todos_items())

    if request.method == 'PUT':
        if not usuario_autorizado():
            return jsonify({"error": "Solo Pinion, tolkien o nasda pueden asignar ítems"}), 403

        data = request.json or {}
        item_id = data.get('id')
        asignado_a = data.get('asignado_a')
        if asignado_a: asignado_a = asignado_a.strip()

        for it in items_mu_db:
            if it.get('id') == item_id or it.get('archivo_id') == item_id:
                it['asignado_a'] = asignado_a

        guardar_json(ITEMS_FILE, items_mu_db)

        conn = get_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE id = %s OR archivo_id = %s;", 
                                (asignado_a, item_id, str(item_id)))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

@app.route('/api/miembros', methods=['GET', 'POST', 'DELETE'])
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
        if not usuario_autorizado():
            return jsonify({"error": "Solo Pinion, tolkien o nasda pueden modificar miembros"}), 403

        data = request.json or {}
        nombre_pj = data.get('nombre_pj', '').strip()
        raza = data.get('raza', 'Dark Knight').strip()
        items_asignados = data.get('items_asignados', [])

        if not nombre_pj:
            return jsonify({"error": "Nick de PJ requerido"}), 400

        nuevo_id = int(time.time() * 1000)
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.miembros_clan (nombre_pj, raza, items_asignados)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (nombre_pj) DO UPDATE 
                        SET raza = EXCLUDED.raza, items_asignados = EXCLUDED.items_asignados
                        RETURNING id;
                    """, (nombre_pj, raza, json.dumps(items_asignados)))
                    r = cur.fetchone()
                    if r: nuevo_id = r['id']
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()

        miembro = {"id": nuevo_id, "nombre_pj": nombre_pj, "raza": raza, "items_asignados": items_asignados}
        miembros_clan_db = [m for m in miembros_clan_db if m['nombre_pj'].lower() != nombre_pj.lower()]
        miembros_clan_db.append(miembro)
        guardar_json(MIEMBROS_FILE, miembros_clan_db)
        return jsonify({"status": "ok", "miembro": miembro}), 201

    if request.method == 'DELETE':
        if not usuario_autorizado():
            return jsonify({"error": "Acceso restringido a encargados"}), 403

        data = request.json or {}
        m_id = data.get('id')
        miembros_clan_db = [m for m in miembros_clan_db if m['id'] != m_id]
        guardar_json(MIEMBROS_FILE, miembros_clan_db)

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM public.miembros_clan WHERE id = %s;", (m_id,))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

# Importador masivo de miembros y asignación (Nick, Raza, Items)
@app.route('/api/miembros/importar_csv', methods=['POST'])
def importar_miembros_csv():
    if not usuario_autorizado():
        return jsonify({"error": "Acceso restringido a encargados"}), 403

    data = request.json or {}
    lineas = data.get('csv_data', '').splitlines()
    cargados = 0

    for lin in lineas:
        partes = [p.strip() for p in lin.split(',')]
        if len(partes) >= 2:
            nick = partes[0]
            raza = partes[1]
            if not nick or nick.lower() == 'nick': continue
            items = partes[2:] if len(partes) > 2 else []
            items_limpios = [x for x in items if x]

            # Guardar o actualizar miembro
            conn = get_db()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO public.miembros_clan (nombre_pj, raza, items_asignados)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (nombre_pj) DO UPDATE SET raza = EXCLUDED.raza, items_asignados = EXCLUDED.items_asignados;
                        """, (nick, raza, json.dumps(items_limpios)))
                        conn.commit()
                    conn.close()
                except Exception:
                    if conn: conn.close()

            # Asignar items en tabla de items
            for arch_id in items_limpios:
                conn_it = get_db()
                if conn_it:
                    try:
                        with conn_it.cursor() as cur:
                            cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE archivo_id = %s;", (nick, arch_id))
                            conn_it.commit()
                        conn_it.close()
                    except Exception:
                        if conn_it: conn_it.close()
            cargados += 1

    return jsonify({"status": "ok", "cargados": cargados}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username_raw = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username_raw or not password:
        return jsonify({"error": "Completá usuario y contraseña"}), 400

    username = username_raw.lower()

    # Validación directa garantizada para los 3 usuarios del clan
    credenciales = {
        "pinion": ("G1nt0n1c", "admin"),
        "tolkien": ("tolkien123", "encargado"),
        "nasda": ("nasda123", "encargado")
    }

    if username in credenciales and password == credenciales[username][0]:
        session['user'] = username_raw
        session['rol'] = credenciales[username][1]
        return jsonify({"status": "ok", "user": session['user'], "rol": session['rol']}), 200

    # Comprobación en base de datos Supabase
    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT username, password_hash, rol FROM public.usuarios WHERE LOWER(username) = %s;", (username,))
                row = cur.fetchone()
                if row:
                    p_hash = row['password_hash']
                    es_valido = check_password_hash(p_hash, password) if (p_hash.startswith("scrypt:") or p_hash.startswith("pbkdf2:")) else (p_hash == password)
                    if es_valido:
                        session['user'] = row['username']
                        session['rol'] = row.get('rol', 'encargado')
                        conn.close()
                        return jsonify({"status": "ok", "user": session['user'], "rol": session['rol']}), 200
            conn.close()
        except Exception:
            if conn: conn.close()

    return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/session')
def api_session():
    if 'user' in session:
        return jsonify({"logged_in": True, "user": session['user'], "rol": session.get('rol', 'encargado'), "autorizado": usuario_autorizado()})
    return jsonify({"logged_in": False, "autorizado": False})

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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
