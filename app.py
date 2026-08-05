import os
import json
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)
app.secret_key = "clave_secreta_mudream_donaciones_key_multiverso"

LINK_DESCARGA_BOT = "https://drive.google.com/drive/folders/1Rx1TZZl5IncOpJPLab4YnRqOEIY6iBrC?usp=sharing"

# === CREDENCIALES DE SUPABASE ===
SUPABASE_URL = "https://csdwnpkvuymtasxpujza.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzZHducGt2dXltdGFzeHB1anphIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3ODU0NDYsImV4cCI6MjEwMTM2MTQ0Nn0.IwgSW7QwoqLArOTfHYT4TyONA_57y1ELCaiQyZ3xyRg"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SERVIDORES_VALIDOS = ["Server 1", "Server 2", "Server 3", "Server 20"]

COOLDOWNS_CONFIG = {
    "Muggron 1": 180, "Muggron 2": 180,
    "Dreadhorn 1": 60, "Dreadhorn 2": 60,
    "Moltragon 1": 60, "Moltragon 2": 60,
    "Borgar": 120,
    "Kharzul 1": 420, "Kharzul 2": 420, "Kharzul 3": 420,
    "Vescrya 1": 420, "Vescrya 2": 420, "Vescrya 3": 420,
    "Muggron Barracks 1": 180, "Muggron Barracks 2": 180,
    "Muggron Crywolf 1": 180, "Muggron Crywolf 2": 180,
    "Yellow Goblin": 120, "Blue Goblin": 120, "Red Goblin": 120,
    "Red Dragon": 240, "Santa 1": 120, "Santa 2": 120,
    "White Wizard 1": 120, "White Wizard 2": 120,
    "Skeleton King 1": 120, "Skeleton King 2": 120
}

# === RUTAS DE PÁGINA WEB Y AUTENTICACIÓN ===

