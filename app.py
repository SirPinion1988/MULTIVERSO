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

# ID DE TU CARPETA DE GOOGLE DRIVE COMPARTIDA
FOLDER_DRIVE_ID = "1nSqaWKAsEc7s6BYT8xg22MoITXLT7IIK"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

DATA_FILE = "timers_data.json"
USERS_FILE = "users_data.json"
DONACIONES_FILE = "donaciones_data.json"
MAPAS_FILE = "mapas_data.json"
ITEMS_FILE = "items_mu_data.json"

BOSSES_MANUALES = [
    "Red Dragon", "Yellow Goblin", "Blue Goblin", 
    "Red Goblin", "Santa", "White Wizard", "Skeleton King"
]

def cargar_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data:
                    return data
        except Exception:
            pass
    return default_val

def guardar_json(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando {filepath}: {e}")

# Memoria local
status_timers = cargar_json(DATA_FILE, {"Server 1": {}, "Server 2": {}, "Server 3": {}, "Server 20": {}})
status_mapas = cargar_json(MAPAS_FILE, {"1": {}, "2": {}, "3": {}})
usuarios_db = cargar_json(USERS_FILE, {"pinion": {"password": "pass123", "rol": "admin", "requiere_cambio": False}})
donaciones_db = cargar_json(DONACIONES_FILE, [])
items_mu_db = cargar_json(ITEMS_FILE, [])

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
        return psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=3)
    except Exception:
        return None

def sincronizar_desde_db():
    global status_timers, heartbeats, ultimas_pcs, ultimos_pjs, usuarios_db, donaciones_db
    conn = get_db()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT server, timers, last_pc, last_pj, last_heartbeat FROM public.timers_bosses;")
            for row in cur.fetchall():
                svr = row['server']
                if row['timers']: status_timers[svr] = row['timers']
                if row['last_pc']: ultimas_pcs[svr] = row['last_pc']
                if row['last_pj']: ultimos_pjs[svr] = row['last_pj']
                if row['last_heartbeat']: heartbeats[svr] = row['last_heartbeat'].strftime("%Y-%m-%d %H:%M:%S")

            cur.execute("SELECT username, password_hash, rol, requiere_cambio_clave, creado_por FROM public.usuarios;")
            for u in cur.fetchall():
                uname = u['username'].lower()
                usuarios_db[uname] = {
                    "username": u['username'],
                    "password": u['password_hash'],
                    "rol": u.get('rol', 'encargado'),
                    "requiere_cambio": u.get('requiere_cambio_clave', False),
                    "creado_por": u.get('creado_por', 'Sistema')
                }

            cur.execute("""
                SELECT id, pj_name, tipo_donacion, cantidad, registrado_por, modificado_por,
                       to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as fecha_registro,
                       to_char(fecha_modificacion, 'YYYY-MM-DD HH24:MI:SS') as fecha_modificacion
                FROM public.donaciones ORDER BY created_at DESC;
            """)
            rows_don = cur.fetchall()
            if rows_don: donaciones_db = rows_don
        conn.close()
    except Exception:
        try: conn.close()
        except Exception: pass

sincronizar_desde_db()

# --- FUNCIÓN DE ESCANEO AUTOMÁTICO DE GOOGLE DRIVE ---

def escanear_carpeta_drive():
    """
    Consulta la carpeta pública de Drive.
    Si se configuró GOOGLE_API_KEY consulta la API oficial;
    si no, utiliza el parser del feed público.
    """
    global items_mu_db
    archivos_drive = []

    if GOOGLE_API_KEY:
        try:
            q = urllib.parse.quote(f"'{FOLDER_DRIVE_ID}' in parents and trashed=false")
            url = f"https://www.googleapis.com/drive/v3/files?q={q}&key={GOOGLE_API_KEY}&fields=files(id,name,mimeType)"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                for f in res_data.get('files', []):
                    if 'image' in f.get('mimeType', ''):
                        archivos_drive.append({"id": f['id'], "nombre": f['name']})
        except Exception as e:
            print(f"Error consultando Drive API: {e}")

    # Si no hay API KEY o falló, intenta leer el directorio web público
    if not archivos_drive:
        try:
            url_folder = f"https://drive.google.com/embeddedfolderview?id={FOLDER_DRIVE_ID}#grid"
            req = urllib.request.Request(url_folder, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                # Busca coincidencias de IDs de archivos
                ids_encontrados = set(re.findall(r'https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', html))
                for file_id in ids_encontrados:
                    archivos_drive.append({"id": file_id, "nombre": f"Item {file_id[:6]}"})
        except Exception as e:
            print(f"Error leyendo carpeta pública: {e}")

    # Incorporar los archivos encontrados que aún no estén en la base local
    items_actuales = {item.get('drive_id'): item for item in items_mu_db if item.get('drive_id')}
    nuevos_detectados = 0

    for arch in archivos_drive:
        fid = arch['id']
        if fid not in items_actuales:
            nombre_limpio = re.sub(r'\.[a-zA-Z0-9]+$', '', arch['nombre']).replace('_', ' ')
            nuevo_item = {
                "id": int(time.time() * 1000) + nuevos_detectados,
                "nombre": nombre_limpio,
                "tipo": "General",
                "tier": "Excellent",
                "base_score": "",
                "grade_score": "",
                "defense": "",
                "durability": "",
                "requisitos": {},
                "clases": ["Dark Knight", "Magic Gladiator", "Dark Lord", "Dark Wizard", "Fairy Elf", "Summoner", "Rage Fighter"],
                "opciones": ["[Auto] Item detectado desde Google Drive"],
                "bonus_excelente": [],
                "drive_id": fid
            }
            items_mu_db.insert(0, nuevo_item)
            nuevos_detectados += 1

    if nuevos_detectados > 0:
        guardar_json(ITEMS_FILE, items_mu_db)
        print(f"✅ Se detectaron y agregaron {nuevos_detectados} ítems nuevos desde Drive.")

# --- VISTAS ---

@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)

@app.route('/items')
def vista_items():
    return render_template('items.html')

# --- API DE ITEMS ---

@app.route('/api/items', methods=['GET', 'POST'])
def api_items():
    global items_mu_db
    if request.method == 'GET':
        items_mu_db = cargar_json(ITEMS_FILE, items_mu_db)
        # Escaneo no bloqueante
        try:
            escanear_carpeta_drive()
        except Exception:
            pass
        return jsonify(items_mu_db)

    if request.method == 'POST':
        data = request.json or {}
        raw_drive = data.get('drive_id', '')
        match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', raw_drive)
        id_limpio = match.group(1) if match else raw_drive.strip()

        nuevo_item = {
            "id": int(time.time() * 1000),
            "nombre": data.get('nombre', 'Sin Nombre'),
            "tipo": data.get('tipo', 'General'),
            "tier": data.get('tier', 'Excellent'),
            "base_score": data.get('base_score', ''),
            "grade_score": data.get('grade_score', ''),
            "defense": data.get('defense', ''),
            "durability": data.get('durability', ''),
            "requisitos": data.get('requisitos', {}),
            "clases": data.get('clases', []),
            "opciones": data.get('opciones', []),
            "bonus_excelente": data.get('bonus_excelente', []),
            "drive_id": id_limpio
        }
        items_mu_db.insert(0, nuevo_item)
        guardar_json(ITEMS_FILE, items_mu_db)
        return jsonify({"status": "ok", "item": nuevo_item}), 201

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

# --- MAPAS INTERACTIVOS ---

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

# --- AUTENTICACIÓN ---

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

# --- DONACIONES ---

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
