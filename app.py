import os
import time
import json
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "multiverso_secret_key_2026")

DATABASE_URL = os.environ.get("DATABASE_URL")
LINK_DESCARGA_BOT = "https://drive.google.com/uc?export=download&id=TU_ID_DE_GOOGLE_DRIVE"

DATA_FILE = "timers_data.json"
MAPAS_FILE = "mapas_data.json"

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
    rol = session.get('rol', '').lower()
    return usr == 'pinion' or rol == 'admin'

@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)

@app.route('/items')
def vista_items():
    return render_template('items.html')

# --- BACKUP LOCAL ---
@app.route('/api/backup/exportar', methods=['GET'])
def exportar_backup():
    if not usuario_es_admin():
        return jsonify({"error": "No autorizado."}), 403
    conn = get_db()
    backup_data = {}
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM public.items_mu;")
                backup_data['items_mu'] = cur.fetchall()
                cur.execute("SELECT * FROM public.miembros_clan;")
                backup_data['miembros_clan'] = cur.fetchall()
                cur.execute("SELECT * FROM public.donaciones_joyas;")
                backup_data['donaciones_joyas'] = cur.fetchall()
                cur.execute("SELECT * FROM public.asistencias_invasiones;")
                backup_data['asistencias_invasiones'] = cur.fetchall()
                cur.execute("SELECT * FROM public.guild_gastos;")
                backup_data['guild_gastos'] = cur.fetchall()
                cur.execute("SELECT id, username, rol, activo FROM public.usuarios;")
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
        return jsonify({"error": "No autorizado."}), 403
    if 'file' not in request.files:
        return jsonify({"error": "No se adjuntó archivo."}), 400
    try:
        backup_data = json.load(request.files['file'])
    except Exception as e:
        return jsonify({"error": f"JSON inválido: {str(e)}"}), 400

    conn = get_db()
    if not conn: return jsonify({"error": "Sin conexión a DB."}), 500
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
                        json.dumps(normalizar_campo_json(itm.get('clases'), [])),
                        json.dumps(normalizar_campo_json(itm.get('opciones'), [])),
                        json.dumps(normalizar_campo_json(itm.get('bonus_excelente'), [])),
                        itm.get('drive_id', ''), itm.get('asignado_a')
                    ))
            if 'miembros_clan' in backup_data:
                cur.execute("DELETE FROM public.miembros_clan;")
                for m in backup_data['miembros_clan']:
                    cur.execute("""
                        INSERT INTO public.miembros_clan (id, nombre_pj, raza, items_asignados, notas)
                        VALUES (%s, %s, %s, %s, %s);
                    """, (m.get('id'), m.get('nombre_pj'), m.get('raza'), json.dumps(normalizar_campo_json(m.get('items_asignados'), [])), m.get('notas', '')))
            if 'donaciones_joyas' in backup_data:
                cur.execute("DELETE FROM public.donaciones_joyas;")
                for d in backup_data['donaciones_joyas']:
                    cur.execute("""
                        INSERT INTO public.donaciones_joyas (id, pj_name, bless, soul, life, chaos, creation, zen, registrado_por, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (d.get('id'), d.get('pj_name'), d.get('bless', 0), d.get('soul', 0), d.get('life', 0), d.get('chaos', 0), d.get('creation', 0), d.get('zen', 0), d.get('registrado_por', 'Sistema'), d.get('created_at')))
            if 'asistencias_invasiones' in backup_data:
                cur.execute("DELETE FROM public.asistencias_invasiones;")
                for a in backup_data['asistencias_invasiones']:
                    cur.execute("""
                        INSERT INTO public.asistencias_invasiones (id, pj_name, cantidad, registrado_por)
                        VALUES (%s, %s, %s, %s);
                    """, (a.get('id'), a.get('pj_name'), a.get('cantidad', 1), a.get('registrado_por', 'Sistema')))
            if 'guild_gastos' in backup_data:
                cur.execute("DELETE FROM public.guild_gastos;")
                for g in backup_data['guild_gastos']:
                    cur.execute("""
                        INSERT INTO public.guild_gastos (id, motivo, bless, soul, life, chaos, creation, zen, registrado_por, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (g.get('id'), g.get('motivo'), g.get('bless', 0), g.get('soul', 0), g.get('life', 0), g.get('chaos', 0), g.get('creation', 0), g.get('zen', 0), g.get('registrado_por', 'Sistema'), g.get('created_at')))
            conn.commit()
        conn.close()
    except Exception as e:
        if conn: conn.close()
        return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok"}), 200

# --- API ASISTENCIAS RANKING ---
@app.route('/api/asistencias-ranking', methods=['GET', 'POST'])
def api_asistencias_ranking():
    conn = get_db()
    if request.method == 'GET':
        ranking = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT pj_name, SUM(cantidad) as total_asistencias
                        FROM public.asistencias_invasiones
                        GROUP BY pj_name
                        ORDER BY total_asistencias DESC;
                    """)
                    ranking = cur.fetchall()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify(ranking)

    if not usuario_es_autorizado(): return jsonify({"error": "No autorizado."}), 403
    data = request.json or {}
    pj_name = data.get('pj_name', '').strip()
    delta = int(data.get('delta', 1))

    if not pj_name: return jsonify({"error": "Falta PJ"}), 400

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.asistencias_invasiones (pj_name, cantidad, registrado_por)
                    VALUES (%s, %s, %s);
                """, (pj_name, delta, session.get('user', 'Sistema')))
                conn.commit()
            conn.close()
        except Exception as e:
            if conn: conn.close()
            return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok"}), 201

