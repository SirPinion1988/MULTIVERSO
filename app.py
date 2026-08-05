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

# Memoria temporal para la X (ocultar tarjetas)
tarjetas_ocultas_global = set()


# --- CONEXIÓN A SUPABASE / POSTGRESQL ---

def get_db():
    """Conecta a la base de datos PostgreSQL de Supabase"""
    if not DATABASE_URL:
        return None
    try:
        # Asegura compatibilidad SSL requerida por Supabase
        db_url = DATABASE_URL
        if "sslmode" not in db_url:
            db_url += "?sslmode=require" if "?" not in db_url else "&sslmode=require"
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Error conectando a PostgreSQL: {e}")
        return None


@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)


# --- SISTEMA DE AUTENTICACIÓN Y USUARIOS (DESDE SUPABASE) ---

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '')

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                # Búsqueda insensible a mayúsculas/minúsculas
                cur.execute("SELECT * FROM public.usuarios WHERE LOWER(username) = %s;", (username,))
                user_row = cur.fetchone()

            conn.close()

            if user_row:
                stored_pass = user_row.get("password_hash", "")
                
                # Valida contra hash werkzeug, scrypt o clave en texto plano si existe
                es_valido = False
                if stored_pass.startswith("scrypt:") or stored_pass.startswith("pbkdf2:"):
                    es_valido = check_password_hash(stored_pass, password)
                else:
                    es_valido = (stored_pass == password)

                if es_valido:
                    session['user'] = user_row['username']
                    session['rol'] = user_row.get("rol", "encargado")
                    return jsonify({
                        "status": "ok",
                        "user": user_row['username'],
                        "rol": session['rol'],
                        "requiere_cambio": user_row.get("requiere_cambio_clave", False)
                    }), 200
        except Exception as e:
            print(f"Error en login DB: {e}")
            if conn: conn.close()

    return jsonify({"error": "Usuario o contraseña incorrectos"}), 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/api/session')
