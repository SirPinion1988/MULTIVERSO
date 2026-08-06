import os
import time
import json
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

# Memoria local de respaldo
status_timers = cargar_json(DATA_FILE, {
    "Server 1": {}, "Server 2": {}, "Server 3": {}, "Server 20": {}
})
usuarios_db = cargar_json(USERS_FILE, {
    "pinion": {"password": "pass123", "rol": "admin", "requiere_cambio": False}
})
donaciones_db = cargar_json(DONACIONES_FILE, [])

tarjetas_ocultas_global = set()
heartbeats = {}
ultimas_pcs = {}
ultimos_pjs = {}


def get_db():
    if not DATABASE_URL:
        return None
    try:
        db_url = DATABASE_URL
        if "sslmode" not in db_url:
            db_url += "?sslmode=require" if "?" not in db_url else "&sslmode=require"
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=5)
        return conn
    except Exception as e:
        print(f"Advertencia DB: {e}")
        return None


def cargar_timers_desde_db():
    """Carga obligatoriamente los timers guardados en Supabase al iniciar"""
    global status_timers, heartbeats, ultimas_pcs, ultimos_pjs
    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT server, timers, last_pc, last_pj, last_heartbeat FROM public.timers_bosses;")
                rows = cur.fetchall()
                for row in rows:
                    svr = row['server']
                    if row['timers']:
                        status_timers[svr] = row['timers']
                    if row['last_pc']:
                        ultimas_pcs[svr] = row['last_pc']
                    if row['last_pj']:
                        ultimos_pjs[svr] = row['last_pj']
                    if row['last_heartbeat']:
                        heartbeats[svr] = row['last_heartbeat'].strftime("%Y-%m-%d %H:%M:%S")
            conn.close()
            print("✅ Timers cargados exitosamente desde Supabase.")
        except Exception as e:
            print(f"Error leyendo timers de Supabase: {e}")
            if conn: conn.close()

# CARGAR DATOS PERSISTENTES DE SUPABASE AL ARRANCAR EL SERVIDOR
cargar_timers_desde_db()


@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)


# --- TIMERS Y BOTS ---

@app.route('/api/status_timers')
@app.route('/api/timers')
def get_status_timers():
    # Intenta refrescar desde Supabase si es posible
    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT server, timers, last_pc, last_pj, last_heartbeat FROM public.timers_bosses;")
                rows = cur.fetchall()
                for row in rows:
                    svr = row['server']
                    if row['timers']:
                        status_timers[svr] = row['timers']
                    if row['last_pc']:
                        ultimas_pcs[svr] = row['last_pc']
                    if row['last_pj']:
                        ultimos_pjs[svr] = row['last_pj']
                    if row['last_heartbeat']:
                        heartbeats[svr] = row['last_heartbeat'].strftime("%Y-%m-%d %H:%M:%S")
            conn.close()
        except Exception:
            if conn: conn.close()

    return jsonify({
        "timers": status_timers,
        "ocultos": list(tarjetas_ocultas_global),
        "heartbeats": heartbeats,
        "ultimas_pcs": ultimas_pcs,
        "ultimos_pjs": ultimos_pjs
    })


@app.route('/api/kill', methods=['POST'])
def registrar_kill():
    data = request.json or {}
    server = data.get('server')
    boss = data.get('boss')
    pc_id = data.get('pc_id', 'Manual Web')
    pj_name = data.get('pj_name', 'Manual Web')

    if not server or not boss:
        return jsonify({"error": "Faltan datos"}), 400

    if server not in status_timers:
        status_timers[server] = {}

    # 1. Guardar en memoria local
    status_timers[server][boss] = int(time.time())

    clave_card = f"{server}_{boss}"
    if clave_card in tarjetas_ocultas_global:
        tarjetas_ocultas_global.remove(clave_card)

    guardar_json(DATA_FILE, status_timers)

    if pc_id != 'Manual Web':
        heartbeats[server] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ultimas_pcs[server] = pc_id
        ultimos_pjs[server] = pj_name

    # 2. Guardar permanentemente en Supabase
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
        except Exception as e:
            print(f"Error guardando kill en DB: {e}")
            if conn: conn.close()

    return jsonify({"status": "ok"}), 200


