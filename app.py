import os
import time
import json
import re
import base64
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.security import check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "multiverso_secret_key_2026")

DATABASE_URL = os.environ.get("DATABASE_URL")
LINK_DESCARGA_BOT = "https://drive.google.com/uc?export=download&id=TU_ID_DE_GOOGLE_DRIVE"

DATA_FILE = "timers_data.json"
DONACIONES_FILE = "donaciones_data.json"
MAPAS_FILE = "mapas_data.json"
MIEMBROS_FILE = "miembros_data.json"

BOSSES_MANUALES = [
    "Red Dragon", "Yellow Goblin", "Blue Goblin", 
    "Red Goblin", "Santa", "White Wizard", "Skeleton King"
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
    usr = session['user'].lower()
    rol = session.get('rol', '').lower()
    return usr in ['pinion', 'tolkien', 'nasda'] or rol in ['admin', 'operador']

def usuario_es_admin():
    if 'user' not in session: return False
    usr = session['user'].lower()
    return usr == 'pinion'

@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)

@app.route('/items')
def vista_items():
    return render_template('items.html')

# --- BACKUP LOCAL (EXPORTAR / IMPORTAR) ---
@app.route('/api/backup/exportar', methods=['GET'])
def exportar_backup():
    if not usuario_es_admin():
        return jsonify({"error": "Solo el administrador Pinion puede exportar respaldos."}), 403

    conn = get_db()
    backup_data = {}
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM public.items_mu;")
                backup_data['items_mu'] = cur.fetchall()
                cur.execute("SELECT * FROM public.miembros_clan;")
                backup_data['miembros_clan'] = cur.fetchall()
                cur.execute("SELECT * FROM public.donaciones;")
                backup_data['donaciones'] = cur.fetchall()
                cur.execute("SELECT * FROM public.asistencias_invasiones;")
                backup_data['asistencias_invasiones'] = cur.fetchall()
                cur.execute("SELECT id, username, rol FROM public.usuarios;")
                backup_data['usuarios'] = cur.fetchall()
            conn.close()
        except Exception as e:
            if conn: conn.close()
            return jsonify({"error": str(e)}), 500

    backup_filepath = "multiverso_backup_db.json"
    with open(backup_filepath, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=4, ensure_ascii=False, default=str)

    return send_file(backup_filepath, as_attachment=True, download_name=f"Multiverso_Backup_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json")

