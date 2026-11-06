import os
import time
import json
import re
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "multiverso_secret_key_2026")

DATABASE_URL = os.environ.get("DATABASE_URL")
LINK_DESCARGA_BOT = "https://drive.google.com/uc?export=download&id=TU_ID_DE_GOOGLE_DRIVE"
FOLDER_DRIVE_ID = os.environ.get("DRIVE_FOLDER_ID", "1nSqaWKAsEc7s6BYT8xg22MoITXLT7IIK")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "AIzaSyDA99w81Z7LDtsA-gX_MmZLdVDFxmqEmlk")

DATA_FILE = "timers_data.json"
USERS_FILE = "users_data.json"
DONACIONES_FILE = "donaciones_data.json"
MAPAS_FILE = "mapas_data.json"
MIEMBROS_FILE = "miembros_data.json"

BOSSES_MANUALES = [
    "Red Dragon", "Yellow Goblin", "Blue Goblin", 
    "Red Goblin", "Santa", "White Wizard", "Skeleton King"
]

PALABRAS_ARMAS = [
    "sword", "blade", "staff", "crossbow", "bow", "stick", "book", 
    "claw", "scepter", "mace", "morning star", "axe", "spear", "dread", "two-hand"
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
usuarios_db = cargar_json(USERS_FILE, {})
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
    return session['user'].lower() in ['pinion', 'tolkien', 'nasda']

def es_solo_armadura(nombre, archivo_id):
    texto = f"{nombre} {archivo_id}".lower()
    return not any(w in texto for w in PALABRAS_ARMAS)

@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)

@app.route('/items')
def vista_items():
    return render_template('items.html')

# --- CONSULTA DIRECTA DE ITEMS (SIN PROCESAMIENTOS PESADOS) ---
@app.route('/api/items', methods=['GET', 'PUT'])
def api_items():
    conn = get_db()
    if request.method == 'GET':
        items_formateados = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, archivo_id, nombre, tipo, base_score, defense, durability,
                               clases, opciones, bonus_excelente, drive_id, asignado_a
                        FROM public.items_mu
                        ORDER BY 
                            NULLIF(regexp_replace(archivo_id, '\D', '', 'g'), '')::numeric ASC NULLS LAST,
                            id ASC;
                    """)
                    filas = cur.fetchall()
                    for r in filas:
                        nom = r.get('nombre') or 'Sin Nombre'
                        arch = r.get('archivo_id') or str(r['id'])
                        if not es_solo_armadura(nom, arch):
                            continue
                        items_formateados.append({
                            "id": r['id'],
                            "archivo_id": arch,
                            "nombre": nom,
                            "tipo": r.get('tipo') or 'Armor',
                            "base_score": r.get('base_score') or 0,
                            "defense": r.get('defense') or 0,
                            "durability": r.get('durability') or '-',
                            "clases": normalizar_campo_json(r.get('clases'), []),
                            "opciones": normalizar_campo_json(r.get('opciones'), []),
                            "bonus_excelente": normalizar_campo_json(r.get('bonus_excelente'), []),
                            "drive_id": r.get('drive_id') or '',
                            "asignado_a": r.get('asignado_a')
                        })
                conn.close()
            except Exception:
                try: conn.close()
                except Exception: pass

        # Si la base de datos aún no tiene registros, sincroniza los archivos de Drive de inmediato
        if not items_formateados:
            items_formateados = sincronizar_drive_directo()

        return jsonify(items_formateados)

    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado"}), 403

    if request.method == 'PUT':
        data = request.json or {}
        item_id = data.get('id')
        asignado_a = data.get('asignado_a')

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE id = %s;", (asignado_a, item_id))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

# --- SINCRONIZACIÓN AUTOMÁTICA DIRECTA DE METADATOS DE DRIVE ---
def sincronizar_drive_directo():
    if not FOLDER_DRIVE_ID or not GOOGLE_API_KEY:
        return []

    archivos_detectados = []
    try:
        page_token = None
        q = f"'{FOLDER_DRIVE_ID}' in parents and trashed=false"
        while True:
            url = f"https://www.googleapis.com/drive/v3/files?q={requests.utils.quote(q)}&key={GOOGLE_API_KEY}&fields=nextPageToken,files(id,name,mimeType)&pageSize=100"
            if page_token:
                url += f"&pageToken={page_token}"
            res = requests.get(url, timeout=7)
            if res.status_code == 200:
                data = res.json()
                for f in data.get('files', []):
                    nombre = f.get('name', '')
                    if 'image' in f.get('mimeType', '') or any(nombre.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                        archivos_detectados.append({"id": f['id'], "name": nombre})
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
            else:
                break
    except Exception as e:
        print(f"Error listando Drive: {e}")

    conn = get_db()
    items_retorno = []

    for idx, arch in enumerate(archivos_detectados):
        fid = arch['id']
        fname = arch['name']
        num_match = re.search(r'\d+', fname)
        num_val = int(num_match.group(0)) if num_match else idx + 2
        nombre_item = f"Armadura #{num_val}"

        if not es_solo_armadura(nombre_item, fname):
            continue

        item_dict = {
            "id": num_val,
            "archivo_id": fname,
            "nombre": nombre_item,
            "tipo": "Armor",
            "base_score": 0, "defense": 0, "durability": "-",
            "clases": ["Dark Knight", "Dark Wizard", "Elf", "Magic Gladiator", "Dark Lord", "Summoner", "Rage Fighter"],
            "opciones": ["[Auto] Captura sincronizada de Drive"],
            "bonus_excelente": [],
            "drive_id": fid,
            "asignado_a": None
        }
        items_retorno.append(item_dict)

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.items_mu (archivo_id, nombre, tipo, clases, opciones, bonus_excelente, drive_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (drive_id) DO NOTHING;
                    """, (
                        fname,
                        nombre_item,
                        "Armor",
                        json.dumps(item_dict["clases"]),
                        json.dumps(item_dict["opciones"]),
                        json.dumps(item_dict["bonus_excelente"]),
                        fid
                    ))
                    conn.commit()
            except Exception: pass

    if conn: conn.close()
    
    # Ordenar numéricamente del menor al mayor (del ID 2 en adelante)
    items_retorno.sort(key=lambda x: int(re.search(r'\d+', x['archivo_id']).group(0)) if re.search(r'\d+', x['archivo_id']) else 999999)
    return items_retorno

