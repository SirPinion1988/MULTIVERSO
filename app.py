import os
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template_string, jsonify, request, redirect, url_for, session
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)
app.secret_key = "clave_secreta_mudream_donaciones_key"

LINK_DESCARGA_BOT = "https://drive.google.com/drive/folders/1Rx1TZZl5IncOpJPLab4YnRqOEIY6iBrC?usp=sharing"

# === CREDENCIALES DE SUPABASE ===
SUPABASE_URL = "https://csdwnpkvuymtasxpujza.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzZHducGt2dXltdGFzeHB1anphIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3ODU0NDYsImV4cCI6MjEwMTM2MTQ0Nn0.IwgSW7QwoqLArOTfHYT4TyONA_57y1ELCaiQyZ3xyRg"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SERVIDORES_VALIDOS = ["Server 1", "Server 2", "Server 3", "Server 20"]

# CONFIGURACIÓN EXCLUSIVA DE LOS 6 BOSSES AUTORIZADOS
COOLDOWNS_CONFIG = {
    "Muggron 1": 180, "Muggron 2": 180,
    "Dreadhorn 1": 60, "Dreadhorn 2": 60,
    "Moltragon 1": 60, "Moltragon 2": 60,
    "Borgar": 120,
    "Kharzul 1": 420, "Kharzul 2": 420, "Kharzul 3": 420,
    "Vescrya 1": 420, "Vescrya 2": 420, "Vescrya 3": 420,
    "Muggron Barracks 1": 180, "Muggron Barracks 2": 180,
    "Muggron Crywolf 1": 180, "Muggron Crywolf 2": 180
}

def parsear_fecha_utc(dt_str):
    if not dt_str: return None
    try:
        clean_str = str(dt_str).replace('Z', '+00:00')
        dt_obj = datetime.fromisoformat(clean_str)
        if dt_obj.tzinfo is None: dt_obj = dt_obj.replace(tzinfo=timezone.utc)
        return dt_obj
    except Exception:
        return None

def obtener_datos():
    timers_map = {svr: {} for svr in SERVIDORES_VALIDOS}
    pcs_map = {svr: "Sin reportes" for svr in SERVIDORES_VALIDOS}
    pj_map = {svr: "Desconocido" for svr in SERVIDORES_VALIDOS}
    hb_map = {svr: None for svr in SERVIDORES_VALIDOS}

    try:
        res_kills = supabase.table('boss_kills').select('*').execute()
        res_pings = supabase.table('heartbeats').select('*').execute()

        if res_kills.data:
            for row in res_kills.data:
                svr = row.get('server_name')
                boss = row.get('boss_name')
                last_kill = row.get('last_kill')
                if svr in SERVIDORES_VALIDOS and boss and last_kill:
                    dt_obj = parsear_fecha_utc(last_kill)
                    if dt_obj:
                        timers_map[svr][boss] = int(dt_obj.timestamp())

        if res_pings.data:
            for row in res_pings.data:
                svr = row.get('server_name')
                if svr in SERVIDORES_VALIDOS:
                    pcs_map[svr] = row.get('pc_id') or 'Sin reportes'
                    pj_map[svr] = row.get('pj_name') or 'Desconocido'
                    hb_map[svr] = row.get('last_ping')

    except Exception as e:
        print(f"Error obteniendo datos Supabase: {e}")

    return timers_map, pcs_map, pj_map, hb_map

