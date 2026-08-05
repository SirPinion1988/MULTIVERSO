import os
import json
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

LINK_DESCARGA_BOT = "https://drive.google.com/drive/folders/1Rx1TZZl5IncOpJPLab4YnRqOEIY6iBrC?usp=sharing"

# === CREDENCIALES DIRECTAS DE SUPABASE ===
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

# === RUTA PRINCIPAL (PÁGINA WEB) ===
@app.route('/')
def index():
    return render_template('index.html', link_descarga=LINK_DESCARGA_BOT)

# === API: CONSULTA DE TIMERS Y BOTS ===
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
        print(f"Error obteniendo timers: {e}")
        return jsonify({"error": str(e)}), 500

# === API: RECEPCIÓN DE HEARTBEAT DEL BOT ===
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

# === API: REGISTRO DE KILL (MANUAL O AUTOMÁTICO) ===
@app.route('/api/kill', methods=['POST'])
def kill():
    data = request.get_json() or {}
    server = data.get('server')
    boss = data.get('boss')
    pc_id = data.get('pc_id', 'Navegador Web')
    pj_name = data.get('pj_name', 'Manual Web')

    if not server or server not in SERVIDORES_VALIDOS or not boss:
        return jsonify({"error": "Datos incompletos"}), 400

    try:
        # 1. Obtener jsonb actual de timers del servidor
        res = supabase.table('timers_bosses').select('timers').eq('server', server).execute()
        current_timers = {}
        if res.data and len(res.data) > 0:
            current_timers = res.data[0].get('timers') or {}

        # 2. Actualizar la marca Unix de muerte del boss
        ahora_unix = int(datetime.now(timezone.utc).timestamp())
        current_timers[boss] = ahora_unix

        # 3. Guardar en Supabase
        supabase.table('timers_bosses').update({
            'timers': current_timers,
            'last_pc': pc_id,
            'last_pj': pj_name,
            'last_heartbeat': datetime.now(timezone.utc).isoformat()
        }).eq('server', server).execute()

        return jsonify({"status": "SUCCESS", "boss": boss, "server": server}), 200
    except Exception as e:
        print(f"Error registrando kill: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
