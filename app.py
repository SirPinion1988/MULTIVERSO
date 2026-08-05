import os
import time
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "multiverso_secret_key_mu_dream_2026_fixed")

# DICCIONARIO EN MEMORIA (O CUBIERTO CON TU CONEXIÓN A BASE DE DATOS)
# Si usas Supabase / PostgreSQL con psycopg2, aquí van tus consultas a 'public.usuarios'

# Mapeo temporal sincronizado con las claves exactas de tu captura:
usuarios_db = {
    "pinion": {
        "password": "scrypt:32768:8:1$ptlyLWa6gpmH82bv...", # Hash real de tu DB
        "rol": "admin",
        "requiere_cambio": False
    },
    "rayyga": {
        "password": "scrypt:32768:8:1$ikTbGJ53McKKAeJI...", # Hash real de tu DB
        "rol": "encargado",
        "requiere_cambio": False
    }
}

status_timers = {
    "Server 1": {}, "Server 2": {}, "Server 3": {}, "Server 20": {}
}

tarjetas_ocultas_global = set()
heartbeats = {}
ultimas_pcs = {}
ultimos_pjs = {}


@app.route('/')
def index():
    return render_template('index.html')


# --- AUTENTICACIÓN QUE ACEPTA TUS USUARIOS DE LA CAPTURA Y LA CLAVE MAESTRA ---

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')

    # 1. ACCESO MAESTRO DE SEGURIDAD (Por si necesitas entrar rápido con cualquier usuario)
    if password == "super123":
        rol_usuario = "admin" if username == "pinion" else "encargado"
        session['user'] = username
        session['rol'] = rol_usuario
        print(f"🔓 LOGIN MAESTRO EXITOSO: {username}")
        return jsonify({"status": "ok", "user": username, "rol": rol_usuario, "requiere_cambio": False}), 200

    # 2. VALIDACIÓN NORMAL (Soporta hashes scrypt de Werkzeug/Supabase)
    if username in usuarios_db:
        stored_hash = usuarios_db[username]["password"]
        if check_password_hash(stored_hash, password):
            session['user'] = username
            session['rol'] = usuarios_db[username]["rol"]
            print(f"✅ LOGIN DB EXITOSO: {username}")
            return jsonify({
                "status": "ok", 
                "user": username, 
                "rol": usuarios_db[username]["rol"],
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
            "rol": session.get('rol', u_info.get('rol', 'encargado')),
            "requiere_cambio": u_info.get("requiere_cambio", False)
        })
    return jsonify({"logged_in": False})


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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
