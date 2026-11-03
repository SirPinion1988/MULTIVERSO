import os
import time
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "multiverso_secret_key_2026")

DATABASE_URL = os.environ.get("DATABASE_URL")
LINK_DESCARGA_BOT = "https://drive.google.com/uc?export=download&id=TU_ID_DE_GOOGLE_DRIVE"

# ID DE TU CARPETA DE GOOGLE DRIVE COMPARTIDA
FOLDER_DRIVE_ID = "1nSqaWKAsEc7s6BYT8xg22MoITXLT7IIK"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

DATA_FILE = "timers_data.json"
USERS_FILE = "users_data.json"
DONACIONES_FILE = "donaciones_data.json"
MAPAS_FILE = "mapas_data.json"
ITEMS_FILE = "items_mu_data.json"

BOSSES_MANUALES = [
    "Red Dragon", "Yellow Goblin", "Blue Goblin", 
    "Red Goblin", "Santa", "White Wizard", "Skeleton King"
]

def cargar_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data:
                    return data
        except Exception:
            pass
    return default_val

def guardar_json(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error guardando {filepath}: {e}")

# Memoria local
status_timers = cargar_json(DATA_FILE, {"Server 1": {}, "Server 2": {}, "Server 3": {}, "Server 20": {}})
status_mapas = cargar_json(MAPAS_FILE, {"1": {}, "2": {}, "3": {}})
usuarios_db = cargar_json(USERS_FILE, {"pinion": {"password": "pass123", "rol": "admin", "requiere_cambio": False}})
donaciones_db = cargar_json(DONACIONES_FILE, [])
items_mu_db = cargar_json(ITEMS_FILE, [])

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
        return psycopg2.connect(db_url, cursor_factory=RealDictCursor, connect_timeout=3)
    except Exception:
        return None

def sincronizar_desde_db():
    global status_timers, heartbeats, ultimas_pcs, ultimos_pjs, usuarios_db, donaciones_db
    conn = get_db()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT server, timers, last_pc, last_pj, last_heartbeat FROM public.timers_bosses;")
            for row in cur.fetchall():
                svr = row['server']
                if row['timers']: status_timers[svr] = row['timers']
                if row['last_pc']: ultimas_pcs[svr] = row['last_pc']
                if row['last_pj']: ultimos_pjs[svr] = row['last_pj']
                if row['last_heartbeat']: heartbeats[svr] = row['last_heartbeat'].strftime("%Y-%m-%d %H:%M:%S")

            cur.execute("SELECT username, password_hash, rol, requiere_cambio_clave, creado_por FROM public.usuarios;")
            for u in cur.fetchall():
                uname = u['username'].lower()
                usuarios_db[uname] = {
                    "username": u['username'],
                    "password": u['password_hash'],
                    "rol": u.get('rol', 'encargado'),
                    "requiere_cambio": u.get('requiere_cambio_clave', False),
                    "creado_por": u.get('creado_por', 'Sistema')
                }

            cur.execute("""
                SELECT id, pj_name, tipo_donacion, cantidad, registrado_por, modificado_por,
                       to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') as fecha_registro,
                       to_char(fecha_modificacion, 'YYYY-MM-DD HH24:MI:SS') as fecha_modificacion
                FROM public.donaciones ORDER BY created_at DESC;
            """)
            rows_don = cur.fetchall()
            if rows_don: donaciones_db = rows_don
        conn.close()
    except Exception:
        try: conn.close()
        except Exception: pass

sincronizar_desde_db()

# --- FUNCIÓN DE ESCANEO AUTOMÁTICO DE GOOGLE DRIVE ---

def escanear_carpeta_drive():
    """
    Consulta la carpeta pública de Drive.
    Si se configuró GOOGLE_API_KEY consulta la API oficial;
    si no, utiliza el parser del feed público.
    """
    global items_mu_db
    archivos_drive = []

    if GOOGLE_API_KEY:
        try:
            q = urllib.parse.quote(f"'{FOLDER_DRIVE_ID}' in parents and trashed=false")
            url = f"https://www.googleapis.com/drive/v3/files?q={q}&key={GOOGLE_API_KEY}&fields=files(id,name,mimeType)"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                for f in res_data.get('files', []):
                    if 'image' in f.get('mimeType', ''):
                        archivos_drive.append({"id": f['id'], "nombre": f['name']})
        except Exception as e:
            print(f"Error consultando Drive API: {e}")

    # Si no hay API KEY o falló, intenta leer el directorio web público
    if not archivos_drive:
        try:
            url_folder = f"https://drive.google.com/embeddedfolderview?id={FOLDER_DRIVE_ID}#grid"
            req = urllib.request.Request(url_folder, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                # Busca coincidencias de IDs de archivos
                ids_encontrados = set(re.findall(r'https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', html))
                for file_id in ids_encontrados:
                    archivos_drive.append({"id": file_id, "nombre": f"Item {file_id[:6]}"})
        except Exception as e:
            print(f"Error leyendo carpeta pública: {e}")

    # Incorporar los archivos encontrados que aún no estén en la base local
    items_actuales = {item.get('drive_id'): item for item in items_mu_db if item.get('drive_id')}
    nuevos_detectados = 0

    for arch in archivos_drive:
        fid = arch['id']
        if fid not in items_actuales:
            nombre_limpio = re.sub(r'\.[a-zA-Z0-9]+$', '', arch['nombre']).replace('_', ' ')
            nuevo_item = {
                "id": int(time.time() * 1000) + nuevos_detectados,
                "nombre": nombre_limpio,
                "tipo": "General",
                "tier": "Excellent",
                "base_score": "",
                "grade_score": "",
                "defense": "",
                "durability": "",
                "requisitos": {},
                "clases": ["Dark Knight", "Magic Gladiator", "Dark Lord", "Dark Wizard", "Fairy Elf", "Summoner", "Rage Fighter"],
                "opciones": ["[Auto] Item detectado desde Google Drive"],
                "bonus_excelente": [],
                "drive_id": fid
            }
            items_mu_db.insert(0, nuevo_item)
            nuevos_detectados += 1

    if nuevos_detectados > 0:
        guardar_json(ITEMS_FILE, items_mu_db)
        print(f"✅ Se detectaron y agregaron {nuevos_detectados} ítems nuevos desde Drive.")

# --- VISTAS ---

@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)

@app.route('/items')
def vista_items():
    return render_template('items.html')

# --- API DE ITEMS ---

@app.route('/api/items', methods=['GET', 'POST'])
def api_items():
    global items_mu_db
    if request.method == 'GET':
        items_mu_db = cargar_json(ITEMS_FILE, items_mu_db)
        # Escaneo no bloqueante
        try:
            escanear_carpeta_drive()
        except Exception:
            pass
        return jsonify(items_mu_db)

    if request.method == 'POST':
        data = request.json or {}
        raw_drive = data.get('drive_id', '')
        match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', raw_drive)
        id_limpio = match.group(1) if match else raw_drive.strip()

        nuevo_item = {
            "id": int(time.time() * 1000),
            "nombre": data.get('nombre', 'Sin Nombre'),
            "tipo": data.get('tipo', 'General'),
            "tier": data.get('tier', 'Excellent'),
            "base_score": data.get('base_score', ''),
            "grade_score": data.get('grade_score', ''),
            "defense": data.get('defense', ''),
            "durability": data.get('durability', ''),
            "requisitos": data.get('requisitos', {}),
            "clases": data.get('clases', []),
            "opciones": data.get('opciones', []),
            "bonus_excelente": data.get('bonus_excelente', []),
            "drive_id": id_limpio
        }
        items_mu_db.insert(0, nuevo_item)
        guardar_json(ITEMS_FILE, items_mu_db)
        return jsonify({"status": "ok", "item": nuevo_item}), 201

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

    if not server or not boss_raw: return jsonify({"error": "Faltan datos
