import os
import time
import json
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "multiverso_secret_key_2026")

DATABASE_URL = os.environ.get("DATABASE_URL")
LINK_DESCARGA_BOT = "https://drive.google.com/uc?export=download&id=TU_ID_DE_GOOGLE_DRIVE"

DATA_FILE = "timers_data.json"
USERS_FILE = "users_data.json"
DONACIONES_FILE = "donaciones_data.json"
MAPAS_FILE = "mapas_data.json"
ITEMS_FILE = "items_mu_data.json"

# LISTA OFICIAL DE BOSSES DE INVASIÓN / MANUALES EXCLUSIVOS
BOSSES_MANUALES = [
    "Red Dragon", "Yellow Goblin", "Blue Goblin", 
    "Red Goblin", "Santa", "White Wizard", "Skeleton King"
]

def cargar_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error leyendo {filepath}: {e}")
    return default_val


def guardar_json(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando {filepath}: {e}")


# MEMORIA LOCAL DE RESPALDO
status_timers = cargar_json(DATA_FILE, {
    "Server 1": {}, "Server 2": {}, "Server 3": {}, "Server 20": {}
})
status_mapas = cargar_json(MAPAS_FILE, {
    "1": {}, "2": {}, "3": {}
})
usuarios_db = cargar_json(USERS_FILE, {
    "pinion": {"password": "pass123", "rol": "admin", "requiere_cambio": False}
})
donaciones_db = cargar_json(DONACIONES_FILE, [])

# CATÁLOGO DE ITEMS POR DEFECTO
DEFAULT_ITEMS = [
    {
        "id": 1,
        "nombre": "Excellent Bronze Gloves",
        "tipo": "Gloves",
        "tier": "Excellent",
        "base_score": 7,
        "grade_score": 87,
        "defense": 21,
        "durability": "49/49",
        "requisitos": {
            "strength": 111,
            "agility": 42
        },
        "clases": ["Dark Knight", "Magic Gladiator", "Dark Lord"],
        "opciones": [
            "[Rare] Increases maximum SD +3%",
            "[Rare] Damage decrease +3%",
            "[Legendary] Critical damage resistance +8%"
        ],
        "bonus_excelente": [
            "Increases Strength +30",
            "Increases Agility +26"
        ],
        "drive_id": "TU_ID_DE_GOOGLE_DRIVE"
    }
]
items_mu_db = cargar_json(ITEMS_FILE, DEFAULT_ITEMS)

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
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=3)
        return conn
    except Exception as e:
        print(f"Advertencia DB (operando en modo local): {e}")
        return None


def sincronizar_desde_db():
    global status_timers, heartbeats, ultimas_pcs, ultimos_pjs, usuarios_db, donaciones_db
    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                # 1. Timers
                cur.execute("SELECT server, timers, last_pc, last_pj, last_heartbeat FROM public.timers_bosses;")
                for row in cur.fetchall():
                    svr = row['server']
                    if row['timers']:
                        status_timers[svr] = row['timers']
                    if row['last_pc']:
                        ultimas_pcs[svr] = row['last_pc']
                    if row['last_pj']:
                        ultimos_pjs[svr] = row['last_pj']
                    if row['last_heartbeat']:
                        heartbeats[svr] = row['last_heartbeat'].strftime("%Y-%m-%d %H:%M:%S")

                # 2. Usuarios
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

                # 3. Donaciones
                cur.execute("""
                    SELECT id, pj_name, tipo_donacion, cantidad, registrado_por, modificado_por,
                           to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as fecha_registro,
                           to_char(fecha_modificacion, 'YYYY-MM-DD HH24:MI:SS') as fecha_modificacion
                    FROM public.donaciones ORDER BY created_at DESC;
                """)
                rows_don = cur.fetchall()
                if rows_don:
                    donaciones_db = rows_don

            conn.close()
            print("✅ Datos cargados y sincronizados desde Supabase.")
        except Exception as e:
            print(f"Error en sincronización DB: {e}")
            if conn: conn.close()


sincronizar_desde_db()


@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)


# --- VISTA Y API DE ITEMS MU ONLINE ---

@app.route('/items')
def vista_items():
    return render_template('items.html')


@app.route('/api/items', methods=['GET', 'POST'])
def api_items():
    global items_mu_db
    if request.method == 'GET':
        return jsonify(items_mu_db)

    if request.method == 'POST':
        if 'user' not in session or session.get('rol') != 'admin':
            return jsonify({"error": "No autorizado"}), 403

        data = request.json or {}
        nuevo_item = {
            "id": int(time.time() * 1000),
            "nombre": data.get('nombre'),
            "tipo": data.get('tipo', 'General'),
            "tier": data.get('tier', 'Excellent'),
            "base_score": data.get('base_score', 0),
            "grade_score": data.get('grade_score', 0),
            "defense": data.get('defense', 0),
            "durability": data.get('durability', '-'),
            "requisitos": data.get('requisitos', {}),
            "clases": data.get('clases', []),
            "opciones": data.get('opciones', []),
            "bonus_excelente": data.get('bonus_excelente', []),
            "drive_id": data.get('drive_id')
        }
        items_mu_db.append(nuevo_item)
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

    if not server or not boss_raw:
        return jsonify({"error": "Faltan datos"}), 400

    boss = re.sub(r'\s+\d+$', '', boss_raw)

    es_manual_web = (pc_id == 'Manual Web') or ('user' in session)
    if boss in BOSSES_MANUALES and not es_manual_web:
        return jsonify({
            "status": "ignored",
            "message": f"El boss '{boss}' es de activación manual y no se procesa vía bot automático."
        }), 200

    now_unix = int(time.time())
    clave_cartel = f"{server}_{boss}_{pj_name}"

    if pc_id != 'Manual Web':
        ultimo_registro = ultimos_kills_recientes.get(clave_cartel, 0)
        if (now_unix - ultimo_registro) < 120:
            return jsonify({
                "status": "ignored", 
                "message": f"Cartel duplicado de {boss} por {pj_name} ignorado."
            }), 200
        ultimos_kills_recientes[clave_cartel] = now_unix

    if server not in status_timers:
        status_timers[server] = {}

    status_timers[server][boss] = now_unix

    clave_card = f"{server}_{boss}"
    if clave_card in tarjetas_ocultas_global:
        tarjetas_ocultas_global.remove(clave_card)

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

    return jsonify({"status": "ok", "message": f"Kill de {boss} por {pj_name} registrado"}), 200


@app.route('/api/reset_boss', methods=['POST'])
def reset_boss():
    data = request.json or {}
    server = data.get('server')
    boss = data.get('boss')

    if server and boss:
        clave_card = f"{server}_{boss}"
        tarjetas_ocultas_global.add(clave_card)
        
        keys_a_borrar = [k for k in ultimos_kills_recientes if k.startswith(f"{server}_{boss}_")]
        for k in keys_a_borrar:
            ultimos_kills_recientes.pop(k, None)

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


# --- MAPAS INTERACTIVOS (S1, S2, S3) ---

@app.route('/api/mapa_kill', methods=['POST'])
def mapa_kill():
    data = request.json or {}
    server_num = str(data.get('server', '1'))
    spot_id = str(data.get('spot_id'))

    if not spot_id:
        return jsonify({"error": "Spot no especificado"}), 400

    if server_num not in status_mapas:
        status_mapas[server_num] = {}

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


# --- AUTENTICACIÓN Y USUARIOS ---

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
        es_valido = False
        
        if stored_pass.startswith("scrypt:") or stored_pass.startswith("pbkdf2:"):
            es_valido = check_password_hash(stored_pass, password)
        else:
            es
