import os
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template_string, jsonify, request, redirect, url_for
import requests

app = Flask(__name__)

# === CONFIGURACIÓN DE SUPABASE REST API ===
SUPABASE_URL = "https://csdwnpkvuymtasxpujza.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzZHducGt2dXltdGFzeHB1anphIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3ODU0NDYsImV4cCI6MjEwMTM2MTQ0Nn0.IwgSW7QwoqLArOTfHYT4TyONA_57y1ELCaiQyZ3xyRg"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# === COOLDOWNS (en minutos) ===
COOLDOWNS = {
    "Muggron 1": 180,
    "Muggron 2": 180,
    "Dreadhorn 1": 60,
    "Dreadhorn 2": 60,
    "Moltragon 1": 60,
    "Moltragon 2": 60,
    "Borgar": 120,
    "Kharzul 1": 420,
    "Kharzul 2": 420,
    "Kharzul 3": 420,
    "Vescrya 1": 420,
    "Vescrya 2": 420,
    "Vescrya 3": 420,
    "Yellow Goblin": 600,
    "Blue Goblin": 600,
    "Red Goblin": 600,
    "Red Dragon": 360,
    "Santa 1": 360,
    "Santa 2": 360,
    "White Wizard 1": 360,
    "White Wizard 2": 360,
    "Skeleton King 1": 360,
    "Skeleton King 2": 360,
    "Muggron Barracks 1": 180,
    "Muggron Barracks 2": 180,
    "Muggron Crywolf 1": 180,
    "Muggron Crywolf 2": 180
}

SERVIDORES = ["Server 1", "Server 2", "Server 3", "Server 20"]

def parsear_fecha_utc(dt_str):
    if not dt_str: return None
    try:
        clean_str = str(dt_str).replace('Z', '+00:00')
        dt_obj = datetime.fromisoformat(clean_str)
        if dt_obj.tzinfo is None: dt_obj = dt_obj.replace(tzinfo=timezone.utc)
        return dt_obj
    except Exception:
        return None

def guardar_backup_supabase_online(server, timers, pc_id, pj_name):
    """Guarda un historial/backup directamente en la tabla secundaria timers_backup de Supabase."""
    try:
        url_post = f"{SUPABASE_URL}/rest/v1/timers_backup"
        payload = {
            "server": server,
            "timers": timers,
            "last_pc": pc_id,
            "last_pj": pj_name
        }
        requests.post(url_post, headers=HEADERS, json=payload, timeout=3)
    except Exception:
        pass

def obtener_datos():
    timers_map = {svr: {} for svr in SERVIDORES}
    pcs_map = {svr: "Sin reportes" for svr in SERVIDORES}
    pj_map = {svr: "Desconocido" for svr in SERVIDORES}
    hb_map = {svr: None for svr in SERVIDORES}

    try:
        url = f"{SUPABASE_URL}/rest/v1/timers_bosses?select=*"
        res = requests.get(url, headers=HEADERS, timeout=5)

        if res.status_code == 200:
            data = res.json()
            for row in data:
                svr = row.get('server')
                if not svr or svr not in SERVIDORES: continue

                boss_timers = {}
                raw_timers = row.get('timers') or {}

                if isinstance(raw_timers, dict):
                    for boss, dt_str in raw_timers.items():
                        dt_obj = parsear_fecha_utc(dt_str)
                        if dt_obj:
                            boss_timers[boss] = int(dt_obj.timestamp())

                timers_map[svr] = boss_timers
                pcs_map[svr] = row.get('last_pc') or 'Sin reportes'
                pj_map[svr] = row.get('last_pj') or 'Desconocido'
                hb_map[svr] = row.get('last_heartbeat')

        return timers_map, pcs_map, pj_map, hb_map
    except Exception:
        return timers_map, pcs_map, pj_map, hb_map

def guardar_boss(server, boss, pc_id, pj_name, custom_minutes=None):
    try:
        url_get = f"{SUPABASE_URL}/rest/v1/timers_bosses?server=eq.{server}&select=timers"
        res_get = requests.get(url_get, headers=HEADERS, timeout=5)
        current = {}
        if res_get.status_code == 200 and res_get.json():
            current = res_get.json()[0].get('timers') or {}

        minutos = custom_minutes if custom_minutes is not None else COOLDOWNS.get(boss, 60)
        nueva_fecha = datetime.now(timezone.utc) + timedelta(minutes=minutos)
        current[boss] = nueva_fecha.isoformat()
        ahora_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        payload = {
            'timers': current,
            'last_pc': pc_id,
            'last_pj': pj_name,
            'last_heartbeat': ahora_iso
        }
        
        # Guardado en tabla principal
        url_patch = f"{SUPABASE_URL}/rest/v1/timers_bosses?server=eq.{server}"
        requests.patch(url_patch, headers=HEADERS, json=payload, timeout=5)

        # Resguardo secundario online en Supabase
        guardar_backup_supabase_online(server, current, pc_id, pj_name)

    except Exception as e:
        print(f"Error guardando: {e}")