# === PLANTILLA FRONTEND EXCLUSIVA PARA LOS 6 BOSSES ===
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚔️ Monitor Multi-PC - MuDream ⚔️</title>
    <style>
        :root { 
            --bg-dark: #0a0814; --card-bg: #141126; --card-border: #2a244d; 
            --accent-purple: #7b2cbf; --accent-glow: #9d4edd; --text-primary: #e6e1ff; 
            --text-secondary: #8e85b8; --cd-red: #ff4757; --window-yellow: #f1c40f; 
        }
        body { font-family: 'Segoe UI', sans-serif; background-color: var(--bg-dark); color: var(--text-primary); margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        header { text-align: center; margin-bottom: 20px; width: 100%; max-width: 1200px; display: flex; justify-content: space-between; align-items: center; }
        h1 { font-size: 1.8rem; margin: 0; color: #fff; text-shadow: 0 0 10px rgba(123, 44, 191, 0.5); }
        .user-info-bar { font-size: 0.85rem; color: var(--accent-glow); background: #100d21; padding: 6px 12px; border-radius: 8px; border: 1px solid var(--card-border); }
        .logout-btn { color: #ff4757; text-decoration: none; margin-left: 8px; font-weight: bold; }
        
        .manual-panel { background: var(--card-bg); border: 1px solid var(--accent-purple); border-radius: 12px; padding: 15px 20px; margin-bottom: 20px; width: 100%; max-width: 1200px; box-sizing: border-box; box-shadow: 0 0 15px rgba(123, 44, 191, 0.2); }
        .manual-panel h3 { margin: 0 0 12px 0; font-size: 1.1rem; color: var(--accent-glow); text-align: center; }
        .manual-form { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; align-items: center; }
        .manual-form select, .manual-form input { background: #0d0a1a; border: 1px solid var(--card-border); color: var(--text-primary); padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; outline: none; }
        .btn-manual-submit { background: var(--accent-purple); border: none; color: white; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 0.9rem; }
        .btn-manual-submit:hover { background: var(--accent-glow); }

        .controls-bar { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; margin-bottom: 25px; background: #100d21; padding: 12px 20px; border-radius: 12px; border: 1px solid var(--card-border); }
        .view-btn { background: #1e1938; border: 1px solid var(--card-border); color: var(--text-primary); padding: 10px 18px; font-size: 0.95rem; font-weight: 600; border-radius: 8px; cursor: pointer; }
        .view-btn.active { background: var(--accent-purple); border-color: var(--accent-glow); color: #fff; }
        .dashboard-container { width: 100%; max-width: 1200px; }
        
        .server-block { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 18px; margin-bottom: 20px; }
        .server-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--card-border); padding-bottom: 10px; margin-bottom: 8px; }
        .server-title { font-size: 1.4rem; font-weight: bold; color: #fff; }
        
        .boss-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
        .boss-card { background: #0d0a1a; border: 1px solid #1f1a3a; border-radius: 10px; padding: 12px 10px; display: flex; flex-direction: column; justify-content: space-between; align-items: center; text-align: center; min-height: 110px; position: relative; }
        .server-badge-top { position: absolute; top: 6px; right: 6px; font-size: 0.7rem; background: var(--accent-purple); color: #fff; padding: 2px 6px; border-radius: 5px; font-weight: 800; }
        .boss-name { font-weight: bold; font-size: 0.9rem; margin-top: 6px; margin-bottom: 8px; width: 100%; word-break: break-word; }
        .timer-badge { font-family: monospace; font-size: 0.85rem; font-weight: bold; padding: 4px 6px; border-radius: 6px; text-align: center; width: 100%; box-sizing: border-box; margin-bottom: 8px; }
        .status-cd { color: var(--cd-red); border: 1px solid var(--cd-red); background: rgba(255, 71, 87, 0.1); }
        .status-window { color: var(--window-yellow); border: 1px solid var(--window-yellow); background: rgba(241, 196, 15, 0.1); }
        .btn-action { background: var(--accent-purple); border: none; color: white; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.75rem; }
        .btn-action:hover { background: var(--accent-glow); }
        .empty-msg { color: var(--text-secondary); text-align: center; padding: 15px; font-style: italic; width: 100%; grid-column: 1 / -1; }
    </style>
</head>
<body>

    <header>
        <h1>⚔️ MONITOR MUDREAM ⚔️</h1>
        {% if session.get('user') %}
        <div class="user-info-bar">
            👤 Encargado: <strong>{{ session.get('user') }}</strong>
            <a href="/logout" class="logout-btn">Salir ✖</a>
        </div>
        {% endif %}
    </header>

    <div class="manual-panel" id="panelKillManual">
        <h3>⚡ Cargar Kill Manual / Iniciar Boss</h3>
        <div class="manual-form">
            <select id="manualServer" required>
                <option value="" disabled selected>Seleccionar Server</option>
                <option value="Server 1">Server 1</option>
                <option value="Server 2">Server 2</option>
                <option value="Server 3">Server 3</option>
                <option value="Server 20">Server 20</option>
            </select>
            <select id="manualBoss" required>
                <option value="" disabled selected>Seleccionar Boss</option>
            </select>
            <button type="button" class="btn-manual-submit" onclick="ejecutarKillForm()">➕ Registrar Kill</button>
        </div>
    </div>

    <div class="controls-bar">
        <button class="view-btn active" onclick="setVista('TODOS')">👁️ Ver Todos Juntos</button>
        <button class="view-btn" onclick="setVista('Server 1')">Server 1</button>
        <button class="view-btn" onclick="setVista('Server 2')">Server 2</button>
        <button class="view-btn" onclick="setVista('Server 3')">Server 3</button>
        <button class="view-btn" onclick="setVista('Server 20')">Server 20</button>
        <button class="view-btn" onclick="setVista('BOTS')">🤖 Bots Activos</button>
        
        <a href="{{ link_descarga }}" target="_blank" style="text-decoration:none;">
            <button class="view-btn" style="background:#7b2cbf; border-color:#9d4edd; color:#fff;">⬇️ Descargar Bot (.exe)</button>
        </a>
    </div>

    <div class="dashboard-container" id="dashboard"></div>

    <script>
        let modoVista = window.location.hash ? window.location.hash.substring(1).toUpperCase() : 'TODOS';
        let estadoWeb = {};

        function obtenerTagServer(svr) {
            if (svr === "Server 1") return "S1";
            if (svr === "Server 2") return "S2";
            if (svr === "Server 3") return "S3";
            if (svr === "Server 20") return "S20";
            return svr;
        }

        function poblarSelectorBosses() {
            const selectBoss = document.getElementById('manualBoss');
            if (!selectBoss || selectBoss.options.length > 1) return;
            const cooldowns = estadoWeb.cooldowns || {};
            for (const boss of Object.keys(cooldowns)) {
                let opt = document.createElement('option');
                opt.value = boss;
                opt.textContent = `${boss} (${cooldowns[boss]}m)`;
                selectBoss.appendChild(opt);
            }
        }

        async function enviarKill(svr, boss) {
            try {
                const res = await fetch('/api/kill', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ server: svr, boss: boss, pc_id: "Navegador Web", pj_name: "Manual Web" })
                });
                if (res.ok) { pedirTimers(); }
            } catch (e) {}
        }

        function ejecutarKillForm() {
            const svr = document.getElementById('manualServer').value;
            const boss = document.getElementById('manualBoss').value;
            if (svr && boss) {
                enviarKill(svr, boss);
            } else {
                alert("Selecciona un Servidor y un Boss.");
            }
        }

        function setVista(vista) {
            modoVista = vista;
            window.location.hash = vista.toLowerCase();
            document.querySelectorAll('.view-btn').forEach(btn => {
                const esActivo = (vista === 'TODOS' && btn.innerText.includes('Todos')) || btn.innerText.includes(vista);
                btn.classList.toggle('active', esActivo);
            });
            render();
        }

        async function pedirTimers() {
            try {
                const res = await fetch('/api/status_timers');
                if (res.ok) {
                    estadoWeb = await res.json();
                    poblarSelectorBosses();
                    render(); 
                }
            } catch (e) {}
        }

        function render() {
            const container = document.getElementById('dashboard');
            container.innerHTML = '';
            const serversDisponibles = estadoWeb.servers || ["Server 1", "Server 2", "Server 3", "Server 20"];
            const timers = estadoWeb.timers || {};
            const cooldowns = estadoWeb.cooldowns || {};
            const ahoraUnix = Math.floor(Date.now() / 1000);

            const renderServerBlock = (svr) => {
                let serverBlock = document.createElement('div');
                serverBlock.className = 'server-block';

                let htmlContent = `<div class="server-header"><div class="server-title">${svr}</div></div><div class="boss-grid">`;
                const bossesServidor = timers[svr] || {};
                let bossesVisiblesCount = 0;

                // FILTRAR PARA QUE SÓLO RENDERICE LOS 6 BOSSES AUTORIZADOS
                for (const [bossName, killUnix] of Object.entries(bossesServidor)) {
                    // Validar pertenencia de servidor para los 6
                    if (svr === "Server 20") {
                        if (!["Kharzul 1", "Kharzul 2", "Kharzul 3", "Vescrya 1", "Vescrya 2", "Vescrya 3", "Muggron Barracks 1", "Muggron Barracks 2", "Muggron Crywolf 1", "Muggron Crywolf 2"].includes(bossName)) continue;
                    } else {
                        if (!["Borgar", "Dreadhorn 1", "Dreadhorn 2", "Moltragon 1", "Moltragon 2", "Muggron 1", "Muggron 2", "Kharzul 1", "Vescrya 1"].includes(bossName)) continue;
                    }

                    const cdMinutos = cooldowns[bossName] || 60;
                    const cooldownSegundos = cdMinutos * 60;
                    const targetRespawnUnix = killUnix + cooldownSegundos;
                    const finVentanaUnix = targetRespawnUnix + 3600; // 60 min de cacería

                    let displayTimer = '';

                    // 1. 🔴 ROJO: En Cooldown (De más a menos)
                    if (ahoraUnix < targetRespawnUnix) {
                        bossesVisiblesCount++;
                        const restoSec = targetRespawnUnix - ahoraUnix;
                        const h = Math.floor(restoSec / 3600), m = Math.floor((restoSec % 3600) / 60), s = restoSec % 60;
                        displayTimer = `<div class="timer-badge status-cd">🔴 ${h > 0 ? h + 'h ' : ''}${m < 10 ? '0':''}${m}m ${s < 10 ? '0':''}${s}s</div>`;
                    } 
                    // 2. 🟡 AMARILLO: Ventana de Cacería (De 0m 00s a 60m 00s)
                    else if (ahoraUnix >= targetRespawnUnix && ahoraUnix <= finVentanaUnix) {
                        bossesVisiblesCount++;
                        const transcurridoVentana = ahoraUnix - targetRespawnUnix;
                        const m = Math.floor(transcurridoVentana / 60), s = transcurridoVentana % 60;
                        displayTimer = `<div class="timer-badge status-window">🟡 VENTANA (${m}m ${s < 10 ? '0':''}${s}s)</div>`;
                    } 
                    // 3. ❌ SI PASA DE 60 MIN DE VENTANA, SE BORRA DE PANTALLA
                    else {
                        continue; 
                    }

                    const tagServer = obtenerTagServer(svr);
                    htmlContent += `
                        <div class="boss-card">
                            <span class="server-badge-top">${tagServer}</span>
                            <div><div class="boss-name">${bossName}</div></div>
                            ${displayTimer}
                            <div class="actions-group">
                                <button type="button" class="btn-action" onclick="enviarKill('${svr}', '${bossName}')">⚔️ Kill</button>
                            </div>
                        </div>
                    `;
                }

                if (bossesVisiblesCount === 0) {
                    htmlContent += `<div class="empty-msg">No hay timers activos de (Borgar, Kharzul, Vescrya, Moltragon, Dreadhorn, Muggron) en este server.</div>`;
                }

                htmlContent += `</div>`;
                serverBlock.innerHTML = htmlContent;
                container.appendChild(serverBlock);
            };

            if (modoVista === 'TODOS') {
                serversDisponibles.forEach(svr => renderServerBlock(svr));
            } else if (SERVIDORES_VALIDOS.includes(modoVista)) {
                renderServerBlock(modoVista);
            }
        }

        setInterval(pedirTimers, 1000);
        
        document.addEventListener('DOMContentLoaded', () => {
            setVista(modoVista);
            pedirTimers();
        });
    </script>
</body>
</html>
"""

# === RUTAS FLASK ===

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, link_descarga=LINK_DESCARGA_BOT)

@app.route('/api/status_timers', methods=['GET'])
def status_timers():
    timers_map, pcs_map, pj_map, hb_map = obtener_datos()
    return jsonify({
        "timers": timers_map, 
        "cooldowns": COOLDOWNS_CONFIG, 
        "servers": SERVIDORES_VALIDOS, 
        "ultimas_pcs": pcs_map, 
        "ultimos_pjs": pj_map, 
        "heartbeats": hb_map
    })

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

        return jsonify({"status": "SUCCESS", "boss": boss, "server": server}), 200
    except Exception as e:
        print(f"Error registrando kill: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