# --- API DE MIEMBROS DEL CLAN ---
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
        return jsonify({"error": "No autorizado. Inicia sesión como Pinion, tolkien o nasda."}), 403

    if request.method == 'POST':
        data = request.json or {}
        nombre_pj = data.get('nombre_pj', '').strip()
        raza = data.get('raza', 'Dark Knight').strip()
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

                    cur.execute("UPDATE public.items_mu SET asignado_a = NULL WHERE asignado_a = %s;", (nombre_pj,))
                    for arch_id in items_asignados:
                        cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE archivo_id = %s OR CAST(id AS TEXT) = %s;", (nombre_pj, str(arch_id), str(arch_id)))

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
                    cur.execute("DELETE FROM public.miembros_clan WHERE id = %s;", (m_id,))
                    if nombre_pj:
                        cur.execute("UPDATE public.items_mu SET asignado_a = NULL WHERE asignado_a = %s;", (nombre_pj,))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

# Importación masiva desde Excel
@app.route('/api/miembros/importar', methods=['POST'])
def importar_miembros_excel():
    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado"}), 403

    filas = (request.json or {}).get('filas', [])
    if not filas:
        return jsonify({"error": "No se enviaron datos"}), 400

    conn = get_db()
    for row in filas:
        pj = str(row.get('nick', '')).strip()
        raza = str(row.get('raza', 'Dark Knight')).strip()
        items_raw = str(row.get('items', '')).strip()
        items_lista = [x.strip() for x in items_raw.split(',') if x.strip()]

        if not pj: continue

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.miembros_clan (nombre_pj, raza, items_asignados)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (nombre_pj) DO UPDATE 
                        SET raza = EXCLUDED.raza, items_asignados = EXCLUDED.items_asignados;
                    """, (pj, raza, json.dumps(items_lista)))
                    
                    cur.execute("UPDATE public.items_mu SET asignado_a = NULL WHERE asignado_a = %s;", (pj,))
                    for arch_id in items_lista:
                        cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE archivo_id = %s OR CAST(id AS TEXT) = %s;", (pj, str(arch_id), str(arch_id)))
                    conn.commit()
            except Exception: pass

    if conn: conn.close()
    return jsonify({"status": "ok", "message": f"{len(filas)} filas procesadas"}), 200

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

    if not server or not boss_raw: return jsonify({"error": "Faltan datos"}), 400
    boss = re.sub(r'\s+\d+$', '', boss_raw)
    es_manual_web = (pc_id == 'Manual Web') or ('user' in session)

    if boss in BOSSES_MANUALES and not es_manual_web:
        return jsonify({"status": "ignored", "message": f"El boss '{boss}' es manual."}), 200

    now_unix = int(time.time())
    clave_cartel = f"{server}_{boss}_{pj_name}"

    if pc_id != 'Manual Web':
        ultimo_registro = ultimos_kills_recientes.get(clave_cartel, 0)
        if (now_unix - ultimo_registro) < 120:
            return jsonify({"status": "ignored", "message": "Cartel duplicado ignorado."}), 200
        ultimos_kills_recientes[clave_cartel] = now_unix

    if server not in status_timers: status_timers[server] = {}
    status_timers[server][boss] = now_unix
    clave_card = f"{server}_{boss}"
    if clave_card in tarjetas_ocultas_global: tarjetas_ocultas_global.remove(clave_card)
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

    return jsonify({"status": "ok", "message": f"Kill de {boss} registrado"}), 200

@app.route('/api/reset_boss', methods=['POST'])
def reset_boss():
    data = request.json or {}
    server = data.get('server')
    boss = data.get('boss')

    if server and boss:
        clave_card = f"{server}_{boss}"
        tarjetas_ocultas_global.add(clave_card)
        keys_a_borrar = [k for k in ultimos_kills_recientes if k.startswith(f"{server}_{boss}_")]
        for k in keys_a_borrar: ultimos_kills_recientes.pop(k, None)

        if server in status_timers and boss in status_timers[server]:
            del status_timers[server][boss]
            guardar_json(DATA_FILE, status_timers)
            conn = get_db()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE public.timers_bosses SET timers = %s WHERE server = %s;", 
                                    (json.dumps(status