@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Faltan datos"}), 400

    try:
        res = supabase.table('usuarios').select('*').eq('username', username).execute()
        if res.data and len(res.data) > 0:
            user = res.data[0]
            pwd_hash = user.get('password_hash', '')
            
            es_valido = False
            try:
                if pwd_hash.startswith('pbkdf2:') or pwd_hash.startswith('scrypt:'):
                    es_valido = check_password_hash(pwd_hash, password)
                else:
                    es_valido = (pwd_hash == password)
            except Exception:
                es_valido = (pwd_hash == password)

            if es_valido:
                session['user'] = user['username']
                session['rol'] = user.get('rol', 'encargado')
                requiere_cambio = user.get('requiere_cambio_clave', False)

                return jsonify({
                    "status": "SUCCESS", 
                    "user": user['username'], 
                    "rol": user.get('rol'),
                    "requiere_cambio": requiere_cambio
                }), 200

        return jsonify({"error": "Usuario o contraseña incorrectos"}), 401
    except Exception as e:
        print(f"Error en login: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/session', methods=['GET'])
def check_session():
    user_name = session.get('user', None)
    requiere_cambio = False
    if user_name:
        res = supabase.table('usuarios').select('requiere_cambio_clave').eq('username', user_name).execute()
        if res.data and len(res.data) > 0:
            requiere_cambio = res.data[0].get('requiere_cambio_clave', False)

    return jsonify({
        "logged_in": 'user' in session,
        "user": user_name,
        "rol": session.get('rol', None),
        "requiere_cambio": requiere_cambio
    })

@app.route('/api/cambiar_clave', methods=['POST'])
def cambiar_clave():
    if 'user' not in session:
        return jsonify({"error": "No has iniciado sesión"}), 401

    data = request.get_json() or {}
    nueva_clave = data.get('nueva_clave')

    if not nueva_clave or len(nueva_clave) < 4:
        return jsonify({"error": "La contraseña debe tener al menos 4 caracteres"}), 400

    try:
        nueva_hash = generate_password_hash(nueva_clave)
        supabase.table('usuarios').update({
            'password_hash': nueva_hash,
            'requiere_cambio_clave': False
        }).eq('username', session['user']).execute()

        return jsonify({"status": "SUCCESS"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === GESTIÓN DE USUARIOS POR PARTE DEL ADMIN ===

@app.route('/api/usuarios', methods=['GET', 'POST'])
def usuarios_admin():
    if 'user' not in session or session.get('rol') != 'admin':
        return jsonify({"error": "Acceso denegado. Solo Administrador."}), 403

    if request.method == 'GET':
        try:
            res = supabase.table('usuarios').select('id, username, rol, requiere_cambio_clave, creado_por, created_at').order('created_at', desc=True).execute()
            return jsonify(res.data if res.data else []), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if request.method == 'POST':
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')
        rol = data.get('rol', 'encargado')

        if not username or not password:
            return jsonify({"error": "Faltan datos obligatorios"}), 400

        try:
            pwd_hash = generate_password_hash(password)
            supabase.table('usuarios').insert({
                'username': username,
                'password_hash': pwd_hash,
                'rol': rol,
                'requiere_cambio_clave': True, # Exigir cambio en 1er login
                'creado_por': session['user']
            }).execute()

            return jsonify({"status": "SUCCESS"}), 200
        except Exception as e:
            return jsonify({"error": f"Error o usuario ya existente: {str(e)}"}), 500

# === API STATUS Y BOTS ===

@app.route('/api/status_timers', methods=['GET'])
def status_timers():
    try:
        res = supabase.table('timers_bosses').select('*').execute()
        timers_map = {svr: {} for svr in SERVIDORES_VALIDOS}
        pcs_map = {svr: "Sin reportes" for svr in SERVIDORES_VALIDOS}
        pj_map = {svr: "Desconocido" for svr in SERVIDORES_VALIDOS}
        hb_map = {svr: None for svr in SERVIDORES_VALIDOS}

        if res.data:
            for row in res.data:
                svr = row.get('server')
                if svr in SERVIDORES_VALIDOS:
                    timers_map[svr] = row.get('timers') or {}
                    pcs_map[svr] = row.get('last_pc') or 'Sin reportes'
                    pj_map[svr] = row.get('last_pj') or 'Desconocido'
                    hb_map[svr] = row.get('last_heartbeat')

        return jsonify({
            "timers": timers_map,
            "cooldowns": COOLDOWNS_CONFIG,
            "servers": SERVIDORES_VALIDOS,
            "ultimas_pcs": pcs_map,
            "ultimos_pjs": pj_map,
            "heartbeats": hb_map
        }), 200
    except Exception as e:
        print(f"Error en status_timers: {e}")
        return jsonify({"error": str(e)}), 500

# === API KILL ===

@app.route('/api/kill', methods=['POST'])
def kill():
    data = request.get_json() or {}
    server = data.get('server')
    boss = data.get('boss')
    pc_id = data.get('pc_id', 'Navegador Web')
    pj_name = session.get('user', data.get('pj_name', 'Manual Web'))

    if not server or server not in SERVIDORES_VALIDOS or not boss:
        return jsonify({"error": "Datos incompletos"}), 400

    try:
        res = supabase.table('timers_bosses').select('timers').eq('server', server).execute()
        current_timers = {}
        if res.data and len(res.data) > 0:
            current_timers = res.data[0].get('timers') or {}

        ahora_unix = int(datetime.now(timezone.utc).timestamp())
        current_timers[boss] = ahora_unix

        supabase.table('timers_bosses').update({
            'timers': current_timers,
            'last_pc': pc_id,
            'last_pj': pj_name,
            'last_heartbeat': datetime.now(timezone.utc).isoformat()
        }).eq('server', server).execute()

        return jsonify({"status": "SUCCESS", "boss": boss, "server": server, "timestamp": ahora_unix}), 200
    except Exception as e:
        print(f"Error registrando kill: {e}")
        return jsonify({"error": str(e)}), 500

# === API HEARTBEAT ===

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    data = request.get_json() or {}
    server = data.get('server')
    pc_id = data.get('pc_id', 'Desconocido')
    pj_name = data.get('pj_name', 'Desconocido')

    if not server or server not in SERVIDORES_VALIDOS:
        return jsonify({"error": "Servidor no válido"}), 400

    try:
        ahora = datetime.now(timezone.utc).isoformat()
        supabase.table('timers_bosses').update({
            'last_pc': pc_id,
            'last_pj': pj_name,
            'last_heartbeat': ahora
        }).eq('server', server).execute()

        return jsonify({"status": "OK"}), 200
    except Exception as e:
        print(f"Error en heartbeat: {e}")
        return jsonify({"error": str(e)}), 500

# === API DONACIONES ===

@app.route('/api/donaciones', methods=['GET', 'POST'])
def donaciones():
    if request.method == 'GET':
        try:
            res = supabase.table('donaciones').select('*').order('created_at', desc=True).execute()
            return jsonify(res.data if res.data else []), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if request.method == 'POST':
        if 'user' not in session:
            return jsonify({"error": "Debes iniciar sesión para guardar donaciones"}), 401

        data = request.get_json() or {}
        pj_name = data.get('pj_name')
        tipo_donacion = data.get('tipo_donacion')
        cantidad = data.get('cantidad', 1)
        registrado_por = session.get('user', 'Encargado')

        if not pj_name or not tipo_donacion:
            return jsonify({"error": "Faltan campos"}), 400

        try:
            supabase.table('donaciones').insert({
                'pj_name': pj_name,
                'tipo_donacion': tipo_donacion,
                'cantidad': cantidad,
                'registrado_por': registrado_por
            }).execute()
            return jsonify({"status": "SUCCESS"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