# --- API DONACIONES JOYAS Y BANCO GUILD ---
@app.route('/api/donaciones-joyas', methods=['GET', 'POST'])
def api_donaciones_joyas():
    conn = get_db()
    if request.method == 'GET':
        registros = []
        banco_total = {"bless": 0, "soul": 0, "life": 0, "chaos": 0, "creation": 0, "zen": 0}
        gastos_total = {"bless": 0, "soul": 0, "life": 0, "chaos": 0, "creation": 0, "zen": 0}
        gastos_lista = []
        
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, pj_name, bless, soul, life, chaos, creation, zen, registrado_por, created_at FROM public.donaciones_joyas ORDER BY created_at DESC;")
                    registros = cur.fetchall()

                    cur.execute("SELECT SUM(bless) as bless, SUM(soul) as soul, SUM(life) as life, SUM(chaos) as chaos, SUM(creation) as creation, SUM(zen) as zen FROM public.donaciones_joyas;")
                    t = cur.fetchone()
                    if t:
                        banco_total = {k: (t[k] or 0) for k in banco_total}

                    cur.execute("SELECT id, motivo, bless, soul, life, chaos, creation, zen, registrado_por, created_at FROM public.guild_gastos ORDER BY created_at DESC;")
                    gastos_lista = cur.fetchall()

                    cur.execute("SELECT SUM(bless) as bless, SUM(soul) as soul, SUM(life) as life, SUM(chaos) as chaos, SUM(creation) as creation, SUM(zen) as zen FROM public.guild_gastos;")
                    g = cur.fetchone()
                    if g:
                        gastos_total = {k: (g[k] or 0) for k in gastos_total}

                conn.close()
            except Exception:
                if conn: conn.close()

        banco_neto = {k: banco_total[k] - gastos_total[k] for k in banco_total}
        return jsonify({"donaciones": registros, "banco_guild": banco_neto, "gastos": gastos_lista})

    if not usuario_es_autorizado(): return jsonify({"error": "No autorizado."}), 403
    data = request.json or {}
    pj_name = data.get('pj_name', '').strip()
    if not pj_name: return jsonify({"error": "Falta PJ"}), 400

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.donaciones_joyas (pj_name, bless, soul, life, chaos, creation, zen, registrado_por)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    pj_name,
                    int(data.get('bless', 0)),
                    int(data.get('soul', 0)),
                    int(data.get('life', 0)),
                    int(data.get('chaos', 0)),
                    int(data.get('creation', 0)),
                    int(data.get('zen', 0)),
                    session.get('user', 'Sistema')
                ))
                conn.commit()
            conn.close()
        except Exception as e:
            if conn: conn.close()
            return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok"}), 201

