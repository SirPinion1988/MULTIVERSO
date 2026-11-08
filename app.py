import os
import time
import json
import re
import base64
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

def actualizar_asignacion_miembro_db(cur, item_id, nuevo_asignado):
    cur.execute("SELECT id, asignado_a FROM public.items_mu WHERE id = %s;", (item_id,))
    item_row = cur.fetchone()
    if not item_row: return
    
    viejo_asignado = item_row['asignado_a']
    
    if viejo_asignado and viejo_asignado != nuevo_asignado:
        cur.execute("SELECT id, nombre_pj, items_asignados FROM public.miembros_clan WHERE LOWER(nombre_pj) = LOWER(%s);", (viejo_asignado,))
        miembro_viejo = cur.fetchone()
        if miembro_viejo:
            items_arr = normalizar_campo_json(miembro_viejo['items_asignados'], [])
            items_arr = [str(x) for x in items_arr if str(x) != str(item_id)]
            cur.execute("UPDATE public.miembros_clan SET items_asignados = %s WHERE id = %s;", (json.dumps(items_arr), miembro_viejo['id']))

    if nuevo_asignado and nuevo_asignado != "Sin asignar":
        cur.execute("SELECT id, nombre_pj, items_asignados FROM public.miembros_clan WHERE LOWER(nombre_pj) = LOWER(%s);", (nuevo_asignado,))
        miembro_nuevo = cur.fetchone()
        if miembro_nuevo:
            items_arr = normalizar_campo_json(miembro_nuevo['items_asignados'], [])
            if str(item_id) not in [str(x) for x in items_arr]:
                items_arr.append(str(item_id))
                cur.execute("UPDATE public.miembros_clan SET items_asignados = %s WHERE id = %s;", (json.dumps(items_arr), miembro_nuevo['id']))