@app.route('/api/reset_boss', methods=['POST'])
def reset_boss():
    data = request.json or {}
    server = data.get('server')
    boss = data.get('boss')

    if server and boss:
        clave_card = f"{server}_{boss}"
        tarjetas_ocultas_global.add(clave_card)
        if server in status_timers and boss in status_timers[server]:
            del status_timers[server][boss]
            guardar_json(DATA_FILE, status_timers)

            conn = get_db()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE public.timers_bosses 
                            SET timers = %s 
                            WHERE server = %s;
                        """, (json.dumps(status_timers.get(server, {})), server))
                        conn.commit()
                    conn.close()
                except Exception:
                    if conn: conn.close()

        return jsonify({"status": "ok", "message": f"{boss} ocultado"}), 200

    return jsonify({"error": "Datos inválidos"}), 400


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
        return jsonify({"status": "ok"}), 200

    return jsonify({"error": "Servidor requerido"}), 400


# --- AUTENTICACIÓN Y SESIONES ---

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')

    user_info = None

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM public.usuarios WHERE LOWER(username) = %s;", (username,))
                user_info = cur.fetchone()
            conn.close()
        except Exception:
            if conn: conn.close()

    if not user_info and username in usuarios_db:
        user_info = {
            "username": username,
            "password_hash": usuarios_db[username].get("password", ""),
            "rol": usuarios_db[username].get("rol", "encargado"),
            "requiere_cambio_clave": usuarios_db[username].get("requiere_cambio", False)
        }

    if user_info:
        stored_pass = user_info.get("password_hash", "")
        es_valido = False
        
        if stored_pass.startswith("scrypt:") or stored_pass.startswith("pbkdf2:"):
            es_valido = check_password_hash(stored_pass, password)
        else:
            es_valido = (stored_pass == password)

        if es_valido:
            session['user'] = user_info['username']
            session['rol'] = user_info.get("rol", "encargado")
            return jsonify({
                "status": "ok",
                "user": user_info['username'],
                "rol": session['rol'],
                "requiere_cambio": user_info.get("requiere_cambio_clave", False)
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
    if 'user' not in session:
        return jsonify({"error": "No autorizado"}), 401

    data = request.json or {}
    nueva_clave = data.get('nueva_clave')

    if not nueva_clave or len(nueva_clave) < 4:
        return jsonify({"error": "La contraseña debe tener al menos 4 caracteres"}), 400

    username = session['user']
    new_hash = generate_password_hash(nueva_clave)

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.usuarios SET password_hash = %s, requiere_cambio_clave = FALSE WHERE username = %s;",
                    (new_hash, username)
                )
                conn.commit()
            conn.close()
        except Exception:
            if conn: conn.close()

    if username in usuarios_db:
        usuarios_db[username]["password"] = new_hash
        usuarios_db[username]["requiere_cambio"] = False
        guardar_json(USERS_FILE, usuarios_db)

    return jsonify({"status": "ok", "message": "Contraseña actualizada"}), 200


# --- DONACIONES Y USUARIOS ---

@app.route('/api/donaciones', methods=['GET', 'POST'])
def donaciones():
    if request.method == 'GET':
        return jsonify(donaciones_db)

    if request.method == 'POST':
        if 'user' not in session:
            return jsonify({"error": "No autorizado"}), 401

        data = request.json or {}
        pj_name = data.get('pj_name')
        tipo_donacion = data.get('tipo_donacion')
        cantidad = data.get('cantidad', 1)

        if not pj_name or not tipo_donacion:
            return jsonify({"error": "Faltan datos de donación"}), 400

        nueva_donacion = {
            "id": int(time.time() * 1000),
            "pj_name": pj_name,
            "tipo_donacion": tipo_donacion,
            "cantidad": int(cantidad),
            "registrado_por": session['user'],
            "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modificado_por": None,
            "fecha_modificacion": None
        }

        donaciones_db.insert(0, nueva_donacion)
        guardar_json(DONACIONES_FILE, donaciones_db)
        return jsonify({"status": "ok", "donacion": nueva_donacion}), 201


@app.route('/api/donaciones/<int:donacion_id>', methods=['PUT'])
def editar_donacion(donacion_id):
    if 'user' not in session:
        return jsonify({"error": "No autorizado"}), 401

    data = request.json or {}
    for don in donaciones_db:
        if don['id'] == donacion_id:
            don['pj_name'] = data.get('pj_name', don['pj_name'])
            don['tipo_donacion'] = data.get('tipo_donacion', don['tipo_donacion'])
            don['cantidad'] = int(data.get('cantidad', don['cantidad']))
            don['modificado_por'] = session['user']
            don['fecha_modificacion'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            guardar_json(DONACIONES_FILE, donaciones_db)
            return jsonify({"status": "ok", "donacion": don}), 200

    return jsonify({"error": "Donación no encontrada"}), 404


@app.route('/api/usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'user' not in session or session.get('rol') != 'admin':
        return jsonify({"error": "Acceso denegado"}), 403

    if request.method == 'GET':
        lista = []
        for u, val in usuarios_db.items():
            lista.append({
                "username": u,
                "rol": val.get("rol", "encargado"),
                "requiere_cambio_clave": val.get("requiere_cambio", False),
                "creado_por": val.get("creado_por", "Sistema")
            })
        return jsonify(lista)

    if request.method == 'POST':
        data = request.json or {}
        new_user = data.get('username', '').strip().lower()
        new_pass = data.get('password', '')
        new_rol = data.get('rol', 'encargado')

        if not new_user or not new_pass:
            return jsonify({"error": "Faltan campos"}), 400

        usuarios_db[new_user] = {
            "password": generate_password_hash(new_pass),
            "rol": new_rol,
            "requiere_cambio": True,
            "creado_por": session['user']
        }
        guardar_json(USERS_FILE, usuarios_db)
        return jsonify({"status": "ok", "message": f"Usuario {new_user} creado"}), 201


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