# --- API GASTOS GUILD ---
@app.route('/api/guild-gastos', methods=['POST'])
def api_guild_gastos():
    if not usuario_es_autorizado(): return jsonify({"error": "No autorizado."}), 403
    data = request.json or {}
    motivo = data.get('motivo', '').strip()
    if not motivo: return jsonify({"error": "Falta motivo"}), 400

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO public.guild_gastos (motivo, bless, soul, life, chaos, creation, zen, registrado_por)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    motivo,
                    int(data.get('bless', 0)),
                    int(data.get('soul', 0)),
                    int(data.get('life', 0)),
                    int(data.get('chaos', 0)),
                    int(data.get('creation', 0)),
                    int(data.get('zen', 0)),
                    session.get('user', 'Sistema')
                ))
                conn.commit()
            conn.close()
        except Exception as e:
            if conn: conn.close()
            return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok"}), 201

# --- API ITEMS ---
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
                    try: target_id = int(custom_id)
                    except ValueError: return jsonify({"error": "ID inválido."}), 400
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

@app.route('/api/items/editar', methods=['POST'])
def editar_item():
    if not usuario_es_autorizado(): return jsonify({"error": "No autorizado."}), 403
    data = request.json or {}
    old_id = data.get('old_id')
    new_id = data.get('new_id')
    nombre = data.get('nombre')
    tipo = data.get('tipo')
    opciones = data.get('opciones', [])
    asignado_a = data.get('asignado_a') or None

    if not old_id or not nombre: return jsonify({"error": "Faltan datos."}), 400
    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                if str(old_id) != str(new_id):
                    cur.execute("SELECT id FROM public.items_mu WHERE id = %s;", (new_id,))
                    if cur.fetchone(): return jsonify({"error": f"ID #{new_id} ya está en uso."}), 400
                cur.execute("""
                    UPDATE public.items_mu 
                    SET id = %s, nombre = %s, tipo = %s, opciones = %s, asignado_a = %s, archivo_id = %s
                    WHERE id = %s;
                """, (new_id, nombre, tipo, json.dumps(opciones), asignado_a, f"{new_id}.png", old_id))
                conn.commit()
            conn.close()
        except Exception as e:
            if conn: conn.close()
            return jsonify({"error": str(e)}), 500
    return jsonify({"status": "ok"}), 200

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
                    filas = cur.fetchall()
                    for r in filas:
                        items.append({
                            "id": r['id'],
                            "archivo_id": r.get('archivo_id') or str(r['id']),
                            "nombre": r.get('nombre') or 'Sin Nombre',
                            "tipo": r.get('tipo') or 'Armor',
                            "clases": normalizar_campo_json(r.get('clases'), []),
                            "opciones": normalizar_campo_json(r.get('opciones'), []),
                            "asignado_a": r.get('asignado_a')
                        })
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

# --- API USUARIOS ---
@app.route('/api/usuarios', methods=['GET', 'POST', 'PUT', 'DELETE'])
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
                    cur.execute("SELECT id, username, rol, activo FROM public.usuarios ORDER BY id ASC;")
                    usrs = cur.fetchall()
                conn.close()
            except Exception: pass
        return jsonify(usrs)
        
    data = request.json or {}
    if request.method == 'POST':
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        rol = data.get('rol', 'lector').strip()
        activo = data.get('activo', True)
        
        if not username: return jsonify({"error": "Falta usuario"}), 400
        if not es_pinion and rol != 'lector': return jsonify({"error": "Solo Pinion puede asignar roles elevados."}), 403
        
        if conn:
            try:
                with conn.cursor() as cur:
                    if password:
                        cur.execute("""
                            INSERT INTO public.usuarios (username, password_hash, rol, activo) 
                            VALUES (%s, %s, %s, %s) 
                            ON CONFLICT (username) DO UPDATE 
                            SET rol = EXCLUDED.rol, password_hash = EXCLUDED.password_hash, activo = EXCLUDED.activo;
                        """, (username, password, rol, activo))
                    else:
                        cur.execute("""
                            UPDATE public.usuarios SET rol = %s, activo = %s WHERE username = %s;
                        """, (rol, activo, username))
                    conn.commit()
                conn.close()
            except Exception as e: return jsonify({"error": str(e)}), 500
        return jsonify({"status": "ok"}), 201

    if request.method == 'PUT':
        if not es_pinion: return jsonify({"error": "Solo Pinion."}), 403
        uid = data.get('id')
        activo = data.get('activo')
        rol = data.get('rol')
        
        if conn:
            try:
                with conn.cursor() as cur:
                    if activo is not None:
                        cur.execute("UPDATE public.usuarios SET activo = %s WHERE id = %s;", (activo, uid))
                    if rol is not None:
                        cur.execute("UPDATE public.usuarios SET rol = %s WHERE id = %s;", (rol, uid))
                    conn.commit()
                conn.close()
            except Exception as e: return jsonify({"error": str(e)}), 500
        return jsonify({"status": "ok"}), 200

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