@app.route('/api/items/agregar-manual', methods=['POST'])
def agregar_item_manual():
    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado."}), 403

    data = request.json or {}
    set_base = data.get('set_base', '').strip()
    tipo = data.get('tipo', 'Armor').strip()
    baul = data.get('baul', '').strip() or 'Baúl General'
    asignado = data.get('asignado', '').strip() or None
    opciones = data.get('opciones', [])
    bonus = data.get('bonus', [])

    if not set_base:
        return jsonify({"error": "Falta seleccionar el set"}), 400

    nombre_completo = f"Excellent {set_base} {tipo} [Baúl: {baul}]"
    clases_default = ["Dark Knight", "Dark Wizard", "Elf", "Magic Gladiator", "Dark Lord", "Summoner", "Rage Fighter"]

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(id), 1) as max_id FROM public.items_mu;")
                row = cur.fetchone()
                next_id = 2 if row['max_id'] < 2 else row['max_id'] + 1
                archivo_id_gen = f"{next_id}.png"

                cur.execute("""
                    INSERT INTO public.items_mu (id, archivo_id, nombre, tipo, clases, opciones, bonus_excelente, drive_id, asignado_a)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    next_id,
                    archivo_id_gen,
                    nombre_completo,
                    tipo,
                    json.dumps(clases_default),
                    json.dumps(opciones),
                    json.dumps(bonus),
                    f"manual_drive_{next_id}",
                    asignado if asignado != "Sin asignar" else None
                ))

                if asignado and asignado != "Sin asignar":
                    actualizar_asignacion_miembro_db(cur, next_id, asignado)

                conn.commit()
            conn.close()
        except Exception as e:
            if conn: conn.close()
            return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ok"}), 201

@app.route('/api/items/eliminar', methods=['POST'])
def eliminar_item_manual():
    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado."}), 403

    data = request.json or {}
    item_id = data.get('id')
    if not item_id: return jsonify({"error": "ID requerido"}), 400

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                actualizar_asignacion_miembro_db(cur, item_id, None)
                cur.execute("DELETE FROM public.items_mu WHERE id = %s;", (item_id,))
                conn.commit()
            conn.close()
        except Exception as e:
            if conn: conn.close()
            return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ok"}), 200

@app.route('/api/items', methods=['GET', 'PUT'])
def api_items():
    conn = get_db()
    if request.method == 'GET':
        limit = request.args.get('limit', default=500, type=int)
        offset = request.args.get('offset', default=0, type=int)
        items_formateados = []
        total_items = 0

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) as total FROM public.items_mu;")
                    row_c = cur.fetchone()
                    if row_c: total_items = row_c['total']

                    cur.execute("""
                        SELECT id, archivo_id, nombre, tipo, base_score, defense, durability,
                               clases, opciones, bonus_excelente, drive_id, asignado_a
                        FROM public.items_mu
                        ORDER BY id ASC
                        LIMIT %s OFFSET %s;
                    """, (limit, offset))
                    filas = cur.fetchall()

                    for r in filas:
                        items_formateados.append({
                            "id": r['id'],
                            "archivo_id": r.get('archivo_id') or str(r['id']),
                            "nombre": r.get('nombre') or 'Sin Nombre',
                            "tipo": r.get('tipo') or 'Armor',
                            "clases": normalizar_campo_json(r.get('clases'), []),
                            "opciones": normalizar_campo_json(r.get('opciones'), []),
                            "bonus_excelente": normalizar_campo_json(r.get('bonus_excelente'), []),
                            "drive_id": r.get('drive_id') or '',
                            "asignado_a": r.get('asignado_a')
                        })
                conn.close()
            except Exception:
                if conn: conn.close()

        return jsonify({
            "items": items_formateados,
            "total": total_items,
            "has_more": (offset + len(items_formateados)) < total_items
        }), 200

    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado."}), 403

    if request.method == 'PUT':
        data = request.json or {}
        item_id = data.get('id')
        asignado_a = data.get('asignado_a')
        if asignado_a == "Sin asignar" or not asignado_a:
            asignado_a = None

        if conn:
            try:
                with conn.cursor() as cur:
                    actualizar_asignacion_miembro_db(cur, item_id, asignado_a)
                    cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE id = %s;", (asignado_a, item_id))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

@app.route('/api/usuarios', methods=['GET', 'POST', 'DELETE'])
def api_usuarios():
    # Pinion puede ver y gestionar todo; los operadores (tolkien, nasda) pueden listar y crear SOLAMENTE usuarios con rol 'lector'.
    es_pinion = usuario_es_admin()
    es_op = usuario_es_autorizado()

    if not es_pinion and not es_op:
        return jsonify({"error": "No autorizado."}), 403

    conn = get_db()
    if request.method == 'GET':
        usuarios = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, username, rol FROM public.usuarios ORDER BY id ASC;")
                    usuarios = cur.fetchall()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify(usuarios)

    data = request.json or {}
    if request.method == 'POST':
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        rol = data.get('rol', 'lector').strip()

        if not username or not password:
            if conn: conn.close()
            return jsonify({"error": "Usuario y contraseña requeridos"}), 400

        # Si no es Pinion, NO puede crear un usuario con rol operador o admin
        if not es_pinion and rol != 'lector':
            if conn: conn.close()
            return jsonify({"error": "Solo el administrador Pinion puede crear operadores."}), 403

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.usuarios (username, password_hash, rol)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (username) DO UPDATE 
                        SET password_hash = EXCLUDED.password_hash, rol = EXCLUDED.rol;
                    """, (username, password, rol))
                    conn.commit()
                conn.close()
            except Exception as e:
                if conn: conn.close()
                return jsonify({"error": str(e)}), 500
        return jsonify({"status": "ok"}), 201

    if request.method == 'DELETE':
        # Solo Pinion puede eliminar usuarios
        if not es_pinion:
            if conn: conn.close()
            return jsonify({"error": "Solo el administrador Pinion puede eliminar usuarios."}), 403

        uid = data.get('id')
        uname = data.get('username')
        if uname and uname.lower() == 'pinion':
            return jsonify({"error": "No se puede eliminar a Pinion."}), 400

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM public.usuarios WHERE id = %s OR username = %s;", (uid, uname))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

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
        return jsonify({"error": "No autorizado."}), 403

    if request.method == 'POST':
        data = request.json or {}
        nombre_pj = data.get('nombre_pj', '').strip()
        raza = data.get('raza', 'DK').strip()
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
                    
                    for item_id in items_asignados:
                        cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE id = %s;", (nombre_pj, item_id))

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
                    if nombre_pj:
                        cur.execute("UPDATE public.items_mu SET asignado_a = NULL WHERE LOWER(asignado_a) = LOWER(%s);", (nombre_pj,))
                    cur.execute("DELETE FROM public.miembros_clan WHERE id = %s;", (m_id,))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

@app.route('/api/session')
def api_session():
    if 'user' in session:
        return jsonify({
            "logged_in": True,
            "user": session['user'],
            "rol": session.get('rol', 'lector'),
            "autorizado": usuario_es_autorizado(),
            "es_admin": usuario_es_admin()
        })
    return jsonify({"logged_in": False, "autorizado": False, "es_admin": False})

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username_raw = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username_raw or not password:
        return jsonify({"error": "Completá usuario y contraseña"}), 400

    username = username_raw.lower()
    user_db = None

    conn = get_db()
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
            user_db = {'username': 'Pinion', 'rol': 'admin'}
        elif username == 'tolkien' and password == 'tolkien123':
            user_db = {'username': 'tolkien', 'rol': 'operador'}
        elif username == 'nasda' and password == 'nasda123':
            user_db = {'username': 'nasda', 'rol': 'operador'}

    if user_db:
        stored_pass = user_db.get("password_hash", "")
        es_valido = (stored_pass == password or check_password_hash(stored_pass, password) if stored_pass.startswith('scrypt:') else stored_pass == password)

        if es_valido:
            session['user'] = user_db.get('username', username_raw)
            session['rol'] = user_db.get('rol', 'lector')
            return jsonify({
                "status": "ok",
                "user": session['user'],
                "rol": session['rol'],
                "autorizado": usuario_es_autorizado(),
                "es_admin": usuario_es_admin()
            }), 200

    return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

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
    if not server or not boss_raw: return jsonify({"error": "Faltan datos"}), 400
    boss = re.sub(r'\s+\d+$', '', boss_raw)
    now_unix = int(time.time())

    if server not in status_timers: status_timers[server] = {}
    status_timers[server][boss] = now_unix
    guardar_json(DATA_FILE, status_timers)
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