def api_session():
    if 'user' in session:
        u_name = session['user']
        conn = get_db()
        req_cambio = False
        rol = session.get('rol', 'encargado')
        
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT rol, requiere_cambio_clave FROM public.usuarios WHERE username = %s;", (u_name,))
                    u_info = cur.fetchone()
                    if u_info:
                        rol = u_info['rol']
                        req_cambio = u_info['requiere_cambio_clave']
                conn.close()
            except Exception:
                if conn: conn.close()

        return jsonify({
            "logged_in": True,
            "user": u_name,
            "rol": rol,
            "requiere_cambio": req_cambio
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
            return jsonify({"status": "ok", "message": "Contraseña actualizada"}), 200
        except Exception as e:
            if conn: conn.close()
            return jsonify({"error": "Error al actualizar clave"}), 500

    return jsonify({"error": "Error de conexión a la base de datos"}), 500


@app.route('/api/usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'user' not in session or session.get('rol') != 'admin':
        return jsonify({"error": "Acceso denegado: Requiere Administrador"}), 403

    conn = get_db()
    if not conn:
        return jsonify({"error": "Error de base de datos"}), 500

    if request.method == 'GET':
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT username, rol, requiere_cambio_clave, creado_por FROM public.usuarios ORDER BY id ASC;")
                rows = cur.fetchall()
            conn.close()
            return jsonify(rows)
        except Exception as e:
            conn.close()
            return jsonify([])

    if request.method == 'POST':
        data = request.json or {}
        new_user = data.get('username', '').strip()
        new_pass = data.get('password', '')
        new_rol = data.get('rol', 'encargado')

        if not new_user or not new_pass:
            conn.close()
            return jsonify({"error": "Faltan campos obligatorios"}), 400

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.usuarios (username, password_hash, rol, requiere_cambio_clave, creado_por) VALUES (%s, %s, %s, TRUE, %s);",
                    (new_user, generate_password_hash(new_pass), new_rol, session['user'])
                )
                conn.commit()
            conn.close()
            return jsonify({"status": "ok", "message": f"Usuario {new_user} creado"}), 201
        except Exception as e:
            conn.close()
            return jsonify({"error": "El usuario ya existe o hubo un fallo"}), 400


# --- TIMERS Y BOTS (DESDE SUPABASE) ---

@app.route('/api/status_timers')
@app.route('/api/timers')
def get_status_timers():
    timers_res = {"Server 1": {}, "Server 2": {}, "Server 3": {}, "Server 20": {}}
    heartbeats = {}
    ultimas_pcs = {}
    ultimos_pjs = {}

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT server, timers, last_pc, last_pj, last_heartbeat FROM public.timers_bosses;")
                rows = cur.fetchall()
                for row in rows:
                    svr = row['server']
                    timers_res[svr] = row['timers'] or {}
                    ultimas_pcs[svr] = row['last_pc']
                    ultimos_pjs[svr] = row['last_pj']
                    if row['last_heartbeat']:
                        heartbeats[svr] = row['last_heartbeat'].strftime("%Y-%m-%d %H:%M:%S")
            conn.close()
        except Exception as e:
            print(f"Error consultando timers DB: {e}")
            if conn: conn.close()

    return jsonify({
        "timers": timers_res,
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

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                # Obtener timers actuales del servidor
                cur.execute("SELECT timers FROM public.timers_bosses WHERE server = %s;", (server,))
                row = cur.fetchone()
                current_timers = row['timers'] if row and row['timers'] else {}

                # Actualizar tiempo del boss
                current_timers[boss] = int(time.time())

                # Reaparecer si estaba ocultado con X
                clave_card = f"{server}_{boss}"
                if clave_card in tarjetas_ocultas_global:
                    tarjetas_ocultas_global.remove(clave_card)

                # Guardar cambios
                if pc_id != 'Manual Web':
                    cur.execute("""
                        INSERT INTO public.timers_bosses (server, timers, last_pc, last_pj, last_heartbeat)
                        VALUES (%s, %s, %s, %s, NOW())
                        ON CONFLICT (server) DO UPDATE 
                        SET timers = EXCLUDED.timers, last_pc = EXCLUDED.last_pc, last_pj = EXCLUDED.last_pj, last_heartbeat = NOW();
                    """, (server, json.dumps(current_timers), pc_id, pj_name))
                else:
                    cur.execute("""
                        INSERT INTO public.timers_bosses (server, timers)
                        VALUES (%s, %s)
                        ON CONFLICT (server) DO UPDATE SET timers = EXCLUDED.timers;
                    """, (server, json.dumps(current_timers)))

                conn.commit()
            conn.close()
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"Error registrando kill: {e}")
            if conn: conn.close()

    return jsonify({"error": "Error de base de datos"}), 500


@app.route('/api/reset_boss', methods=['POST'])
def reset_boss():
    data = request.json or {}
    server = data.get('server')
    boss = data.get('boss')

    if server and boss:
        clave_card = f"{server}_{boss}"
        tarjetas_ocultas_global.add(clave_card)

        conn = get_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT timers FROM public.timers_bosses WHERE server = %s;", (server,))
                    row = cur.fetchone()
                    if row and row['timers'] and boss in row['timers']:
                        current_timers = row['timers']
                        del current_timers[boss]
                        cur.execute("UPDATE public.timers_bosses SET timers = %s WHERE server = %s;", (json.dumps(current_timers), server))
                        conn.commit()
                conn.close()
            except Exception as e:
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
                return jsonify({"status": "ok"}), 200
            except Exception as e:
                if conn: conn.close()

    return jsonify({"error": "Servidor requerido"}), 400


# --- DONACIONES (DESDE SUPABASE CON AUDITORÍA) ---

@app.route('/api/donaciones', methods=['GET', 'POST'])
def donaciones():
    conn = get_db()
    if not conn:
        return jsonify([] if request.method == 'GET' else {"error": "Error DB"}), 500

    if request.method == 'GET':
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, pj_name, tipo_donacion, cantidad, registrado_por, modificado_por,
                           to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as fecha_registro,
                           to_char(fecha_modificacion, 'YYYY-MM-DD HH24:MI:SS') as fecha_modificacion
                    FROM public.donaciones ORDER BY created_at DESC;
                """)
                rows = cur.fetchall()
            conn.close()
            return jsonify(rows)
        except Exception as e:
            conn.close()
            return jsonify([])

    if request.method == 'POST':
        if 'user' not in session:
            conn.close()
            return jsonify({"error": "No autorizado"}), 401

        data = request.json or {}
        pj_name = data.get('pj_name')
        tipo_donacion = data.get('tipo_donacion')
        cantidad = data.get('cantidad', 1)

        if not pj_name or not tipo_donacion:
            conn.close()
            return jsonify({"error": "Faltan datos de donación"}), 400

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.donaciones (pj_name, tipo_donacion, cantidad, registrado_por)
                    VALUES (%s, %s, %s, %s) RETURNING id;
                """, (pj_name, tipo_donacion, int(cantidad), session['user']))
                conn.commit()
            conn.close()
            return jsonify({"status": "ok"}), 201
        except Exception as e:
            conn.close()
            return jsonify({"error": "Error al guardar donación"}), 500


@app.route('/api/donaciones/<int:donacion_id>', methods=['PUT'])
def editar_donacion(donacion_id):
    if 'user' not in session:
        return jsonify({"error": "No autorizado"}), 401

    data = request.json or {}
    pj_name = data.get('pj_name')
    tipo_donacion = data.get('tipo_donacion')
    cantidad = data.get('cantidad')

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE public.donaciones 
                    SET pj_name = %s, tipo_donacion = %s, cantidad = %s, 
                        modificado_por = %s, fecha_modificacion = NOW()
                    WHERE id = %s;
                """, (pj_name, tipo_donacion, int(cantidad), session['user'], donacion_id))
                conn.commit()
            conn.close()
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            if conn: conn.close()

    return jsonify({"error": "Error al actualizar donación"}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