@app.route('/api/backup/importar', methods=['POST'])
def importar_backup():
    if not usuario_es_admin():
        return jsonify({"error": "Solo el administrador Pinion puede restaurar respaldos."}), 403

    if 'file' not in request.files:
        return jsonify({"error": "No se adjuntó ningún archivo de respaldo."}), 400

    file = request.files['file']
    try:
        backup_data = json.load(file)
    except Exception as e:
        return jsonify({"error": f"Archivo JSON inválido: {str(e)}"}), 400

    conn = get_db()
    if not conn:
        return jsonify({"error": "Sin conexión a la base de datos."}), 500

    try:
        with conn.cursor() as cur:
            if 'items_mu' in backup_data:
                cur.execute("DELETE FROM public.items_mu;")
                for itm in backup_data['items_mu']:
                    cur.execute("""
                        INSERT INTO public.items_mu (id, archivo_id, nombre, tipo, base_score, defense, durability, clases, opciones, bonus_excelente, drive_id, asignado_a)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        itm.get('id'), itm.get('archivo_id'), itm.get('nombre'), itm.get('tipo'),
                        itm.get('base_score', 0), itm.get('defense', 0), itm.get('durability', '-'),
                        json.dumps(itm.get('clases', [])), json.dumps(itm.get('opciones', [])),
                        json.dumps(itm.get('bonus_excelente', [])), itm.get('drive_id', ''), itm.get('asignado_a')
                    ))

            if 'miembros_clan' in backup_data:
                cur.execute("DELETE FROM public.miembros_clan;")
                for m in backup_data['miembros_clan']:
                    cur.execute("""
                        INSERT INTO public.miembros_clan (id, nombre_pj, raza, items_asignados, notas)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (m.get('id'), m.get('nombre_pj'), m.get('raza'), json.dumps(m.get('items_asignados', [])), m.get('notas', '')))

            if 'donaciones' in backup_data:
                cur.execute("DELETE FROM public.donaciones;")
                for d in backup_data['donaciones']:
                    cur.execute("""
                        INSERT INTO public.donaciones (id, pj_name, tipo_donacion, cantidad, registrado_por, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s);
                    """, (d.get('id'), d.get('pj_name'), d.get('tipo_donacion'), d.get('cantidad', 1), d.get('registrado_por', 'Sistema'), d.get('created_at')))

            if 'asistencias_invasiones' in backup_data:
                cur.execute("DELETE FROM public.asistencias_invasiones;")
                for a in backup_data['asistencias_invasiones']:
                    cur.execute("""
                        INSERT INTO public.asistencias_invasiones (id, pj_name, evento, fecha, registrado_por)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (a.get('id'), a.get('pj_name'), a.get('evento'), a.get('fecha'), a.get('registrado_por', 'Sistema')))

            conn.commit()
        conn.close()
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": f"Error al restaurar base de datos: {str(e)}"}), 500

    return jsonify({"status": "ok", "message": "Respaldo restaurado con éxito."}), 200

# --- APIS DE DONACIONES Y ASISTENCIAS ---
@app.route('/api/donaciones', methods=['GET', 'POST', 'DELETE'])
def api_donaciones():
    conn = get_db()
    if request.method == 'GET':
        donaciones = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, pj_name, tipo_donacion, cantidad, registrado_por, created_at FROM public.donaciones ORDER BY created_at DESC;")
                    donaciones = cur.fetchall()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify(donaciones)

    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado."}), 403

    data = request.json or {}
    if request.method == 'POST':
        pj_name = data.get('pj_name', '').strip()
        tipo_donacion = data.get('tipo_donacion', '').strip()
        cantidad = data.get('cantidad', 1)

        if not pj_name or not tipo_donacion:
            if conn: conn.close()
            return jsonify({"error": "PJ y tipo de donación requeridos"}), 400

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.donaciones (pj_name, tipo_donacion, cantidad, registrado_por)
                        VALUES (%s, %s, %s, %s);
                    """, (pj_name, tipo_donacion, cantidad, session.get('user', 'Sistema')))
                    conn.commit()
                conn.close()
            except Exception as e:
                if conn: conn.close()
                return jsonify({"error": str(e)}), 500
        return jsonify({"status": "ok"}), 201

    if request.method == 'DELETE':
        if not usuario_es_admin():
            return jsonify({"error": "Solo el administrador Pinion puede eliminar registros."}), 403
        d_id = data.get('id')
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM public.donaciones WHERE id = %s;", (d_id,))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

