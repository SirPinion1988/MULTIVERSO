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
FOLDER_DRIVE_ID = os.environ.get("DRIVE_FOLDER_ID", "1nSqaWKAsEc7s6BYT8xg22MoITXLT7IIK")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

DATA_FILE = "timers_data.json"
USERS_FILE = "users_data.json"
DONACIONES_FILE = "donaciones_data.json"
MAPAS_FILE = "mapas_data.json"
ITEMS_FILE = "items_mu_data.json"
MIEMBROS_FILE = "miembros_data.json"

BOSSES_MANUALES = [
    "Red Dragon", "Yellow Goblin", "Blue Goblin", 
    "Red Goblin", "Santa", "White Wizard", "Skeleton King"
]

# Respaldo en memoria garantizado
DEFAULT_ITEMS = [
    {"id": 1, "nombre": "Excellent Scale Pants", "tipo": "Pants", "base_score": 13, "defense": 48, "durability": "55/55", "clases": ["Dark Knight", "Magic Gladiator", "Dark Lord", "Rage Fighter"], "opciones": ["[Rare] Increases maximum life +3%", "[Epic] Damage decrease +5%"], "bonus_excelente": ["Increases Strength +30", "Increases Energy +31"], "drive_id": "scale_pants_img"},
    {"id": 265, "nombre": "Excellent Sphinx Armor", "tipo": "Armor", "base_score": 19, "defense": 75, "durability": "51/51", "clases": ["Dark Wizard", "Magic Gladiator"], "opciones": ["[Legendary] Increases maximum life +4%", "[Rare] Increases zen drop rate +21%"], "bonus_excelente": ["Increases Energy +50", "Increases Vitality +41"], "drive_id": "1BC0k90uaW4rHp1dQM1Y-pxLwE1KfnLku"},
    {"id": 264, "nombre": "Excellent Legendary Pants", "tipo": "Pants", "base_score": 27, "defense": 105, "durability": "57/57", "clases": ["Dark Wizard", "Magic Gladiator"], "opciones": ["[Epic] Reflect damage +5%", "[Epic] Critical damage resistance +10%"], "bonus_excelente": ["Increases Agility +98", "Increases Strength +110"], "drive_id": "1Jmjh8YltzfO2xBhBDGX0oYxr-WMdG4xK"},
    {"id": 260, "nombre": "Excellent Black Dragon Pants", "tipo": "Pants", "base_score": 42, "defense": 129, "durability": "89/89", "clases": ["Dark Knight"], "opciones": ["[Legendary] Reflect damage +4%", "[Epic] Increases zen drop rate +30%"], "bonus_excelente": ["Increases Energy +101", "Increases Strength +145"], "drive_id": "1iHHVi5Fr0KKdjWX1luSpI9CzuPAK5Aq5"},
    {"id": 258, "nombre": "Excellent Sphinx Gloves", "tipo": "Gloves", "base_score": 14, "defense": 40, "durability": "51/51", "clases": ["Dark Wizard", "Magic Gladiator"], "opciones": ["[Rare] Increases maximum life +3%", "[Legendary] Critical damage resistance +8%"], "bonus_excelente": ["Increases Vitality +58", "Increases Agility +65"], "drive_id": "1SD_eAIslC4Le3N1PuIBrF1fFB2V5mIZE"},
    {"id": 253, "nombre": "Excellent Light Plate Pants", "tipo": "Pants", "base_score": 25, "defense": 66, "durability": "57/57", "clases": ["Dark Lord"], "opciones": ["[Rare] Damage decrease +3%", "[Rare] Reflect damage +3%"], "bonus_excelente": ["Increases Vitality +52", "Increases Agility +78"], "drive_id": "134KbPtgfHsEJsso7bM7bBWeiC5qt3VY4"},
    {"id": 252, "nombre": "Excellent Bronze Helm", "tipo": "Helm", "base_score": 8, "defense": 36, "durability": "49/49", "clases": ["Dark Knight", "Dark Lord"], "opciones": ["[Rare] Reflect damage +3%", "[Legendary] Critical damage resistance +8%"], "bonus_excelente": ["Increases Strength +32", "Increases Vitality +34"], "drive_id": "1TuHbtxMsonvbMfdAvR18aO7oYJTiVWxd"},
    {"id": 250, "nombre": "Excellent Bill of Balrog", "tipo": "Weapon", "base_score": 32, "defense": 0, "durability": "100/100", "clases": ["Dark Knight", "Magic Gladiator"], "opciones": ["[Legendary] Excellent damage rate +8%", "[Epic] Damage to monsters +10%"], "bonus_excelente": ["Increases Agility +232", "Increases Vitality +239"], "drive_id": "14Ufrcc1tRoI5OD1weZ7Ag1opgm-djCIm"},
    {"id": 248, "nombre": "Excellent Legendary Shield", "tipo": "Shield", "base_score": 24, "defense": 229, "durability": "65/65", "clases": ["Dark Wizard", "Elf", "Magic Gladiator"], "opciones": ["[Rare] Increases maximum SD +3%", "[Rare] Damage decrease +3%"], "bonus_excelente": ["Increases Vitality +99", "Increases Energy +74"], "drive_id": "1uNOlQGiHDxzszBHLYFBqLra-c6Vy2Qe1"},
    {"id": 246, "nombre": "Excellent Bronze Gloves", "tipo": "Gloves", "base_score": 7, "defense": 21, "durability": "49/49", "clases": ["Dark Knight", "Magic Gladiator", "Dark Lord"], "opciones": ["[Rare] Increases maximum SD +3%", "[Rare] Damage decrease +3%", "[Legendary] Critical damage resistance +8%"], "bonus_excelente": ["Increases Strength +30", "Increases Agility +26"], "drive_id": "1u0mZvM_JmyY3NABCGCf35dj6rGVqrFHh"},
    {"id": 244, "nombre": "Excellent Book of Samut", "tipo": "Book", "base_score": 26, "defense": 0, "durability": "75/75", "clases": ["Summoner"], "opciones": ["Increases wizardry by 3%", "[Rare] Critical damage rate +7%"], "bonus_excelente": ["Increases Energy +146", "Increases Strength +200"], "drive_id": "1f5VMBmH8o4CdKIblTkW382mnxkzj7s2U"},
    {"id": 242, "nombre": "Excellent Red Winged Gloves", "tipo": "Gloves", "base_score": 22, "defense": 46, "durability": "57/57", "clases": ["Summoner"], "opciones": ["[Rare] Increases maximum SD +3%"], "bonus_excelente": ["Increases Strength +69", "Increases Agility +69"], "drive_id": "1T3RcyL2SCS4_a20q2ymcOwu4FpDdW6Hi"},
    {"id": 241, "nombre": "Excellent Pad Armor", "tipo": "Armor", "base_score": 5, "defense": 34, "durability": "43/43", "clases": ["Dark Wizard", "Magic Gladiator"], "opciones": ["[Epic] Damage decrease +5%", "[Rare] Reflect damage +3%"], "bonus_excelente": ["Increases Vitality +29", "Increases Energy +30"], "drive_id": "1Z1YEGk78j_3qZtNUHqFasLqq6_EMKUdW"},
    {"id": 240, "nombre": "Excellent Violent Wind Pants", "tipo": "Pants", "base_score": 15, "defense": 40, "durability": "51/51", "clases": ["Summoner"], "opciones": ["[Legendary] Damage decrease +4%"], "bonus_excelente": ["Increases Agility +34", "Increases Strength +32"], "drive_id": "1euLQrkH0g0i7L9ugmRk10QRlqgwnmYCY"},
    {"id": 239, "nombre": "Excellent Epic Silver Bow", "tipo": "Bow", "base_score": 36, "defense": 0, "durability": "80/80", "clases": ["Elf"], "opciones": ["[Legendary] Excellent damage rate +8%", "[Rare] Increases physical damage +7%"], "bonus_excelente": ["Increases Energy +194", "Increases Vitality +181"], "drive_id": "1vp4qyg0Idn9OXgijU7RMAuj9NeUGXkDS"},
    {"id": 238, "nombre": "Excellent Guardian Pants", "tipo": "Pants", "base_score": 27, "defense": 109, "durability": "60/60", "clases": ["Elf"], "opciones": ["[Rare] Increases maximum life +3%"], "bonus_excelente": ["Increases Energy +62", "Increases Vitality +92"], "drive_id": "1PFjrFglCCrOxtVLmSqftJQGX7TjuxYXN"},
    {"id": 237, "nombre": "Excellent Aquagold Crossbow", "tipo": "Crossbow", "base_score": 36, "defense": 0, "durability": "84/84", "clases": ["Elf"], "opciones": ["[Epic] Critical damage rate +10%"], "bonus_excelente": ["Increases Agility +193", "Increases Energy +187"], "drive_id": "1Q9-7z5UIjQE47WN-iB68S4AItMitA-U-"},
    {"id": 236, "nombre": "Excellent Sacred Claw", "tipo": "Claw", "base_score": 26, "defense": 0, "durability": "80/80", "clases": ["Rage Fighter"], "opciones": ["[Legendary] Damage to monsters +8%", "[Rare] Obtains +1% life when monster is killed"], "bonus_excelente": ["Increases Strength +212", "Increases Energy +190"], "drive_id": "1_SlZm5z7Kt_tPnTLDE7cqQmpJvWAl71E"},
    {"id": 234, "nombre": "Excellent Bronze Pants", "tipo": "Pants", "base_score": 8, "defense": 41, "durability": "49/49", "clases": ["Dark Knight", "Magic Gladiator", "Dark Lord"], "opciones": ["[Rare] Damage decrease +3%", "[Rare] Reflect damage +3%"], "bonus_excelente": ["Increases Strength +37", "Increases Agility +39"], "drive_id": "1iS3vLcZtCi3QULyH9FP12KX3gy3f05in"},
    {"id": 232, "nombre": "Excellent Brass Gloves", "tipo": "Gloves", "base_score": 16, "defense": 37, "durability": "59/59", "clases": ["Dark Knight", "Magic Gladiator"], "opciones": ["[Epic] Damage decrease +5%"], "bonus_excelente": ["Increases Strength +52", "Increases Agility +58"], "drive_id": "14jkj6gYmmDrFzDDxjOYxVzo9x3RE44Xh"},
    {"id": 231, "nombre": "Excellent Buckler", "tipo": "Shield", "base_score": 3, "defense": 115, "durability": "39/39", "clases": ["Dark Wizard", "Dark Knight", "Elf", "Magic Gladiator", "Dark Lord", "Grow Lancer"], "opciones": ["[Legendary] Increases maximum life +4%"], "bonus_excelente": ["Increases Energy +27", "Increases Vitality +24"], "drive_id": "1dKoBcHU0jPDRHl4uTzdZJYBTC_mxyrfn"},
    {"id": 228, "nombre": "Excellent Wind Armor", "tipo": "Armor", "base_score": 16, "defense": 69, "durability": "47/47", "clases": ["Elf"], "opciones": ["[Legendary] Damage decrease +4%", "[Legendary] Reflect damage +4%"], "bonus_excelente": ["Increases Energy +47", "Increases Vitality +41"], "drive_id": "1YjKaPoCXFLBcWL7Lz9Goj0lrRarDeTL3"}
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
usuarios_db = cargar_json(USERS_FILE, {"pinion": {"password": "pass123", "rol": "admin", "requiere_cambio": False}})
donaciones_db = cargar_json(DONACIONES_FILE, [])
items_mu_db = cargar_json(ITEMS_FILE, DEFAULT_ITEMS) or DEFAULT_ITEMS
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

def sincronizar_drive_continuo():
    global items_mu_db
    archivos_detectados = []

    if GOOGLE_API_KEY:
        try:
            q = urllib.parse.quote(f"'{FOLDER_DRIVE_ID}' in parents and trashed=false")
            url = f"https://www.googleapis.com/drive/v3/files?q={q}&key={GOOGLE_API_KEY}&fields=files(id,name,mimeType)"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for f in data.get('files', []):
                    if 'image' in f.get('mimeType', ''):
                        archivos_detectados.append({"id": f['id'], "name": f['name']})
        except Exception: pass

    if not archivos_detectados:
        try:
            url_folder = f"https://drive.google.com/embeddedfolderview?id={FOLDER_DRIVE_ID}#grid"
            req = urllib.request.Request(url_folder, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                ids = set(re.findall(r'https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', html))
                for fid in ids:
                    archivos_detectados.append({"id": fid, "name": f"Item_{fid[:6]}"})
        except Exception: pass

    existentes = {it.get('drive_id') for it in items_mu_db if it.get('drive_id')}
    nuevos = 0
    for arch in archivos_detectados:
        fid = arch['id']
        if fid not in existentes:
            nombre_limpio = re.sub(r'\.[a-zA-Z0-9]+$', '', arch['name']).replace('_', ' ')
            nuevo_item = {
                "id": int(time.time() * 1000) + nuevos,
                "nombre": nombre_limpio,
                "tipo": "General",
                "base_score": 0, "defense": 0, "durability": "-",
                "clases": ["Dark Knight", "Dark Wizard", "Elf", "Magic Gladiator", "Dark Lord", "Summoner", "Rage Fighter"],
                "opciones": ["[Auto] Captura nueva detectada en Drive"],
                "bonus_excelente": [],
                "drive_id": fid
            }
            items_mu_db.insert(0, nuevo_item)
            nuevos += 1

    if nuevos > 0:
        guardar_json(ITEMS_FILE, items_mu_db)

def obtener_todos_items():
    global items_mu_db
    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, nombre, tipo, base_score, grade_score, defense, durability,
                           requisitos, clases, opciones, bonus_excelente, drive_id
                    FROM public.items_mu ORDER BY id DESC;
                """)
                filas = cur.fetchall()
                if filas and len(filas) > 0:
                    items_formateados = []
                    for r in filas:
                        items_formateados.append({
                            "id": r['id'],
                            "nombre": r.get('nombre') or 'Sin Nombre',
                            "tipo": r.get('tipo') or 'General',
                            "base_score": r.get('base_score') or 0,
                            "grade_score": r.get('grade_score') or 0,
                            "defense": r.get('defense') or 0,
                            "durability": r.get('durability') or '-',
                            "requisitos": normalizar_campo_json(r.get('requisitos'), {}),
                            "clases": normalizar_campo_json(r.get('clases'), []),
                            "opciones": normalizar_campo_json(r.get('opciones'), []),
                            "bonus_excelente": normalizar_campo_json(r.get('bonus_excelente'), []),
                            "drive_id": r.get('drive_id') or ''
                        })
                    items_mu_db = items_formateados
                    guardar_json(ITEMS_FILE, items_mu_db)
            conn.close()
        except Exception:
            try: conn.close()
            except Exception: pass

    if not items_mu_db or len(items_mu_db) == 0:
        items_mu_db = DEFAULT_ITEMS

    try:
        sincronizar_drive_continuo()
    except Exception: pass

    return items_mu_db

@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)

@app.route('/items')
def vista_items():
    return render_template('items.html')

@app.route('/api/items', methods=['GET', 'POST', 'PUT'])
def api_items():
    global items_mu_db
    if request.method == 'GET':
        lista = obtener_todos_items()
        return jsonify(lista)

    conn = get_db()
    if request.method == 'POST':
        data = request.json or {}
        raw_drive = data.get('drive_id', '')
        match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', raw_drive)
        id_limpio = match.group(1) if match else raw_drive.strip()

        nuevo = {
            "nombre": data.get('nombre', 'Item MU'),
            "tipo": data.get('tipo', 'Armor'),
            "base_score": int(data.get('base_score', 0)) if str(data.get('base_score', '')).isdigit() else 0,
            "defense": int(data.get('defense', 0)) if str(data.get('defense', '')).isdigit() else 0,
            "durability": data.get('durability', '-'),
            "clases": data.get('clases', []),
            "opciones": data.get('opciones', []),
            "bonus_excelente": data.get('bonus_excelente', []),
            "drive_id": id_limpio
        }
        item_id = int(time.time() * 1000)

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.items_mu (nombre, tipo, base_score, defense, durability, clases, opciones, bonus_excelente, drive_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
                    """, (nuevo["nombre"], nuevo["tipo"], nuevo["base_score"], nuevo["defense"], nuevo["durability"], json.dumps(nuevo["clases"]), json.dumps(nuevo["opciones"]), json.dumps(nuevo["bonus_excelente"]), nuevo["drive_id"]))
                    row = cur.fetchone()
                    if row: item_id = row['id']
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()

        nuevo["id"] = item_id
        items_mu_db.insert(0, nuevo)
        guardar_json(ITEMS_FILE, items_mu_db)
        return jsonify({"status": "ok", "item": nuevo}), 201

    if request.method == 'PUT':
        data = request.json or {}
        item_id = data.get('id')
        for it in items_mu_db:
            if it.get('id') == item_id:
                it['nombre'] = data.get('nombre', it['nombre'])
                it['clases'] = data.get('clases', it.get('clases', []))
                it['opciones'] = data.get('opciones', it.get('opciones', []))
                it['bonus_excelente'] = data.get('bonus_excelente', it.get('bonus_excelente', []))
        guardar_json(ITEMS_FILE, items_mu_db)

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE public.items_mu 
                        SET nombre = %s, clases = %s, opciones = %s, bonus_excelente = %s
                        WHERE id = %s;
                    """, (data.get('nombre'), json.dumps(data.get('clases', [])), json.dumps(data.get('opciones', [])), json.dumps(data.get('bonus_excelente', [])), item_id))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

@app.route('/api/miembros', methods=['GET', 'POST', 'PUT', 'DELETE'])
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
                        guardar_json(MIEMBROS_FILE, miembros_clan_db)
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify(miembros_clan_db)

    if request.method == 'POST':
        data = request.json or {}
        nombre_pj = data.get('nombre_pj', '').strip()
        raza = data.get('raza', 'Dark Knight').strip()
        items_asignados = data.get('items_asignados', [])
        notas = data.get('notas', '').strip()

        if not nombre_pj:
            if conn: conn.close()
            return jsonify({"error": "Nombre de PJ requerido"}), 400

        nuevo_id = int(time.time() * 1000)
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.miembros_clan (nombre_pj, raza, items_asignados, notas)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (nombre_pj) DO UPDATE 
                        SET raza = EXCLUDED.raza, items_asignados = EXCLUDED.items_asignados, notas = EXCLUDED.notas
                        RETURNING id;
                    """, (nombre_pj, raza, json.dumps(items_asignados), notas))
                    r = cur.fetchone()
                    if r: nuevo_id = r['id']
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()

        miembro = {"id": nuevo_id, "nombre_pj": nombre_pj, "raza": raza, "items_asignados": items_asignados, "notas": notas}
        miembros_clan_db = [m for m in miembros_clan_db if m['nombre_pj'].lower() != nombre_pj.lower()]
        miembros_clan_db.append(miembro)
        guardar_json(MIEMBROS_FILE, miembros_clan_db)
        return jsonify({"status": "ok", "miembro": miembro}), 201

    if request.method == 'PUT':
        data = request.json or {}
        m_id = data.get('id')
        for m in miembros_clan_db:
            if m['id'] == m_id:
                m['nombre_pj'] = data.get('nombre_pj', m['nombre_pj'])
                m['raza'] = data.get('raza', m['raza'])
                m['items_asignados'] = data.get('items_asignados', m['items_asignados'])
                m['notas'] = data.get('notas', m['notas'])

        guardar_json(MIEMBROS_FILE, miembros_clan_db)
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE public.miembros_clan
                        SET nombre_pj = %s, raza = %s, items_asignados = %s, notas = %s
                        WHERE id = %s;
                    """, (data.get('nombre_pj'), data.get('raza'), json.dumps(data.get('items_asignados', [])), data.get('notas', ''), m_id))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200

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
                                    (json.dumps(status_timers.get(server, {})), server))
                        conn.commit()
                    conn.close()
                except Exception:
                    if conn: conn.close()

        return jsonify({"status": "ok", "message": f"{boss} ocultado"}), 200
    return jsonify({"error": "Datos inválidos"}), 400

@app.route('/api/mapa_kill', methods=['POST'])
def mapa_kill():
    data = request.json or {}
    server_num = str(data.get('server', '1'))
    spot_id = str(data.get('spot_id'))

    if not spot_id: return jsonify({"error": "Spot requerido"}), 400
    if server_num not in status_mapas: status_mapas[server_num] = {}
    status_mapas[server_num][spot_id] = int(time.time() * 1000)
    guardar_json(MAPAS_FILE, status_mapas)
    return jsonify({"status": "ok", "mapas": status_mapas}), 200

@app.route('/api/mapa_reset', methods=['POST'])
def mapa_reset():
    data = request.json or {}
    server_num = str(data.get('server', '1'))
    spot_id = str(data.get('spot_id'))

    if server_num in status_mapas and spot_id in status_mapas[server_num]:
        del status_mapas[server_num][spot_id]
        guardar_json(MAPAS_FILE, status_mapas)
    return jsonify({"status": "ok", "mapas": status_mapas}), 200

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
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok"}), 200
    return jsonify({"error": "Servidor requerido"}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username_raw = data.get('username', '').strip()
    username = username_raw.lower()
    password = data.get('password', '')

    user_info = usuarios_db.get(username)
    if not user_info:
        conn = get_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM public.usuarios WHERE LOWER(username) = %s;", (username,))
                    row = cur.fetchone()
                    if row:
                        user_info = {
                            "username": row['username'],
                            "password": row['password_hash'],
                            "rol": row.get('rol', 'encargado'),
                            "requiere_cambio": row.get('requiere_cambio_clave', False)
                        }
                        usuarios_db[username] = user_info
                conn.close()
            except Exception:
                if conn: conn.close()

    if user_info:
        stored_pass = user_info.get("password", "")
        if stored_pass.startswith("scrypt:") or stored_pass.startswith("pbkdf2:"):
            es_valido = check_password_hash(stored_pass, password)
        else:
            es_valido = (stored_pass == password)

        if es_valido:
            session['user'] = user_info.get('username', username_raw)
            session['rol'] = user_info.get("rol", "encargado")
            return jsonify({
                "status": "ok",
                "user": session['user'],
                "rol": session['rol'],
                "requiere_cambio": user_info.get("requiere_cambio", False)
            }), 200

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
            "rol": session.get('rol', 'encargado'),
            "requiere_cambio": False
        })
    return jsonify({"logged_in": False})

@app.route('/api/cambiar_clave', methods=['POST'])
def cambiar_clave():
    if 'user' not in session: return jsonify({"error": "No autorizado"}), 401
    data = request.json or {}
    nueva_clave = data.get('nueva_clave')
    if not nueva_clave or len(nueva_clave) < 4: return jsonify({"error": "Mínimo 4 caracteres"}), 400

    username = session['user']
    new_hash = generate_password_hash(nueva_clave)
    u_key = username.lower()
    if u_key in usuarios_db:
        usuarios_db[u_key]["password"] = new_hash
        usuarios_db[u_key]["requiere_cambio"] = False
        guardar_json(USERS_FILE, usuarios_db)

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE public.usuarios SET password_hash = %s, requiere_cambio_clave = FALSE WHERE LOWER(username) = %s;", 
                            (new_hash, u_key))
                conn.commit()
            conn.close()
        except Exception:
            if conn: conn.close()

    return jsonify({"status": "ok", "message": "Contraseña actualizada"}), 200

@app.route('/api/usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'user' not in session or session.get('rol') != 'admin': return jsonify({"error": "Acceso denegado"}), 403
    conn = get_db()
    if request.method == 'GET':
        lista = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT username, rol, requiere_cambio_clave, creado_por FROM public.usuarios ORDER BY id ASC;")
                    for r in cur.fetchall():
                        lista.append({
                            "username": r['username'],
                            "rol": r.get('rol', 'encargado'),
                            "requiere_cambio_clave": r.get('requiere_cambio_clave', False),
                            "creado_por": r.get('creado_por', 'Sistema')
                        })
                conn.close()
                return jsonify(lista)
            except Exception:
                if conn: conn.close()

        for u, val in usuarios_db.items():
            lista.append({
                "username": val.get("username", u),
                "rol": val.get("rol", "encargado"),
                "requiere_cambio_clave": val.get("requiere_cambio", False),
                "creado_por": val.get("creado_por", "Sistema")
            })
        return jsonify(lista)

    if request.method == 'POST':
        data = request.json or {}
        new_user = data.get('username', '').strip()
        new_pass = data.get('password', '')
        new_rol = data.get('rol', 'encargado')
        if not new_user or not new_pass:
            if conn: conn.close()
            return jsonify({"error": "Faltan campos"}), 400

        u_key = new_user.lower()
        p_hash = generate_password_hash(new_pass)
        usuarios_db[u_key] = {
            "username": new_user, "password": p_hash,
            "rol": new_rol, "requiere_cambio": True, "creado_por": session['user']
        }
        guardar_json(USERS_FILE, usuarios_db)
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.usuarios (username, password_hash, rol, requiere_cambio_clave, creado_por)
                        VALUES (%s, %s, %s, TRUE, %s)
                        ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash, rol = EXCLUDED.rol;
                    """, (new_user, p_hash, new_rol, session['user']))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok", "message": f"Usuario {new_user} creado"}), 201

