import os
import time
import json
import re
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "multiverso_secret_key_2026")

DATABASE_URL = os.environ.get("DATABASE_URL")
LINK_DESCARGA_BOT = "https://drive.google.com/uc?export=download&id=TU_ID_DE_GOOGLE_DRIVE"
FOLDER_DRIVE_ID = os.environ.get("DRIVE_FOLDER_ID", "1nSqaWKAsEc7s6BYT8xg22MoITXLT7IIK")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyDA99w81Z7LDtsA-gX_MmZLdVDFxmqEmlk")

DATA_FILE = "timers_data.json"
USERS_FILE = "users_data.json"
DONACIONES_FILE = "donaciones_data.json"
MAPAS_FILE = "mapas_data.json"
MIEMBROS_FILE = "miembros_data.json"

BOSSES_MANUALES = [
    "Red Dragon", "Yellow Goblin", "Blue Goblin", 
    "Red Goblin", "Santa", "White Wizard", "Skeleton King"
]

PALABRAS_ARMAS = [
    "sword", "blade", "staff", "crossbow", "bow", "stick", "book", 
    "claw", "scepter", "mace", "morning star", "axe", "spear", "dread", "two-hand"
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
usuarios_db = cargar_json(USERS_FILE, {})
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

def usuario_es_autorizado():
    if 'user' not in session: return False
    return session['user'].lower() in ['pinion', 'tolkien', 'nasda']

def es_solo_armadura(nombre, archivo_id):
    texto = f"{nombre} {archivo_id}".lower()
    return not any(w in texto for w in PALABRAS_ARMAS)

@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)

@app.route('/items')
def vista_items():
    return render_template('items.html')

