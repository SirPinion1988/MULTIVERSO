import os
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

# === CREDENCIALES DIRECTAS DE SUPABASE ===
SUPABASE_URL = "https://csdwnpkvuymtasxpujza.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzZHducGt2dXltdGFzeHB1anphIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3ODU0NDYsImV4cCI6MjEwMTM2MTQ0Nn0.IwgSW7QwoqLArOTfHYT4TyONA_57y1ELCaiQyZ3xyRg"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Servidores válidos
SERVIDORES_VALIDOS = ["Server 1", "Server 2", "Server 3", "Server 20"]

# === RUTA PRINCIPAL (PÁGINA WEB) ===
@app.route('/')
def index():
    return render_template('index.html')

# === API: RECEPCIÓN DE HEARTBEAT DEL BOT LOCAL ===
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
        supabase.table('heartbeats').upsert({
            'server_name': server,
            'pc_id': pc_id,
            'pj_name': pj_name,
            'last_ping': ahora
        }, on_conflict='server_name, pc_id').execute()

        return jsonify({"status": "OK"}), 200
    except Exception as e:
        print(f"Error en heartbeat: {e}")
        return jsonify({"error": str(e)}), 500

# === API: REGISTRO DE KILL DEL BOT LOCAL ===
@app.route('/api/kill', methods=['POST'])
def kill():
    data = request.get_json() or {}
    server = data.get('server')
    boss = data.get('boss')
    pc_id = data.get('pc_id', 'Desconocido')
    pj_name = data.get('pj_name', 'Desconocido')

    if not server or server not in SERVIDORES_VALIDOS or not boss:
        return jsonify({"error": "Datos de kill incompletos"}), 400

    try:
        ahora = datetime.now(timezone.utc).isoformat()
        supabase.table('boss_kills').upsert({
            'server_name': server,
            'boss_name': boss,
            'last_kill': ahora,
            'last_pc': pc_id,
            'last_pj': pj_name
        }, on_conflict='server_name, boss_name').execute()

        print(f"⚔️ [KILL REGISTRADO] {boss} en {server} por {pj_name} ({pc_id})")
        return jsonify({"status": "SUCCESS", "boss": boss, "server": server}), 200
    except Exception as e:
        print(f"Error registrando kill: {e}")
        return jsonify({"error": str(e)}), 500

# === API: CONSULTA DE ESTADO GENERAL DE BOSSES Y PINGS ===
@app.route('/api/status', methods=['GET'])
def status():
    try:
        res_kills = supabase.table('boss_kills').select('*').execute()
        res_pings = supabase.table('heartbeats').select('*').execute()

        return jsonify({
            "kills": res_kills.data if res_kills.data else [],
            "heartbeats": res_pings.data if res_pings.data else []
        }), 200
    except Exception as e:
        print(f"Error obteniendo status: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