@app.route('/api/donaciones', methods=['GET', 'POST'])
def donaciones():
    if request.method == 'GET':
        return jsonify(donaciones_db)
    if request.method == 'POST':
        if 'user' not in session: return jsonify({"error": "No autorizado"}), 401
        data = request.json or {}
        pj_name = data.get('pj_name')
        tipo_donacion = data.get('tipo_donacion')
        cantidad = data.get('cantidad', 1)
        if not pj_name or not tipo_donacion: return jsonify({"error": "Faltan datos"}), 400

        nueva_donacion = {
            "id": int(time.time() * 1000), "pj_name": pj_name, "tipo_donacion": tipo_donacion,
            "cantidad": int(cantidad), "registrado_por": session['user'],
            "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "modificado_por": None, "fecha_modificacion": None
        }
        donaciones_db.insert(0, nueva_donacion)
        guardar_json(DONACIONES_FILE, donaciones_db)

        conn = get_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.donaciones (pj_name, tipo_donacion, cantidad, registrado_por)
                        VALUES (%s, %s, %s, %s);
                    """, (pj_name, tipo_donacion, int(cantidad), session['user']))
                    conn.commit()
                conn.close()
            except Exception:
                if conn: conn.close()
        return jsonify({"status": "ok", "donacion": nueva_donacion}), 201

@app.route('/api/donaciones/<int:donacion_id>', methods=['PUT'])
def editar_donacion(donacion_