def borrar_boss(server, boss):
    try:
        url_get = f"{SUPABASE_URL}/rest/v1/timers_bosses?server=eq.{server}&select=timers"
        res_get = requests.get(url_get, headers=HEADERS, timeout=5)
        current = {}
        if res_get.status_code == 200 and res_get.json():
            current = res_get.json()[0].get('timers') or {}

        if boss in current:
            del current[boss]
            payload = {'timers': current}
            url_patch = f"{SUPABASE_URL}/rest/v1/timers_bosses?server=eq.{server}"
            requests.patch(url_patch, headers=HEADERS, json=payload, timeout=5)
            
            # Resguardo secundario online en Supabase
            guardar_backup_supabase_online(server, current, "Navegador Web", "Reset")
    except Exception:
        pass

def actualizar_heartbeat(server, pc_id, pj_name):
    try:
        ahora_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        payload = {
            'last_pc': pc_id,
            'last_pj': pj_name,
            'last_heartbeat': ahora_iso
        }
        url_patch = f"{SUPABASE_URL}/rest/v1/timers_bosses?server=eq.{server}"
        requests.patch(url_patch, headers=HEADERS, json=payload, timeout=5)
    except Exception:
        pass

# === PLANTILLA WEB ===
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚔️ Monitor Multi-PC - MuDream ⚔️</title>
    <style>
        :root { 
            --bg-dark: #0a0814; 
            --card-bg: #141126; 
            --card-border: #2a244d; 
            --accent-purple: #7b2cbf; 
            --accent-glow: #9d4edd; 
            --text-primary: #e6e1ff; 
            --text-secondary: #8e85b8; 
            --alive-green: #2ecc71; 
            --cd-red: #ff4757; 
            --window-yellow: #f1c40f; 
        }
        body { font-family: 'Segoe UI', sans-serif; background-color: var(--bg-dark); color: var(--text-primary); margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        header { text-align: center; margin-bottom: 20px; width: 100%; max-width: 1200px; }
        h1 { font-size: 1.8rem; margin: 0; color: #fff; text-shadow: 0 0 10px rgba(123, 44, 191, 0.5); }
        
        .manual-panel {
            background: var(--card-bg);
            border: 1px solid var(--accent-purple);
            border-radius: 12px;
            padding: 15px 20px;
            margin-bottom: 20px;
            width: 100%;
            max-width: 1200px;
            box-sizing: border-box;
            box-shadow: 0 0 15px rgba(123, 44, 191, 0.2);
        }
        .manual-panel h3 { margin: 0 0 12px 0; font-size: 1.1rem; color: var(--accent-glow); text-align: center; }
        .manual-form { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; align-items: center; }
        .manual-form select, .manual-form input {
            background: #0d0a1a;
            border: 1px solid var(--card-border);
            color: var(--text-primary);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.9rem;
            outline: none;
        }
        .manual-form select:focus, .manual-form input:focus { border-color: var(--accent-glow); }
        .btn-manual-submit {
            background: var(--accent-purple);
            border: none;
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            font-size: 0.9rem;
            transition: background 0.2s;
        }
        .btn-manual-submit:hover { background: var(--accent-glow); }

        .controls-bar { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; margin-bottom: 25px; background: #100d21; padding: 12px 20px; border-radius: 12px; border: 1px solid var(--card-border); }
        .view-btn { background: #1e1938; border: 1px solid var(--card-border); color: var(--text-primary); padding: 10px 18px; font-size: 0.95rem; font-weight: 600; border-radius: 8px; cursor: pointer; }
        .view-btn.active { background: var(--accent-purple); border-color: var(--accent-glow); color: #fff; }
        .dashboard-container { width: 100%; max-width: 1200px; }
        .grid-all { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; }
        .server-block { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 18px; }
        .server-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--card-border); padding-bottom: 10px; margin-bottom: 8px; }
        .server-title { font-size: 1.4rem; font-weight: bold; color: #fff; }
        .bot-status-container { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 0.8rem; background: #0c091f; padding: 6px 10px; border-radius: 6px; }
        .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }
        .dot-online { background-color: var(--alive-green); }
        .dot-offline { background-color: var(--cd-red); }
        .pc-badge { font-size: 0.75rem; color: var(--text-secondary); }
        .pj-badge { font-size: 0.8rem; color: #b8acff; font-weight: bold; }
        
        .boss-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); 
            gap: 10px; 
        }
        .boss-card { 
            background: #0d0a1a; 
            border: 1px solid #1f1a3a; 
            border-radius: 10px; 
            padding: 10px; 
            display: flex; 
            flex-direction: column; 
            justify-content: space-between; 
            align-items: center; 
            text-align: center;
            min-height: 120px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }
        .boss-name { font-weight: bold; font-size: 0.85rem; margin-bottom: 2px; }
        .boss-respawn { font-size: 0.7rem; color: var(--text-secondary); margin-bottom: 6px; }
        
        .timer-badge { font-family: monospace; font-size: 0.85rem; font-weight: bold; padding: 4px 6px; border-radius: 6px; text-align: center; width: 100%; box-sizing: border-box; margin-bottom: 8px; }
        .status-alive { color: var(--alive-green); border: 1px solid var(--alive-green); background: rgba(46, 204, 113, 0.1); }
        .status-cd { color: var(--cd-red); border: 1px solid var(--cd-red); background: rgba(255, 71, 87, 0.1); }
        .status-window { color: var(--window-yellow); border: 1px solid var(--window-yellow); background: rgba(241, 196, 15, 0.1); }
        
        .btn-action { background: var(--accent-purple); border: none; color: white; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.75rem; }
        .btn-action:hover { background: var(--accent-glow); }
        .btn-reset { background: #2a2347; color: #aaa; margin-left: 4px; }
        .btn-reset:hover { background: #ff4757; color: #fff; }
        .actions-group { display: flex; align-items: center; gap: 4px; }
        form { margin: 0; padding: 0; display: inline; }
    </style>
</head>
<body>

    <header>
        <h1>⚔️ MONITOR MUDREAM ⚔️</h1>
    </header>

    <div class="manual-panel">
        <h3>⚡ Cargar Kill Manual / Timer Especial</h3>
        <form action="/action/kill" method="POST" class="manual-form">
            <select name="server" id="manualServer" required>
                <option value="" disabled selected>Seleccionar Server</option>
                <option value="Server 1">Server 1</option>
                <option value="Server 2">Server 2</option>
                <option value="Server 3">Server 3</option>
                <option value="Server 20">Server 20</option>
            </select>
            
            <select name="boss" id="manualBoss" required>
                <option value="" disabled selected>Seleccionar Boss</option>
            </select>

            <input type="number" name="custom_timer" placeholder="Minutos restantes (Opcional)" min="0">

            <button type="submit" class="btn-manual-submit">➕ Registrar Kill</button>
        </form>
    </div>

    <div class="controls-bar">
        <button class="view-btn active" onclick="setVista('TODOS')">👁️ Ver Todos Juntos</button>
        <button class="view-btn" onclick="setVista('Server 1')">Server 1</button>
        <button class="view-btn" onclick="setVista('Server 2')">Server 2</button>
        <button class="view-btn" onclick="setVista('Server 3')">Server 3</button>
        <button class="view-btn" onclick="setVista('Server 20')">Server 20</button>
    </div>

    <div class="dashboard-container" id="dashboard"></div>

    <script>
        let modoVista = 'TODOS';
        let estadoWeb = {};

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

        function setVista(vista) {
            modoVista = vista;
            document.querySelectorAll('.view-btn').forEach(btn => {
                const esActivo = (vista === 'TODOS' && btn.innerText.includes('Todos')) || btn.innerText === vista;
                btn.classList.toggle('active', esActivo);
            });
            render();
        }

        async function pedirTimers() {
            try {
                const res = await fetch('/api/timers');
                estadoWeb = await res.json();
                poblarSelectorBosses();
                render();
            } catch (e) {}
        }

        function render() {
            const container = document.getElementById('dashboard');
            container.innerHTML = '';
            const serversDisponibles = estadoWeb.servers || ["Server 1", "Server 2", "Server 3", "Server 20"];
            const timers = estadoWeb.timers || {};
            const cooldowns = estadoWeb.cooldowns || {};
            const ultimosReportes = estadoWeb.ultimas_pcs || {};
            const ultimosPjs = estadoWeb.ultimos_pjs || {};
            const heartbeats = estadoWeb.heartbeats || {};
            const ahoraUnix = Math.floor(Date.now() / 1000);
            const servidoresAMostrar = (modoVista === 'TODOS') ? serversDisponibles : [modoVista];
            container.className = (modoVista === 'TODOS') ? "dashboard-container grid-all" : "dashboard-container";

            servidoresAMostrar.forEach(svr => {
                let serverBlock = document.createElement('div');
                serverBlock.className = 'server-block';
                const pcOrigen = ultimosReportes[svr] || 'Sin reportes';
                const pjOrigen = ultimosPjs[svr] || 'Desconocido';
                
                let esOnline = false;
                if (heartbeats[svr]) {
                    const fechaLimpia = heartbeats[svr].replace(' ', 'T');
                    const hbUnix = Math.floor(new Date(fechaLimpia).getTime() / 1000);
                    if (!isNaN(hbUnix) && Math.abs(ahoraUnix - hbUnix) <= 60) { 
                        esOnline = true; 
                    }
                }

                const statusHtml = esOnline 
                    ? `<span><span class="status-dot dot-online"></span><strong style="color:#2ecc71;">ONLINE</strong></span>`
                    : `<span><span class="status-dot dot-offline"></span><strong style="color:#ff4757;">OFFLINE</strong></span>`;

                let htmlContent = `
                    <div class="server-header">
                        <div class="server-title">${svr}</div>
                        <div>${statusHtml}</div>
                    </div>
                    <div class="bot-status-container">
                        <div class="pj-badge">👤 PJ: ${pjOrigen}</div>
                        <div class="pc-badge">💻 PC: ${pcOrigen}</div>
                    </div>
                    <div class="boss-grid">
                `;

                const bossesServidor = timers[svr] || {};
                let bossesProcesados = [];

                for (const [bossName, cdMinutos] of Object.entries(cooldowns)) {
                    if (svr === "Server 20") {
                        if (["Borgar", "Yellow Goblin", "Blue Goblin", "Red Goblin", "Red Dragon", "Santa 1", "Santa 2", "White Wizard 1", "White Wizard 2", "Skeleton King 1", "Skeleton King 2", "Dreadhorn 1", "Dreadhorn 2", "Moltragon 1", "Moltragon 2", "Muggron 1", "Muggron 2"].includes(bossName)) continue;
                    } else {
                        if (["Muggron Barracks 1", "Muggron Barracks 2", "Muggron Crywolf 1", "Muggron Crywolf 2", "Kharzul 2", "Kharzul 3", "Vescrya 2", "Vescrya 3"].includes(bossName)) continue;
                    }

                    let statusState = 'alive';
                    let displayTimer = '';
                    let prioridadOrden = 0;

                    if (bossName in bossesServidor) {
                        const targetUnix = bossesServidor[bossName];
                        const diffSec = targetUnix - ahoraUnix;

                        if (["Yellow Goblin", "Blue Goblin", "Red Goblin"].includes(bossName)) {
                            const inicioVentanaUnix = targetUnix;
                            const finVentanaUnix = targetUnix + 3600;
                            if (ahoraUnix < inicioVentanaUnix) {
                                statusState = 'cd';
                                const cdSec = inicioVentanaUnix - ahoraUnix;
                                prioridadOrden = cdSec; 
                                const h = Math.floor(cdSec / 3600), m = Math.floor((cdSec % 3600) / 60), s = cdSec % 60;
                                displayTimer = `<div class="timer-badge status-cd">🔴 ${h}h ${m < 10 ? '0':''}${m}m ${s < 10 ? '0':''}${s}s</div>`;
                            } else if (ahoraUnix >= inicioVentanaUnix && ahoraUnix <= finVentanaUnix) {
                                statusState = 'window';
                                prioridadOrden = -500;
                                const winSec = finVentanaUnix - ahoraUnix;
                                const m = Math.floor(winSec / 60), s = winSec % 60;
                                displayTimer = `<div class="timer-badge status-window">🟡 VENTANA (${m}m ${s < 10 ? '0':''}${s}s)</div>`;
                            } else {
                                const vivoSec = ahoraUnix - finVentanaUnix;
                                prioridadOrden = -1000 - vivoSec; 
                                const h = Math.floor(vivoSec / 3600), m = Math.floor((vivoSec % 3600) / 60), s = vivoSec % 60;
                                displayTimer = `<div class="timer-badge status-alive">🟢 VIVO +${h > 0 ? h + 'h ' : ''}${m}m ${s < 10 ? '0':''}${s}s</div>`;
                            }
                        } else if (diffSec > 0) {
                            statusState = 'cd';
                            prioridadOrden = diffSec;
                            const h = Math.floor(diffSec / 3600), m = Math.floor((diffSec % 3600) / 60), s = diffSec % 60;
                            displayTimer = `<div class="timer-badge status-cd">🔴 ${h > 0 ? h + 'h ' : ''}${m < 10 ? '0':''}${m}m ${s < 10 ? '0':''}${s}s</div>`;
                        } else {
                            const vivoSec = Math.abs(diffSec);
                            prioridadOrden = -1000 - vivoSec;
                            const h = Math.floor(vivoSec / 3600), m = Math.floor((vivoSec % 3600) / 60), s = vivoSec % 60;
                            displayTimer = `<div class="timer-badge status-alive">🟢 VIVO +${h > 0 ? h + 'h ' : ''}${m}m ${s < 10 ? '0':''}${s}s</div>`;
                        }
                    } else {
                        prioridadOrden = -999;
                        displayTimer = `<div class="timer-badge status-alive">🟢 ¡VIVO!</div>`;
                    }

                    bossesProcesados.push({
                        bossName,
                        cdMinutos,
                        statusState,
                        displayTimer,
                        prioridadOrden
                    });
                }

                bossesProcesados.sort((a, b) => a.prioridadOrden - b.prioridadOrden);

                bossesProcesados.forEach(b => {
                    htmlContent += `
                        <div class="boss-card">
                            <div>
                                <div class="boss-name">${b.bossName}</div>
                                <div class="boss-respawn">${b.cdMinutos} min</div>
                            </div>
                            ${b.displayTimer}
                            <div class="actions-group">
                                <form action="/action/kill" method="POST">
                                    <input type="hidden" name="server" value="${svr}">
                                    <input type="hidden" name="boss" value="${b.bossName}">
                                    <button type="submit" class="btn-action">⚔️ Kill</button>
                                </form>
                                ${b.statusState !== 'alive' ? `
                                <form action="/action/reset" method="POST">
                                    <input type="hidden" name="server" value="${svr}">
                                    <input type="hidden" name="boss" value="${b.bossName}">
                                    <button type="submit" class="btn-action btn-reset">✖</button>
                                </form>` : ''}
                            </div>
                        </div>
                    `;
                });

                htmlContent += `</div>`;
                serverBlock.innerHTML = htmlContent;
                container.appendChild(serverBlock);
            });
        }
        setInterval(pedirTimers, 1000);
        pedirTimers();
    </script>
</body>
</html>
"""

# === RUTAS API ===
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/ping')
def ping():
    return "OK", 200

@app.route('/api/timers', methods=['GET'])
def get_timers():
    timers_map, pcs_map, pj_map, hb_map = obtener_datos()
    return jsonify({
        "timers": timers_map, 
        "cooldowns": COOLDOWNS, 
        "servers": SERVIDORES, 
        "ultimas_pcs": pcs_map, 
        "ultimos_pjs": pj_map, 
        "heartbeats": hb_map
    })

@app.route('/action/kill', methods=['GET', 'POST'])
def action_kill():
    svr = request.form.get("server") or request.args.get("server")
    boss = request.form.get("boss") or request.args.get("boss")
    custom_timer = request.form.get("custom_timer") or request.args.get("custom_timer")
    
    custom_min = None
    if custom_timer:
        try:
            custom_min = int(custom_timer)
        except ValueError:
            pass

    if svr and boss:
        guardar_boss(svr, boss, "Navegador Web", "Web", custom_minutes=custom_min)
    return redirect(url_for('index'))

@app.route('/action/reset', methods=['GET', 'POST'])
def action_reset():
    svr = request.form.get("server") or request.args.get("server")
    boss = request.form.get("boss") or request.args.get("boss")
    if svr and boss:
        borrar_boss(svr, boss)
    return redirect(url_for('index'))

@app.route('/api/kill', methods=['POST'])
def api_kill():
    data = request.get_json(silent=True) or {}
    svr = data.get("server")
    boss = data.get("boss")
    pc_id = data.get("pc_id", "Desconocida")
    pj_name = data.get("pj_name", "Desconocido")
    if svr and boss:
        guardar_boss(svr, boss, pc_id, pj_name)
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

@app.route('/api/heartbeat', methods=['POST'])
def api_heartbeat():
    data = request.get_json(silent=True) or {}
    svr = data.get("server")
    pc_id = data.get("pc_id", "Desconocida")
    pj_name = data.get("pj_name", "Desconocido")
    if svr:
        actualizar_heartbeat(svr, pc_id, pj_name)
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