# --- LECTURA DE DRIVE SIN DESCARGAR IMÁGENES ---
def sincronizar_drive_rapido():
    if not FOLDER_DRIVE_ID or not GOOGLE_API_KEY:
        return []

    archivos_detectados = []
    try:
        page_token = None
        q = f"'{FOLDER_DRIVE_ID}' in parents and trashed=false"
        while True:
            url = f"https://www.googleapis.com/drive/v3/files?q={requests.utils.quote(q)}&key={GOOGLE_API_KEY}&fields=nextPageToken,files(id,name,mimeType)&pageSize=100"
            if page_token:
                url += f"&pageToken={page_token}"
            res = requests.get(url, timeout=6)
            if res.status_code == 200:
                data = res.json()
                for f in data.get('files', []):
                    nombre = f.get('name', '')
                    if 'image' in f.get('mimeType', '') or any(nombre.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                        archivos_detectados.append(f)
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
            else:
                break
    except Exception as e:
        print(f"Error Drive: {e}")

    conn = get_db()
    items_retorno = []

    for idx, arch in enumerate(archivos_detectados):
        fid = arch['id']
        fname = arch['name']
        num_m = re.search(r'\d+', fname)
        num_val = int(num_m.group(0)) if num_m else (idx + 2)
        nombre_item = f"Armadura #{num_val}"

        if not es_solo_armadura(nombre_item, fname):
            continue

        item_dict = {
            "id": num_val,
            "archivo_id": fname,
            "nombre": nombre_item,
            "tipo": "Armor",
            "base_score": 0, "defense": 0, "durability": "-",
            "clases": ["Dark Knight", "Dark Wizard", "Elf", "Magic Gladiator", "Dark Lord", "Summoner", "Rage Fighter"],
            "opciones": ["[Auto] Sincronizado"],
            "bonus_excelente": [],
            "drive_id": fid,
            "asignado_a": None
        }
        items_retorno.append(item_dict)

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.items_mu (archivo_id, nombre, tipo, clases, opciones, bonus_excelente, drive_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (drive_id) DO NOTHING;
                    """, (
                        fname,
                        nombre_item,
                        "Armor",
                        json.dumps(item_dict["clases"]),
                        json.dumps(item_dict["opciones"]),
                        json.dumps(item_dict["bonus_excelente"]),
                        fid
                    ))
                    conn.commit()
            except Exception: pass

    if conn: conn.close()
    items_retorno.sort(key=lambda x: int(re.search(r'\d+', x['archivo_id']).group(0)) if re.search(r'\d+', x['archivo_id']) else 999999)
    return items_retorno

# --- API DE ITEMS ---
@app.route('/api/items', methods=['GET', 'PUT'])
def api_items():
    conn = get_db()
    if request.method == 'GET':
        items_formateados = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, archivo_id, nombre, tipo, base_score, defense, durability,
                               clases, opciones, bonus_excelente, drive_id, asignado_a
                        FROM public.items_mu
                        ORDER BY 
                            NULLIF(regexp_replace(archivo_id, '\D', '', 'g'), '')::numeric ASC NULLS LAST,
                            id ASC;
                    """)
                    filas = cur.fetchall()
                    for r in filas:
                        nom = r.get('nombre') or 'Sin Nombre'
                        arch = r.get('archivo_id') or str(r['id'])
                        if not es_solo_armadura(nom, arch):
                            continue
                        items_formateados.append({
                            "id": r['id'],
                            "archivo_id": arch,
                            "nombre": nom,
                            "tipo": r.get('tipo') or 'Armor',
                            "base_score": r.get('base_score') or 0,
                            "defense": r.get('defense') or 0,
                            "durability": r.get('durability') or '-',
                            "clases": normalizar_campo_json(r.get('clases'), []),
                            "opciones": normalizar_campo_json(r.get('opciones'), []),
                            "bonus_excelente": normalizar_campo_json(r.get('bonus_excelente'), []),
                            "drive_id": r.get('drive_id') or '',
                            "asignado_a": r.get('asignado_a')
                        })
                conn.close()
            except Exception:
                try: conn.close()
                except Exception: pass

        if not items_formateados:
            items_formateados = sincronizar_drive_rapido()

        return jsonify(items_formateados), 200

    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado"}), 403

    if request.method == 'PUT':
        data = request.json or {}
        item_id = data.get('id')
        asignado_a = data.get('asignado_a')

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE id = %s;", (asignado_a, item_id))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

# --- API DE MIEMBROS ---
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
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify(miembros_clan_db)

    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado"}), 403

    if request.method == 'POST':
        data = request.json or {}
        nombre_pj = data.get('nombre_pj', '').strip()
        raza = data.get('raza', 'Dark Knight').strip()
        items_asignados = data.get('items_asignados', [])

        if not nombre_pj:
            if conn: conn.close()
            return jsonify({"error": "Nick requerido"}), 400

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

                    cur.execute("UPDATE public.items_mu SET asignado_a = NULL WHERE asignado_a = %s;", (nombre_pj,))
                    for arch_id in items_asignados:
                        cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE archivo_id = %s OR CAST(id AS TEXT) = %s;", (nombre_pj, str(arch_id), str(arch_id)))

                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()

        miembro = {"id": nuevo_id, "nombre_pj": nombre_pj, "raza": raza, "items_asignados": items_asignados}
        miembros_clan_db = [m for m in miembros_clan_db if m['nombre_pj'].lower() != nombre_pj.lower()]
        miembros_clan_db.append(miembro)
        return jsonify({"status": "ok", "miembro": miembro}), 201

    if request.method == 'DELETE':
        data = request.json or {}
        m_id = data.get('id')
        nombre_pj = data.get('nombre_pj')

        miembros_clan_db = [m for m in miembros_clan_db if m['id'] != m_id]
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM public.miembros_clan WHERE id = %s;", (m_id,))
                    if nombre_pj:
                        cur.execute("UPDATE public.items_mu SET asignado_a = NULL WHERE asignado_a = %s;", (nombre_pj,))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

@app.route('/api/miembros/importar', methods=['POST'])
def importar_miembros_excel():
    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado"}), 403

    filas = (request.json or {}).get('filas', [])
    if not filas:
        return jsonify({"error": "No se enviaron datos"}), 400

    conn = get_db()
    for row in filas:
        pj = str(row.get('nick', '')).strip()
        raza = str(row.get('raza', 'Dark Knight')).strip()
        items_raw = str(row.get('items', '')).strip()
        items_lista = [x.strip() for x in items_raw.split(',') if x.strip()]

        if not pj: continue

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.miembros_clan (nombre_pj, raza, items_asignados)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (nombre_pj) DO UPDATE 
                        SET raza = EXCLUDED.raza, items_asignados = EXCLUDED.items_asignados;
                    """, (pj, raza, json.dumps(items_lista)))
                    
                    cur.execute("UPDATE public.items_mu SET asignado_a = NULL WHERE asignado_a = %s;", (pj,))
                    for arch_id in items_lista:
                        cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE archivo_id = %s OR CAST(id AS TEXT) = %s;", (pj, str(arch_id), str(arch_id)))
                    conn.commit()
            except Exception: pass

    if conn: conn.close()
    return jsonify({"status": "ok", "message": f"{len(filas)} filas procesadas"}), 200

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
    password = data.get('password', '').strip()

    if not username_raw or not password:
        return jsonify({"error": "Completá usuario y contraseña"}), 400

    username = username_raw.lower()

    conn = get_db()
    user_db = None
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT username, password_hash, rol FROM public.usuarios WHERE LOWER(username) = %s;", (username,))
                user_db = cur.fetchone()
            conn.close()
        except Exception:
            if conn: conn.close()

    if not user_db:
        if username == 'pinion' and password == 'G1nt0n1c':
            user_db = {'username': 'Pinion', 'password_hash': 'G1nt0n1c', 'rol': 'admin'}
        elif username == 'tolkien' and password == 'tolkien123':
            user_db = {'username': 'tolkien', 'password_hash': 'tolkien123', 'rol': 'encargado'}
        elif username == 'nasda' and password == 'nasda123':
            user_db = {'username': 'nasda', 'password_hash': 'nasda123', 'rol': 'encargado'}

    if user_db:
        stored_pass = user_db.get("password_hash", "")
        es_valido = False
        if stored_pass.startswith("scrypt:") or stored_pass.startswith("pbkdf2:"):
            try: es_valido = check_password_hash(stored_pass, password)
            except Exception: pass
        else:
            es_valido = (stored_pass == password)

        if es_valido:
            session['user'] = user_db.get('username', username_raw)
            session['rol'] = user_db.get('rol', 'encargado')
            return jsonify({
                "status": "ok",
                "user": session['user'],
                "rol": session['rol']
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
            "autorizado": usuario_es_autorizado()
        })
    return jsonify({"logged_in": False, "autorizado": False})

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
            "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        donaciones_db.insert(0, nueva_donacion)
        guardar_json(DONACIONES_FILE, donaciones_db)

        conn = get_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO public.donaciones (pj_name, tipo_donacion, cantidad, registrado_por) VALUES (%s, %s, %s, %s);", (pj_name, tipo_donacion, int(cantidad), session['user']))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok", "donacion": nueva_donacion}), 201

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