# --- API MIEMBROS ---
@app.route('/api/miembros', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_miembros():
    conn = get_db()
    if request.method == 'GET':
        miembros = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, nombre_pj, raza, items_asignados, notas FROM public.miembros_clan ORDER BY id ASC;")
                    filas = cur.fetchall()
                    for r in filas:
                        miembros.append({
                            "id": r['id'],
                            "nombre_pj": r['nombre_pj'],
                            "raza": r['raza'],
                            "items_asignados": normalizar_campo_json(r['items_asignados'], []),
                            "notas": r.get('notas', '')
                        })
                conn.close()
            except Exception: pass
        return jsonify(miembros)
        
    if not usuario_es_autorizado(): return jsonify({"error": "No autorizado."}), 403
    data = request.json or {}
    
    if request.method == 'POST': # Crear miembro y usuario automático (nick+123)
        nombre_pj = data.get('nombre_pj', '').strip()
        raza = data.get('raza', 'DK').strip()
        if not nombre_pj: return jsonify({"error": "Falta nick"}), 400
        
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO public.miembros_clan (nombre_pj, raza) VALUES (%s, %s) ON CONFLICT (nombre_pj) DO UPDATE SET raza = EXCLUDED.raza;", (nombre_pj, raza))
                    
                    pass_inicial = nombre_pj + "123"
                    cur.execute("""
                        INSERT INTO public.usuarios (username, password_hash, rol, activo)
                        VALUES (%s, %s, 'lector', TRUE)
                        ON CONFLICT (username) DO NOTHING;
                    """, (nombre_pj, pass_inicial))
                    
                    conn.commit()
                conn.close()
            except Exception as e: return jsonify({"error": str(e)}), 500
        return jsonify({"status": "ok"}), 201

    if request.method == 'PUT': # Editar Nick o Raza del miembro
        m_id = data.get('id')
        nuevo_nombre = data.get('nombre_pj', '').strip()
        nueva_raza = data.get('raza', '').strip()
        
        if not m_id or not nuevo_nombre: return jsonify({"error": "Faltan datos"}), 400
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT nombre_pj FROM public.miembros_clan WHERE id = %s;", (m_id,))
                    row_old = cur.fetchone()
                    if row_old:
                        viejo_nombre = row_old['nombre_pj']
                        cur.execute("UPDATE public.miembros_clan SET nombre_pj = %s, raza = %s WHERE id = %s;", (nuevo_nombre, nueva_raza, m_id))
                        if viejo_nombre != nuevo_nombre:
                            cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE asignado_a = %s;", (nuevo_nombre, viejo_nombre))
                    conn.commit()
                conn.close()
            except Exception as e: return jsonify({"error": str(e)}), 500
        return jsonify({"status": "ok"}), 200

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
                cur.execute("SELECT username, password_hash, rol, activo FROM public.usuarios WHERE LOWER(username) = %s;", (username,))
                user_db = cur.fetchone()
            conn.close()
        except Exception: pass
        
    if not user_db:
        if username == 'pinion' and password == 'G1nt0n1c': user_db = {'username': 'Pinion', 'rol': 'admin', 'activo': True}
        elif username == 'tolkien' and password == 'tolkien123': user_db = {'username': 'tolkien', 'rol': 'operador', 'activo': True}
        elif username == 'nasda' and password == 'nasda123': user_db = {'username': 'nasda', 'rol': 'operador', 'activo': True}
        
    if user_db:
        if user_db.get('activo') is False:
            return jsonify({"error": "Tu cuenta se encuentra suspendida."}), 403
            
        if user_db.get('password_hash') == password:
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
    return jsonify({"timers": status_timers, "ocultos": list(tarjetas_ocultas_global) if 'tarjetas_ocultas_global' in globals() else [], "heartbeats": heartbeats, "ultimas_pcs": ultimas_pcs, "ultimos_pjs": ultimos_pjs, "mapas": status_mapas})

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