@app.route('/api/asistencias', methods=['GET', 'POST', 'DELETE'])
def api_asistencias():
    conn = get_db()
    if request.method == 'GET':
        asistencias = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, pj_name, evento, fecha, registrado_por FROM public.asistencias_invasiones ORDER BY fecha DESC, id DESC;")
                    asistencias = cur.fetchall()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify(asistencias)

    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado."}), 403

    data = request.json or {}
    if request.method == 'POST':
        pj_name = data.get('pj_name', '').strip()
        evento = data.get('evento', 'Invasión').strip()
        fecha = data.get('fecha') or datetime.now().strftime('%Y-%m-%d')

        if not pj_name:
            if conn: conn.close()
            return jsonify({"error": "Nombre del PJ requerido"}), 400

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.asistencias_invasiones (pj_name, evento, fecha, registrado_por)
                        VALUES (%s, %s, %s, %s);
                    """, (pj_name, evento, fecha, session.get('user', 'Sistema')))
                    conn.commit()
                conn.close()
            except Exception as e:
                if conn: conn.close()
                return jsonify({"error": str(e)}), 500
        return jsonify({"status": "ok"}), 201

    if request.method == 'DELETE':
        if not usuario_es_admin():
            return jsonify({"error": "Solo Pinion puede eliminar registros."}), 403
        a_id = data.get('id')
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM public.asistencias_invasiones WHERE id = %s;", (a_id,))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

# --- APIS DE ITEMS (CON SOPORTE DE ID MANUAL) ---
@app.route('/api/items/agregar-manual', methods=['POST'])
def agregar_item_manual():
    if not usuario_es_autorizado(): return jsonify({"error": "No autorizado."}), 403
    data = request.json or {}
    set_base = data.get('set_base', '').strip()
    tipo = data.get('tipo', 'Armor').strip()
    baul = data.get('baul', '').strip() or 'Baúl General'
    asignado = data.get('asignado', '').strip() or None
    opciones = data.get('opciones', [])
    custom_id = data.get('custom_id')

    if not set_base: return jsonify({"error": "Falta seleccionar set"}), 400
    nombre_completo = f"Excellent {set_base} {tipo} [Baúl: {baul}]"
    clases_default = ["Dark Knight", "Dark Wizard", "Elf", "Magic Gladiator", "Dark Lord", "Summoner", "Rage Fighter"]

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                if custom_id is not None and str(custom_id).strip() != "":
                    target_id = int(custom_id)
                    cur.execute("SELECT id FROM public.items_mu WHERE id = %s;", (target_id,))
                    if cur.fetchone(): return jsonify({"error": f"ID #{target_id} ya existe."}), 400
                    next_id = target_id
                else:
                    cur.execute("SELECT COALESCE(MAX(id), 1) as max_id FROM public.items_mu;")
                    row = cur.fetchone()
                    next_id = 2 if row['max_id'] < 2 else row['max_id'] + 1

                cur.execute("""
                    INSERT INTO public.items_mu (id, archivo_id, nombre, tipo, clases, opciones, drive_id, asignado_a)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """, (next_id, f"{next_id}.png", nombre_completo, tipo, json.dumps(clases_default), json.dumps(opciones), f"manual_{next_id}", asignado if asignado != "Sin asignar" else None))
                conn.commit()
            conn.close()
        except Exception as e:
            if conn: conn.close()
            return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok"}), 201

@app.route('/api/items/eliminar', methods=['POST'])
def eliminar_item_manual():
    if not usuario_es_autorizado(): return jsonify({"error": "No autorizado."}), 403
    data = request.json or {}
    item_id = data.get('id')
    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public.items_mu WHERE id = %s;", (item_id,))
                conn.commit()
            conn.close()
        except Exception:
            if conn: conn.close()
    return jsonify({"status": "ok"}), 200

@app.route('/api/items', methods=['GET', 'PUT'])
def api_items():
    conn = get_db()
    if request.method == 'GET':
        items = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, archivo_id, nombre, tipo, clases, opciones, asignado_a FROM public.items_mu ORDER BY id ASC;")
                    items = cur.fetchall()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"items": items})

    if not usuario_es_autorizado(): return jsonify({"error": "No autorizado."}), 403
    data = request.json or {}
    item_id = data.get('id')
    asignado_a = data.get('asignado_a') or None
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE id = %s;", (asignado_a, item_id))
                conn.commit()
            conn.close()
        except Exception:
            if conn: conn.close()
    return jsonify({"status": "ok"}), 200

# --- APIS DE USUARIOS Y MIEMBROS ---
@app.route('/api/usuarios', methods=['GET', 'POST', 'DELETE'])
def api_usuarios():
    es_pinion = usuario_es_admin()
    es_op = usuario_es_autorizado()
    if not es_pinion and not es_op: return jsonify({"error": "No autorizado."}), 403
    conn = get_db()
    if request.method == 'GET':
        usrs = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, username, rol FROM public.usuarios ORDER BY id ASC;")
                    usrs = cur.fetchall()
                conn.close()
            except Exception: pass
        return jsonify(usrs)
    data = request.json or {}
    if request.method == 'POST':
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        rol = data.get('rol', 'lector').strip()
        if not es_pinion and rol != 'lector': return jsonify({"error": "Solo Pinion puede crear operadores."}), 403
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO public.usuarios (username, password_hash, rol) VALUES (%s, %s, %s) ON CONFLICT (username) DO UPDATE SET rol = EXCLUDED.rol;", (username, password, rol))
                    conn.commit()
                conn.close()
            except Exception as e: return jsonify({"error": str(e)}), 500
        return jsonify({"status": "ok"}), 201
    if request.method == 'DELETE':
        if not es_pinion: return jsonify({"error": "Solo Pinion."}), 403
        uid = data.get('id')
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM public.usuarios WHERE id = %s;", (uid,))
                    conn.commit()
                conn.close()
            except Exception: pass
        return jsonify({"status": "ok"}), 200

@app.route('/api/miembros', methods=['GET', 'POST', 'DELETE'])
def api_miembros():
    conn = get_db()
    if request.method == 'GET':
        miembros = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, nombre_pj, raza, items_asignados, notas FROM public.miembros_clan ORDER BY id ASC;")
                    miembros = cur.fetchall()
                conn.close()
            except Exception: pass
        return jsonify(miembros)
    if not usuario_es_autorizado(): return jsonify({"error": "No autorizado."}), 403
    data = request.json or {}
    if request.method == 'POST':
        nombre_pj = data.get('nombre_pj', '').strip()
        raza = data.get('raza', 'DK').strip()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO public.miembros_clan (nombre_pj, raza) VALUES (%s, %s) ON CONFLICT (nombre_pj) DO UPDATE SET raza = EXCLUDED.raza;", (nombre_pj, raza))
                    conn.commit()
                conn.close()
            except Exception: pass
        return jsonify({"status": "ok"}), 201
    if request.method == 'DELETE':
        m_id = data.get('id')
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM public.miembros_clan WHERE id = %s;", (m_id,))
                    conn.commit()
                conn.close()
            except Exception: pass
        return jsonify({"status": "ok"}), 200

@app.route('/api/session')
def api_session():
    if 'user' in session:
        return jsonify({"logged_in": True, "user": session['user'], "rol": session.get('rol', 'lector'), "autorizado": usuario_es_autorizado(), "es_admin": usuario_es_admin()})
    return jsonify({"logged_in": False, "autorizado": False, "es_admin": False})

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username', '').strip().lower()
    password = data.get('password', '').strip()
    user_db = None
    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT username, password_hash, rol FROM public.usuarios WHERE LOWER(username) = %s;", (username,))
                user_db = cur.fetchone()
            conn.close()
        except Exception: pass
    if not user_db:
        if username == 'pinion' and password == 'G1nt0n1c': user_db = {'username': 'Pinion', 'rol': 'admin'}
        elif username == 'tolkien' and password == 'tolkien123': user_db = {'username': 'tolkien', 'rol': 'operador'}
        elif username == 'nasda' and password == 'nasda123': user_db = {'username': 'nasda', 'rol': 'operador'}
    if user_db and (user_db.get('password_hash') == password):
        session['user'] = user_db.get('username')
        session['rol'] = user_db.get('rol', 'lector')
        return jsonify({"status": "ok", "user": session['user'], "rol": session['rol'], "autorizado": usuario_es_autorizado(), "es_admin": usuario_es_admin()}), 200
    return jsonify({"error": "Credenciales incorrectas"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/status_timers')
@app.route('/api/timers')
def get_status_timers():
    return jsonify({"timers": status_timers, "ocultos": list(tarjetas_ocultas_global), "heartbeats": heartbeats, "ultimas_pcs": ultimas_pcs, "ultimos_pjs": ultimos_pjs, "mapas": status_mapas})

@app.route('/api/kill', methods=['POST'])
def registrar_kill():
    data = request.json or {}
    server = data.get('server')
    boss_raw = data.get('boss', '').strip()
    if server and boss_raw:
        if server not in status_timers: status_timers[server] = {}
        status_timers[server][re.sub(r'\s+\d+$', '', boss_raw)] = int(time.time())
        guardar_json(DATA_FILE, status_timers)
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
