import os
import time
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "multiverso_secret_key_mu_dream_2026_fixed")

# ARCHIVOS DE PERSISTENCIA
DATA_FILE = "timers_data.json"
USERS_FILE = "users_data.json"
DONACIONES_FILE = "donaciones_data.json"

LINK_DESCARGA_BOT = "https://drive.google.com/uc?export=download&id=TU_ID_DE_GOOGLE_DRIVE"

# ESTADO EN MEMORIA
status_timers = {
    "Server 1": {},
    "Server 2": {},
    "Server 3": {},
    "Server 20": {}
}

tarjetas_ocultas_global = set()
heartbeats = {}
ultimas_pcs = {}
ultimos_pjs = {}

# --- FUNCIONES DE PERSISTENCIA ---
def cargar_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando {filepath}: {e}")
    return default_val

def guardar_json(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando {filepath}: {e}")

# Cargar datos existentes
status_timers = cargar_json(DATA_FILE, status_timers)
usuarios_db = cargar_json(USERS_FILE, {})
donaciones_db = cargar_json(DONACIONES_FILE, [])


@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)


# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/login', methods=['POST'])
def login():
    global usuarios_db
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')

    # 1. CLAVE MAESTRA DE RESCATE (Funciona SIEMPRE para recuperar el control)
    if password == "super123":
        # Si el usuario no existía en la DB, lo creamos dinámicamente como Admin
        if username not in usuarios_db:
            usuarios_db[username] = {
                "password": generate_password_hash("super123"),
                "rol": "admin",
                "requiere_cambio": False,
                "creado_por": "Sistema_Rescate"
            }
            guardar_json(USERS_FILE, usuarios_db)
        
        session['user'] = username
        session['rol'] = usuarios_db[username].get("rol", "admin")
        print(f"🔓 ACCESO POR CLAVE MAESTRA CONCEDIDO A: {username}")
        return jsonify({
            "status": "ok", 
            "user": username, 
            "rol": session['rol'],
            "requiere_cambio": False
        }), 200

    # 2. VALIDACIÓN NORMAL CONTRA HASH
    if username in usuarios_db:
        stored_hash = usuarios_db[username]["password"]
        if check_password_hash(stored_hash, password):
            session['user'] = username
            session['rol'] = usuarios_db[username].get("rol", "encargado")
            return jsonify({
                "status": "ok", 
                "user": username, 
                "rol": usuarios_db[username].get("rol", "encargado"),
                "requiere_cambio": usuarios_db[username].get("requiere_cambio", False)
            }), 200
    
    return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/session')
def api_session():
    if 'user' in session:
        u_name = session['user']
        u_info = usuarios_db.get(u_name, {})
        return jsonify({
            "logged_in": True,
            "user": u_name,
            "rol": session.get('rol', u_info.get('rol', 'admin')),
            "requiere_cambio": u_info.get("requiere_cambio", False)
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
    if username in usuarios_db:
        usuarios_db[username]["password"] = generate_password_hash(nueva_clave)
        usuarios_db[username]["requiere_cambio"] = False
        guardar_json(USERS_FILE, usuarios_db)
    
    return jsonify({"status": "ok", "message": "Contraseña actualizada"}), 200


# --- RUTAS DE TIMERS Y BOTS ---

@app.route('/api/timers')
@app.route('/api/status_timers')
def get_status_timers():
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

    status_timers[server][boss] = int(time.time())
    
    clave_card = f"{server}_{boss}"
    if clave_card in tarjetas_ocultas_global:
        tarjetas_ocultas_global.remove(clave_card)

    guardar_json(DATA_FILE, status_timers)

    if pc_id != 'Manual Web':
        heartbeats[server] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ultimas_pcs[server] = pc_id
        ultimos_pjs[server] = pj_name

    return jsonify({"status": "ok", "server": server, "boss": boss}), 200

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


# --- RUTAS DE DONACIONES ---

@app.route('/api/donaciones', methods=['GET', 'POST'])
def donaciones():
    global donaciones_db

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


# --- RUTAS DE USUARIOS (SÓLO ADMIN) ---

@app.route('/api/usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'user' not in session or session.get('rol') != 'admin':
        return jsonify({"error": "Acceso denegado: requiere rol Admin"}), 403

    if request.method == 'GET':
        lista_u = []
        for u, val in usuarios_db.items():
            lista_u.append({
                "username": u,
                "rol": val.get("rol", "encargado"),
                "requiere_cambio_clave": val.get("requiere_cambio", False),
                "creado_por": val.get("creado_por", "Sistema")
            })
        return jsonify(lista_u)

    if request.method == 'POST':
        data = request.json or {}
        new_user = data.get('username', '').strip().lower()
        new_pass = data.get('password', '')
        new_rol = data.get('rol', 'encargado')

        if not new_user or not new_pass:
            return jsonify({"error": "Faltan campos obligatorios"}), 400

        if new_user in usuarios_db:
            return jsonify({"error": "El usuario ya existe"}), 400

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
