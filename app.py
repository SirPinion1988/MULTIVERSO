import os
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "multiverso_secret_key_2026")

# Cadena de conexión a Supabase/PostgreSQL desde Render
DATABASE_URL = os.environ.get("DATABASE_URL")

# Almacenamiento en memoria para Heartbeats y Ocultado de tarjetas (✕)
status_timers = {"Server 1": {}, "Server 2": {}, "Server 3": {}, "Server 20": {}}
tarjetas_ocultas_global = set()
heartbeats = {}
ultimas_pcs = {}
ultimos_pjs = {}

def get_db_connection():
    """Conecta a la base de datos PostgreSQL de Supabase"""
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL)


@app.route('/')
def index():
    return render_template('index.html')


# --- AUTENTICACIÓN CONECTADA A SUPABASE ---

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username_input = data.get('username', '').strip()
    password_input = data.get('password', '')

    if not username_input or not password_input:
        return jsonify({"error": "Ingresa usuario y contraseña"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Error de conexión a la base de datos"}), 500

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Busca al usuario ignorando mayúsculas/minúsculas en public.usuarios
            cur.execute("SELECT * FROM public.usuarios WHERE LOWER(username) = LOWER(%s)", (username_input,))
            user = cur.fetchone()

            if user:
                stored_hash = user.get('password_hash')
                
                # Compara la clave ingresada contra el hash 'scrypt' de Supabase
                if stored_hash and check_password_hash(stored_hash, password_input):
                    session['user'] = user['username']
                    session['rol'] = user.get('rol', 'encargado')
                    
                    return jsonify({
                        "status": "ok",
                        "user": user['username'],
                        "rol": user.get('rol', 'encargado'),
                        "requiere_cambio": user.get('requiere_cambio', False)
                    }), 200

    except Exception as e:
        print(f"Error consultando usuarios en DB: {e}")
    finally:
        conn.close()

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
            "rol": session.get('rol', 'encargado')
        })
    return jsonify({"logged_in": False})


# --- RUTAS DE BOTS Y TIMERS ---

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

    # Si el boss estaba oculto con la ✕, reaparece automáticamente al registrar kill
    clave_card = f"{server}_{boss}"
    if clave_card in tarjetas_ocultas_global:
        tarjetas_ocultas_global.remove(clave_card)

    if pc_id != 'Manual Web':
        heartbeats[server] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ultimas_pcs[server] = pc_id
        ultimos_pjs[server] = pj_name

    return jsonify({"status": "ok"}), 200


@app.route('/api/reset_boss', methods=['POST'])
def reset_boss():
    """Elimina la tarjeta de la pantalla de toda la guild al presionar ✕"""
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


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
