import os
import json
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template_string, jsonify, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import requests

app = Flask(__name__)
app.secret_key = "clave_secreta_mudream_donaciones_key"

# === ENLACE DE DESCARGA DIRECTO A GOOGLE DRIVE ===
LINK_DESCARGA_BOT = "https://drive.google.com/drive/folders/1Rx1TZZl5IncOpJPLab4YnRqOEIY6iBrC?usp=sharing"

# === CONFIGURACIÓN DE SUPABASE REST API ===
SUPABASE_URL = "https://csdwnpkvuymtasxpujza.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzZHducGt2dXltdGFzeHB1anphIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU3ODU0NDYsImV4cCI6MjEwMTM2MTQ0Nn0.IwgSW7QwoqLArOTfHYT4TyONA_57y1ELCaiQyZ3xyRg"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# === COOLDOWNS Y VENTANAS (en minutos) ===
COOLDOWNS_CONFIG = {
    "Muggron 1": (180, 60), "Muggron 2": (180, 60),
    "Dreadhorn 1": (60, 60), "Dreadhorn 2": (60, 60),
    "Moltragon 1": (60, 60), "Moltragon 2": (60, 60),
    "Borgar": (120, 60),
    "Kharzul 1": (420, 60), "Kharzul 2": (420, 60), "Kharzul 3": (420, 60),
    "Vescrya 1": (420, 60), "Vescrya 2": (420, 60), "Vescrya 3": (420, 60),
    "Yellow Goblin": (600, 60), "Blue Goblin": (600, 60), "Red Goblin": (600, 60),
    "Red Dragon": (360, 60), "Santa 1": (360, 60), "Santa 2": (360, 60),
    "White Wizard 1": (360, 60), "White Wizard 2": (360, 60),
    "Skeleton King 1": (360, 60), "Skeleton King 2": (360, 60),
    "Muggron Barracks 1": (180, 60), "Muggron Barracks 2": (180, 60),
    "Muggron Crywolf 1": (180, 60), "Muggron Crywolf 2": (180, 60)
}

COOLDOWNS = {k: v[0] for k, v in COOLDOWNS_CONFIG.items()}
SERVIDORES = ["Server 1", "Server 2", "Server 3", "Server 20"]
BOSSES_MANUALES = ["Yellow Goblin", "Blue Goblin", "Red Goblin", "Skeleton King 1", "Skeleton King 2", "Red Dragon", "Santa 1", "Santa 2"]

GRUPOS_PARES = [
    ["Moltragon 1", "Moltragon 2"], ["Dreadhorn 1", "Dreadhorn 2"],
    ["Muggron 1", "Muggron 2"], ["Santa 1", "Santa 2"],
    ["White Wizard 1", "White Wizard 2"], ["Skeleton King 1", "Skeleton King 2"],
    ["Kharzul 1", "Kharzul 2", "Kharzul 3"], ["Vescrya 1", "Vescrya 2", "Vescrya 3"],
    ["Muggron Barracks 1", "Muggron Barracks 2"], ["Muggron Crywolf 1", "Muggron Crywolf 2"]
]

# === FUNCIONES AUXILIARES Y SUPABASE ===
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
    try:
        url_post = f"{SUPABASE_URL}/rest/v1/timers_backup"
        payload = {"server": server, "timers": timers, "last_pc": pc_id, "last_pj": pj_name}
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
                        if dt_obj: boss_timers[boss] = int(dt_obj.timestamp())

                timers_map[svr] = boss_timers
                pcs_map[svr] = row.get('last_pc') or 'Sin reportes'
                pj_map[svr] = row.get('last_pj') or 'Desconocido'
                hb_map[svr] = row.get('last_heartbeat')

        return timers_map, pcs_map, pj_map, hb_map
    except Exception:
        return timers_map, pcs_map, pj_map, hb_map

def seleccionar_boss_objetivo(server, boss_recibido, current_timers):
    ahora_utc = datetime.now(timezone.utc)
    for grupo in GRUPOS_PARES:
        nombre_base = boss_recibido.split(" ")[0]
        if any(b.startswith(nombre_base) for b in grupo):
            if boss_recibido in grupo: return boss_recibido
            for b_opcion in grupo:
                dt_str = current_timers.get(b_opcion)
                dt_obj = parsear_fecha_utc(dt_str) if dt_str else None
                if not dt_obj or dt_obj <= ahora_utc: return b_opcion
            return grupo[0]
    return boss_recibido

def guardar_boss(server, boss_solicitado, pc_id, pj_name, custom_minutes=None):
    try:
        url_get = f"{SUPABASE_URL}/rest/v1/timers_bosses?server=eq.{server}&select=timers"
        res_get = requests.get(url_get, headers=HEADERS, timeout=5)
        current = {}
        if res_get.status_code == 200 and res_get.json(): current = res_get.json()[0].get('timers') or {}

        boss_final = seleccionar_boss_objetivo(server, boss_solicitado, current)
        minutos = custom_minutes if custom_minutes is not None else COOLDOWNS_CONFIG.get(boss_final, (60, 60))[0]
        nueva_fecha = datetime.now(timezone.utc) + timedelta(minutes=minutos)
        current[boss_final] = nueva_fecha.isoformat()
        ahora_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        payload = {'timers': current, 'last_pc': pc_id, 'last_pj': pj_name, 'last_heartbeat': ahora_iso}
        requests.patch(f"{SUPABASE_URL}/rest/v1/timers_bosses?server=eq.{server}", headers=HEADERS, json=payload, timeout=5)
        guardar_backup_supabase_online(server, current, pc_id, pj_name)
    except Exception as e: print(f"Error guardando: {e}")

def borrar_boss(server, boss):
    try:
        url_get = f"{SUPABASE_URL}/rest/v1/timers_bosses?server=eq.{server}&select=timers"
        res_get = requests.get(url_get, headers=HEADERS, timeout=5)
        current = {}
        if res_get.status_code == 200 and res_get.json(): current = res_get.json()[0].get('timers') or {}

        if boss in current:
            del current[boss]
            payload = {'timers': current}
            requests.patch(f"{SUPABASE_URL}/rest/v1/timers_bosses?server=eq.{server}", headers=HEADERS, json=payload, timeout=5)
            guardar_backup_supabase_online(server, current, "Navegador Web", "Reset")
    except Exception: pass

def actualizar_heartbeat(server, pc_id, pj_name):
    try:
        ahora_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        payload = {'last_pc': pc_id, 'last_pj': pj_name, 'last_heartbeat': ahora_iso}
        requests.patch(f"{SUPABASE_URL}/rest/v1/timers_bosses?server=eq.{server}", headers=HEADERS, json=payload, timeout=5)
    except Exception: pass

# === PLANTILLA WEB COMPLETA ===
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
            --text-secondary: #8e85b8; --alive-green: #2ecc71; --cd-red: #ff4757; --window-yellow: #f1c40f; 
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
        .bot-status-container { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 0.8rem; background: #0c091f; padding: 6px 10px; border-radius: 6px; }
        .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }
        .dot-online { background-color: var(--alive-green); }
        .dot-offline { background-color: var(--cd-red); }
        .pc-badge { font-size: 0.75rem; color: var(--text-secondary); }
        .pj-badge { font-size: 0.8rem; color: #b8acff; font-weight: bold; }
        
        .boss-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
        .boss-card { background: #0d0a1a; border: 1px solid #1f1a3a; border-radius: 10px; padding: 12px 10px; display: flex; flex-direction: column; justify-content: space-between; align-items: center; text-align: center; min-height: 110px; position: relative; }
        .server-badge-top { position: absolute; top: 6px; right: 6px; font-size: 0.7rem; background: var(--accent-purple); color: #fff; padding: 2px 6px; border-radius: 5px; font-weight: 800; }
        .boss-name { font-weight: bold; font-size: 0.9rem; margin-top: 6px; margin-bottom: 8px; width: 100%; word-break: break-word; }
        .timer-badge { font-family: monospace; font-size: 0.85rem; font-weight: bold; padding: 4px 6px; border-radius: 6px; text-align: center; width: 100%; box-sizing: border-box; margin-bottom: 8px; }
        .status-alive { color: var(--alive-green); border: 1px solid var(--alive-green); background: rgba(46, 204, 113, 0.1); }
        .status-cd { color: var(--cd-red); border: 1px solid var(--cd-red); background: rgba(255, 71, 87, 0.1); }
        .status-window { color: var(--window-yellow); border: 1px solid var(--window-yellow); background: rgba(241, 196, 15, 0.1); }
        .btn-action { background: var(--accent-purple); border: none; color: white; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-weight: bold; font-size: 0.75rem; }
        .btn-action:hover { background: var(--accent-glow); }
        .btn-reset { background: #2a2347; color: #aaa; margin-left: 4px; }
        .btn-reset:hover { background: #ff4757; color: #fff; }
        .actions-group { display: flex; align-items: center; gap: 4px; }

        .donacion-pj-card { background: #0d0a1a; border: 1px solid var(--card-border); border-radius: 10px; padding: 14px 18px; margin-bottom: 10px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; }
        .pj-name-tag { font-size: 1.1rem; font-weight: bold; color: #b8acff; min-width: 140px; }
        .items-donados-container { display: flex; flex-wrap: wrap; gap: 8px; }
        .item-donado-chip { background: #1a1533; border: 1px solid var(--accent-purple); padding: 4px 10px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; color: var(--text-primary); }
        .leyenda-modificado { font-size: 0.75rem; color: var(--window-yellow); font-style: italic; display: block; margin-top: 2px; }

        .donaciones-table { width: 100%; border-collapse: collapse; margin-top: 15px; background: #0d0a1a; border-radius: 8px; overflow: hidden; }
        .donaciones-table th, .donaciones-table td { padding: 10px 14px; text-align: center; border-bottom: 1px solid var(--card-border); }
        .donaciones-table th { background: #1a1533; color: var(--accent-glow); font-size: 0.9rem; }
        .donaciones-table td { font-size: 0.85rem; }

        .login-box { background: #0d0a1a; border: 1px solid var(--accent-purple); padding: 20px; border-radius: 12px; max-width: 350px; margin: 30px auto; text-align: center; box-shadow: 0 0 15px rgba(123, 44, 191, 0.3); }
        .login-box input { width: 100%; padding: 8px 12px; margin-bottom: 12px; background: #141126; border: 1px solid var(--card-border); color: #fff; border-radius: 6px; box-sizing: border-box; }
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
        <h3>⚡ Cargar Kill Manual / Timer Especial</h3>
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
            <input type="number" id="manualTimer" placeholder="Minutos restantes (Opcional)" min="0">
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
        <button class="view-btn" onclick="setVista('DONACIONES')">💎 Donaciones</button>
        
        <a href="{{ link_descarga }}" target="_blank" style="text-decoration:none;">
            <button class="view-btn" style="background:#7b2cbf; border-color:#9d4edd; color:#fff;">⬇️ Descargar Bot (.exe)</button>
        </a>
    </div>

    <div class="dashboard-container" id="dashboard"></div>

    <script>
        let modoVista = 'TODOS';
        let estadoWeb = {};
        let listaDonaciones = [];
        const usuarioLogueado = "{{ session.get('user', '') }}";
        const esAdmin = "{{ session.get('user', '') }}" === "admin";
        const BOSSES_MANUALES_LIST = ["Yellow Goblin", "Blue Goblin", "Red Goblin", "Skeleton King 1", "Skeleton King 2", "Red Dragon", "Santa 1", "Santa 2"];

        function formatearCantidad(num) {
            if (num >= 1000000000) return (num / 1000000000).toFixed(1).replace('.0', '') + 'kkk';
            if (num >= 1000000) return (num / 1000000).toFixed(1).replace('.0', '') + 'kk';
            if (num >= 1000) return (num / 1000).toFixed(1).replace('.0', '') + 'k';
            return num.toLocaleString();
        }

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

        // === ACCIONES VIA AJAX (SIN RECARGAR PAGINA) ===
        async function enviarKill(svr, boss, customMin = '') {
            try {
                const formData = new FormData();
                formData.append('server', svr);
                formData.append('boss', boss);
                if (customMin) formData.append('custom_timer', customMin);
                await fetch('/action/kill', { method: 'POST', body: formData });
                pedirTimers();
            } catch (e) {}
        }

        async function enviarReset(svr, boss) {
            try {
                const formData = new FormData();
                formData.append('server', svr);
                formData.append('boss', boss);
                await fetch('/action/reset', { method: 'POST', body: formData });
                pedirTimers();
            } catch (e) {}
        }

        function ejecutarKillForm() {
            const svr = document.getElementById('manualServer').value;
            const boss = document.getElementById('manualBoss').value;
            const customTimer = document.getElementById('manualTimer').value;
            if (svr && boss) {
                enviarKill(svr, boss, customTimer);
            }
        }

        function setVista(vista) {
            modoVista = vista;
            document.querySelectorAll('.view-btn').forEach(btn => {
                const esActivo = (vista === 'TODOS' && btn.innerText.includes('Todos')) || btn.innerText.includes(vista);
                btn.classList.toggle('active', esActivo);
            });
            
            const panelKill = document.getElementById('panelKillManual');
            if (panelKill) {
                panelKill.style.display = (vista === 'DONACIONES' || vista === 'BOTS') ? 'none' : 'block';
            }

            if (vista === 'DONACIONES') {
                if (usuarioLogueado) { pedirDonaciones(); } 
                else { renderLoginDonaciones(); }
            } else { render(); }
        }

        async function pedirTimers() {
            try {
                const res = await fetch('/api/timers');
                estadoWeb = await res.json();
                poblarSelectorBosses();
                if (modoVista !== 'DONACIONES') { render(); }
            } catch (e) {}
        }

        async function pedirDonaciones() {
            try {
                const res = await fetch('/api/donaciones');
                listaDonaciones = await res.json();
                renderDonaciones();
            } catch (e) {}
        }

        function renderLoginDonaciones() {
            const container = document.getElementById('dashboard');
            container.innerHTML = `
                <div class="server-block">
                    <div class="login-box">
                        <h3 style="color:var(--accent-glow); margin:0 0 15px 0;">🔐 Acceso a Donaciones</h3>
                        <p style="font-size:0.85rem; color:var(--text-secondary); margin-bottom:15px;">Ingresa tus credenciales para administrar las donaciones.</p>
                        <form action="/login" method="POST">
                            <input type="text" name="username" placeholder="Usuario" required>
                            <input type="password" name="password" placeholder="Contraseña" required>
                            <button type="submit" class="btn-manual-submit" style="width:100%;">Ingresar</button>
                        </form>
                    </div>
                </div>
            `;
        }

        function renderBotsActivos() {
            const container = document.getElementById('dashboard');
            container.innerHTML = '';
            const serversDisponibles = estadoWeb.servers || ["Server 1", "Server 2", "Server 3", "Server 20"];
            const ultimosReportes = estadoWeb.ultimas_pcs || {};
            const ultimosPjs = estadoWeb.ultimos_pjs || {};
            const heartbeats = estadoWeb.heartbeats || {};
            const ahoraUnix = Math.floor(Date.now() / 1000);

            let block = document.createElement('div');
            block.className = 'server-block';

            let htmlContent = `
                <div class="server-header">
                    <div class="server-title">🤖 ESTADO DE BOTS Y CUENTAS CONECTADAS</div>
                </div>
                <div class="boss-grid" style="grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));">
            `;

            serversDisponibles.forEach(svr => {
                const pcOrigen = ultimosReportes[svr] || 'Sin reportes';
                const pjOrigen = ultimosPjs[svr] || 'Desconocido';
                let esOnline = false;
                let horaHbStr = 'Sin registros';

                if (heartbeats[svr]) {
                    const fechaLimpia = heartbeats[svr].replace(' ', 'T');
                    const hbDate = new Date(fechaLimpia);
                    const hbUnix = Math.floor(hbDate.getTime() / 1000);
                    if (!isNaN(hbUnix)) {
                        horaHbStr = hbDate.toLocaleTimeString();
                        if (Math.abs(ahoraUnix - hbUnix) <= 60) { esOnline = true; }
                    }
                }

                const tagServer = obtenerTagServer(svr);
                const statusBadge = esOnline 
                    ? `<div class="timer-badge status-alive">🟢 ONLINE</div>`
                    : `<div class="timer-badge status-cd">🔴 OFFLINE</div>`;

                htmlContent += `
                    <div class="boss-card">
                        <span class="server-badge-top">${tagServer}</span>
                        <div style="margin-top:8px;">
                            <div class="boss-name" style="font-size:1.05rem; color:#b8acff;">👤 Character: ${pjOrigen}</div>
                            <div style="font-size:0.75rem; color:var(--text-secondary); margin-bottom:6px;">💻 PC: ${pcOrigen}</div>
                        </div>
                        ${statusBadge}
                        <div style="font-size:0.7rem; color:#8e85b8; margin-top:4px;">Última señal: ${horaHbStr}</div>
                    </div>
                `;
            });

            htmlContent += `</div>`;
            block.innerHTML = htmlContent;
            container.appendChild(block);
        }

        function renderDonaciones() {
            const container = document.getElementById('dashboard');
            container.innerHTML = '';

            let block = document.createElement('div');
            block.className = 'server-block';

            let htmlForm = `
                <div class="server-header">
                    <div class="server-title">💎 REGISTRO Y CONTROL DE DONACIONES</div>
                </div>
            `;

            if (esAdmin) {
                htmlForm += `
                    <div style="background:#0c091f; padding:15px; border-radius:10px; margin-bottom:20px; border:1px solid var(--accent-purple);">
                        <h4 style="margin:0 0 10px 0; color:var(--accent-glow);">👥 Panel Admin: Crear Nuevo Encargado</h4>
                        <form action="/admin/crear_usuario" method="POST" style="display:flex; flex-wrap:wrap; gap:10px; align-items:center;">
                            <input type="text" name="nuevo_usuario" placeholder="Nombre de Usuario" required style="background:#0d0a1a; border:1px solid var(--card-border); color:#fff; padding:8px; border-radius:6px;">
                            <input type="password" name="clave_inicial" placeholder="Clave Temporal" required style="background:#0d0a1a; border:1px solid var(--card-border); color:#fff; padding:8px; border-radius:6px;">
                            <button type="submit" class="btn-manual-submit" style="background:#2ecc71;">➕ Crear Encargado</button>
                        </form>
                    </div>
                `;
            }

            htmlForm += `
                <div style="background:#0c091f; padding:15px; border-radius:10px; margin-bottom:20px; border:1px solid var(--card-border);">
                    <h4 style="margin:0 0 10px 0; color:var(--accent-glow);">➕ Cargar Nueva Donación</h4>
                    <form action="/action/donar" method="POST" style="display:flex; flex-wrap:wrap; gap:10px; align-items:center;">
                        <input type="text" name="pj_name" placeholder="Nick del Personaje" required style="background:#0d0a1a; border:1px solid var(--card-border); color:#fff; padding:8px; border-radius:6px;">
                        
                        <select name="tipo_donacion" required style="background:#0d0a1a; border:1px solid var(--card-border); color:#fff; padding:8px; border-radius:6px;">
                            <option value="Bless">Jewel of Bless</option>
                            <option value="Soul">Jewel of Soul</option>
                            <option value="Chaos">Jewel of Chaos</option>
                            <option value="Life">Jewel of Life</option>
                            <option value="Creation">Jewel of Creation</option>
                            <option value="Zen">Zen</option>
                        </select>

                        <input type="number" name="cantidad" placeholder="Cantidad" min="1" value="1" required style="background:#0d0a1a; border:1px solid var(--card-border); color:#fff; padding:8px; border-radius:6px; width:120px;">

                        <button type="submit" class="btn-manual-submit">💎 Registrar Donación</button>
                    </form>
                </div>

                <h3 style="color:var(--accent-glow); margin-bottom:12px;">📊 Resumen por Personaje</h3>
            `;

            let resumenPj = {};
            listaDonaciones.forEach(d => {
                const pj = d.pj_name;
                const tipo = d.tipo_donacion;
                const cant = Number(d.cantidad) || 0;

                if (!resumenPj[pj]) resumenPj[pj] = {};
                if (!resumenPj[pj][tipo]) resumenPj[pj][tipo] = 0;
                resumenPj[pj][tipo] += cant;
            });

            if (Object.keys(resumenPj).length === 0) {
                htmlForm += `<div style="color:var(--text-secondary); margin-bottom:20px;">No hay donaciones registradas para resumir.</div>`;
            } else {
                htmlForm += `<div style="display:flex; flex-direction:column; gap:8px; margin-bottom:25px;">`;
                for (const [pj, items] of Object.entries(resumenPj)) {
                    htmlForm += `<div class="donacion-pj-card"><div class="pj-name-tag">👤 ${pj}</div><div class="items-donados-container">`;
                    for (const [tipoItem, totalCant] of Object.entries(items)) {
                        const cantTexto = formatearCantidad(totalCant);
                        htmlForm += `<div class="item-donado-chip"><span style="color:var(--window-yellow);">${cantTexto}</span> ${tipoItem}</div>`;
                    }
                    htmlForm += `</div></div>`;
                }
                htmlForm += `</div>`;
            }

            htmlForm += `
                <h3 style="color:var(--accent-glow); margin-bottom:10px;">📜 Historial Detallado</h3>
                <table class="donaciones-table">
                    <thead>
                        <tr>
                            <th>Fecha</th>
                            <th>Personaje</th>
                            <th>Item / Donación</th>
                            <th>Cantidad</th>
                            <th>Registrado Por</th>
                            <th>Acción</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            if (listaDonaciones.length === 0) {
                htmlForm += `<tr><td colspan="6" style="color:var(--text-secondary);">No hay donaciones en el historial.</td></tr>`;
            } else {
                listaDonaciones.forEach(d => {
                    const fechaObj = new Date(d.created_at);
                    const fechaStr = !isNaN(fechaObj) ? fechaObj.toLocaleString() : 'Reciente';
                    
                    let leyendaModificado = '';
                    if (d.modificado_por) {
                        const fechaModObj = new Date(d.fecha_modificacion);
                        const fechaModStr = !isNaN(fechaModObj) ? fechaModObj.toLocaleTimeString() : '';
                        leyendaModificado = `<span class="leyenda-modificado">✏️ Modificado por <strong>${d.modificado_por}</strong> (${fechaModStr})</span>`;
                    }

                    htmlForm += `
                        <tr>
                            <td style="color:var(--text-secondary);">${fechaStr}</td>
                            <td style="font-weight:bold; color:#b8acff;">${d.pj_name}</td>
                            <td><strong style="color:var(--window-yellow);">${d.tipo_donacion}</strong>${leyendaModificado}</td>
                            <td style="font-weight:bold; color:var(--alive-green);">${Number(d.cantidad).toLocaleString()}</td>
                            <td style="color:var(--text-secondary); font-size:0.8rem;">👤 ${d.registrado_por || 'Sistema'}</td>
                            <td>
                                <form action="/action/editar_donacion" method="POST" style="display:inline;">
                                    <input type="hidden" name="id" value="${d.id}">
                                    <input type="number" name="nueva_cantidad" placeholder="Nueva cant." style="width:70px; background:#000; color:#fff; border:1px solid #444; border-radius:4px; font-size:0.75rem; padding:2px 4px;">
                                    <button type="submit" class="btn-action" style="font-size:0.7rem;">✏️ Modificar</button>
                                </form>
                            </td>
                        </tr>
                    `;
                });
            }

            htmlForm += `</tbody></table>`;
            block.innerHTML = htmlForm;
            container.appendChild(block);
        }

        function render() {
            if (modoVista === 'BOTS') { renderBotsActivos(); return; }
            if (modoVista === 'DONACIONES') {
                if (usuarioLogueado) { renderDonaciones(); } 
                else { renderLoginDonaciones(); }
                return;
            }

            const container = document.getElementById('dashboard');
            container.innerHTML = '';
            const serversDisponibles = estadoWeb.servers || ["Server 1", "Server 2", "Server 3", "Server 20"];
            const timers = estadoWeb.timers || {};
            const cooldowns = estadoWeb.cooldowns || {};
            const ultimosReportes = estadoWeb.ultimas_pcs || {};
            const ultimosPjs = estadoWeb.ultimos_pjs || {};
            const heartbeats = estadoWeb.heartbeats || {};
            const ahoraUnix = Math.floor(Date.now() / 1000);

            if (modoVista === 'TODOS') {
                let generalBlock = document.createElement('div');
                generalBlock.className = 'server-block';
                let htmlContent = `<div class="server-header"><div class="server-title">🔥 VISTA GENERAL DE TIMERS (TODOS LOS SERVIDORES)</div></div><div class="boss-grid">`;
                let todosLosBosses = [];

                serversDisponibles.forEach(svr => {
                    const bossesServidor = timers[svr] || {};

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
                            const finVentanaUnix = targetUnix + 3600;

                            if (diffSec > 0) {
                                statusState = 'cd'; prioridadOrden = diffSec;
                                const h = Math.floor(diffSec / 3600), m = Math.floor((diffSec % 3600) / 60), s = diffSec % 60;
                                displayTimer = `<div class="timer-badge status-cd">🔴 ${h > 0 ? h + 'h ' : ''}${m < 10 ? '0':''}${m}m ${s < 10 ? '0':''}${s}s</div>`;
                            } else if (ahoraUnix >= targetUnix && ahoraUnix <= finVentanaUnix) {
                                statusState = 'window'; prioridadOrden = -500;
                                const winSec = finVentanaUnix - ahoraUnix;
                                const m = Math.floor(winSec / 60), s = winSec % 60;
                                displayTimer = `<div class="timer-badge status-window">🟡 VENTANA (${m}m ${s < 10 ? '0':''}${s}s)</div>`;
                            } else {
                                if (BOSSES_MANUALES_LIST.includes(bossName)) continue;
                                const vivoSec = ahoraUnix - finVentanaUnix;
                                prioridadOrden = -1000 - vivoSec;
                                const h = Math.floor(vivoSec / 3600), m = Math.floor((vivoSec % 3600) / 60), s = vivoSec % 60;
                                displayTimer = `<div class="timer-badge status-alive">🟢 VIVO +${h > 0 ? h + 'h ' : ''}${m}m ${s < 10 ? '0':''}${s}s</div>`;
                            }
                        } else {
                            if (BOSSES_MANUALES_LIST.includes(bossName)) continue;
                            prioridadOrden = -999;
                            displayTimer = `<div class="timer-badge status-alive">🟢 ¡VIVO!</div>`;
                        }

                        todosLosBosses.push({ svr, bossName, statusState, displayTimer, prioridadOrden });
                    }
                });

                todosLosBosses.sort((a, b) => a.prioridadOrden - b.prioridadOrden);

                todosLosBosses.forEach(b => {
                    const tagServer = obtenerTagServer(b.svr);
                    htmlContent += `
                        <div class="boss-card">
                            <span class="server-badge-top">${tagServer}</span>
                            <div><div class="boss-name">${b.bossName}</div></div>
                            ${b.displayTimer}
                            <div class="actions-group">
                                <button type="button" class="btn-action" onclick="enviarKill('${b.svr}', '${b.bossName}')">⚔️ Kill</button>
                                ${b.statusState !== 'alive' ? `
                                <button type="button" class="btn-action btn-reset" onclick="enviarReset('${b.svr}', '${b.bossName}')">✖</button>` : ''}
                            </div>
                        </div>
                    `;
                });

                htmlContent += `</div>`;
                generalBlock.innerHTML = htmlContent;
                container.appendChild(generalBlock);

            } else {
                const svr = modoVista;
                let serverBlock = document.createElement('div');
                serverBlock.className = 'server-block';
                const pcOrigen = ultimosReportes[svr] || 'Sin reportes';
                const pjOrigen = ultimosPjs[svr] || 'Desconocido';
                let esOnline = false;

                if (heartbeats[svr]) {
                    const fechaLimpia = heartbeats[svr].replace(' ', 'T');
                    const hbUnix = Math.floor(new Date(fechaLimpia).getTime() / 1000);
                    if (!isNaN(hbUnix) && Math.abs(ahoraUnix - hbUnix) <= 60) esOnline = true;
                }

                const statusHtml = esOnline 
                    ? `<span><span class="status-dot dot-online"></span><strong style="color:#2ecc71;">ONLINE</strong></span>`
                    : `<span><span class="status-dot dot-offline"></span><strong style="color:#ff4757;">OFFLINE</strong></span>`;

                let htmlContent = `
                    <div class="server-header"><div class="server-title">${svr}</div><div>${statusHtml}</div></div>
                    <div class="bot-status-container"><div class="pj-badge">👤 PJ: ${pjOrigen}</div><div class="pc-badge">💻 PC: ${pcOrigen}</div></div>
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
                        const finVentanaUnix = targetUnix + 3600;

                        if (diffSec > 0) {
                            statusState = 'cd'; prioridadOrden = diffSec;
                            const h = Math.floor(diffSec / 3600), m = Math.floor((diffSec % 3600) / 60), s = diffSec % 60;
                            displayTimer = `<div class="timer-badge status-cd">🔴 ${h > 0 ? h + 'h ' : ''}${m < 10 ? '0':''}${m}m ${s < 10 ? '0':''}${s}s</div>`;
                        } else if (ahoraUnix >= targetUnix && ahoraUnix <= finVentanaUnix) {
                            statusState = 'window'; prioridadOrden = -500;
                            const winSec = finVentanaUnix - ahoraUnix;
                            const m = Math.floor(winSec / 60), s = winSec % 60;
                            displayTimer = `<div class="timer-badge status-window">🟡 VENTANA (${m}m ${s < 10 ? '0':''}${s}s)</div>`;
                        } else {
                            if (BOSSES_MANUALES_LIST.includes(bossName)) continue;
                            const vivoSec = ahoraUnix - finVentanaUnix;
                            prioridadOrden = -1000 - vivoSec;
                            const h = Math.floor(vivoSec / 3600), m = Math.floor((vivoSec % 3600) / 60), s = vivoSec % 60;
                            displayTimer = `<div class="timer-badge status-alive">🟢 VIVO +${h > 0 ? h + 'h ' : ''}${m}m ${s < 10 ? '0':''}${s}s</div>`;
                        }
                    } else {
                        if (BOSSES_MANUALES_LIST.includes(bossName)) continue;
                        prioridadOrden = -999;
                        displayTimer = `<div class="timer-badge status-alive">🟢 ¡VIVO!</div>`;
                    }

                    bossesProcesados.push({ bossName, statusState, displayTimer, prioridadOrden });
                }

                bossesProcesados.sort((a, b) => a.prioridadOrden - b.prioridadOrden);

                const tagServer = obtenerTagServer(svr);
                bossesProcesados.forEach(b => {
                    htmlContent += `
                        <div class="boss-card">
                            <span class="server-badge-top">${tagServer}</span>
                            <div><div class="boss-name">${b.bossName}</div></div>
                            ${b.displayTimer}
                            <div class="actions-group">
                                <button type="button" class="btn-action" onclick="enviarKill('${svr}', '${b.bossName}')">⚔️ Kill</button>
                                ${b.statusState !== 'alive' ? `
                                <button type="button" class="btn-action btn-reset" onclick="enviarReset('${svr}', '${b.bossName}')">✖</button>` : ''}
                            </div>
                        </div>
                    `;
                });

                htmlContent += `</div>`;
                serverBlock.innerHTML = htmlContent;
                container.appendChild(serverBlock);
            }
        }
        setInterval(pedirTimers, 1000);
        pedirTimers();
    </script>
</body>
</html>
"""

HTML_CAMBIO_CLAVE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>🔑 Primer Ingreso - Cambiar Contraseña</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #0a0814; color: #e6e1ff; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .box { background: #141126; border: 1px solid #7b2cbf; border-radius: 12px; padding: 30px; width: 340px; box-shadow: 0 0 20px rgba(123, 44, 191, 0.3); text-align: center; }
        h3 { color: #9d4edd; margin-top: 0; }
        input { width: 100%; padding: 10px; margin-bottom: 12px; background: #0d0a1a; border: 1px solid #2a244d; color: #fff; border-radius: 6px; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background: #2ecc71; border: none; color: white; border-radius: 6px; font-weight: bold; cursor: pointer; }
        button:hover { background: #27ae60; }
        .error { color: #ff4757; font-size: 0.85rem; margin-bottom: 12px; }
    </style>
</head>
<body>
    <div class="box">
        <h3>🔑 Primer Ingreso Detectado</h3>
        <p style="font-size:0.85rem; color:#8e85b8; margin-bottom:20px;">Por seguridad de la guild, debes establecer tu propia contraseña personal antes de continuar.</p>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form action="/action/cambiar_clave_inicial" method="POST">
            <input type="password" name="nueva_clave" placeholder="Nueva Contraseña" required minlength="4">
            <input type="password" name="confirmar_clave" placeholder="Confirmar Nueva Contraseña" required minlength="4">
            <button type="submit">🔒 Guardar y Continuar</button>
        </form>
    </div>
</body>
</html>
"""

# === RUTAS Y CONTROL DE ACCESO ===
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    if username == "admin" and password == "admin123":
        session['user'] = "admin"
        return redirect(url_for('index') + '#donaciones')

    try:
        url = f"{SUPABASE_URL}/rest/v1/usuarios?username=eq.{username}&select=*"
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200 and res.json():
            usr_data = res.json()[0]
            if check_password_hash(usr_data.get('password_hash', ''), password):
                session['user'] = usr_data.get('username')
                
                if usr_data.get('requiere_cambio_clave', True):
                    session['cambio_clave_pendiente'] = True
                    return render_template_string(HTML_CAMBIO_CLAVE)

                return redirect(url_for('index') + '#donaciones')
    except Exception as e:
        print(f"Error en login: {e}")

    return redirect(url_for('index'))

@app.route('/action/cambiar_clave_inicial', methods=['POST'])
def cambiar_clave_inicial():
    if 'user' not in session or not session.get('cambio_clave_pendiente'):
        return redirect(url_for('index'))

    nueva_clave = request.form.get("nueva_clave")
    confirmar_clave = request.form.get("confirmar_clave")

    if nueva_clave != confirmar_clave:
        return render_template_string(HTML_CAMBIO_CLAVE, error="Las contraseñas no coinciden.")

    try:
        pass_hash = generate_password_hash(nueva_clave)
        url_patch = f"{SUPABASE_URL}/rest/v1/usuarios?username=eq.{session['user']}"
        payload = {
            "password_hash": pass_hash,
            "requiere_cambio_clave": False
        }
        requests.patch(url_patch, headers=HEADERS, json=payload, timeout=5)
        session.pop('cambio_clave_pendiente', None)
        return redirect(url_for('index') + '#donaciones')
    except Exception as e:
        return render_template_string(HTML_CAMBIO_CLAVE, error="Error actualizando clave.")

@app.route('/admin/crear_usuario', methods=['POST'])
def crear_usuario():
    if session.get('user') != 'admin':
        return redirect(url_for('index'))

    nuevo_usuario = request.form.get("nuevo_usuario")
    clave_inicial = request.form.get("clave_inicial")

    if nuevo_usuario and clave_inicial:
        try:
            pass_hash = generate_password_hash(clave_inicial)
            url_post = f"{SUPABASE_URL}/rest/v1/usuarios"
            payload = {
                "username": nuevo_usuario.strip(),
                "password_hash": pass_hash,
                "rol": "encargado",
                "requiere_cambio_clave": True,
                "creado_por": "admin"
            }
            res = requests.post(url_post, headers=HEADERS, json=payload, timeout=5)
            print(f"[CREAR USUARIO STATUS]: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"[Error creando usuario]: {e}")

    return redirect(url_for('index') + '#donaciones')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, link_descarga=LINK_DESCARGA_BOT)

@app.route('/api/timers', methods=['GET'])
def get_timers():
    timers_map, pcs_map, pj_map, hb_map = obtener_datos()
    return jsonify({
        "timers": timers_map, "cooldowns": COOLDOWNS, 
        "servers": SERVIDORES, "ultimas_pcs": pcs_map, 
        "ultimos_pjs": pj_map, "heartbeats": hb_map
    })

@app.route('/api/donaciones', methods=['GET'])
def get_donaciones():
    try:
        url = f"{SUPABASE_URL}/rest/v1/donaciones?select=*&order=created_at.desc"
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200: return jsonify(res.json()), 200
    except Exception: pass
    return jsonify([]), 200

@app.route('/action/donar', methods=['POST'])
def action_donar():
    if 'user' not in session: return redirect(url_for('index'))

    pj_name = request.form.get("pj_name")
    tipo_donacion = request.form.get("tipo_donacion")
    cantidad = request.form.get("cantidad", 1)

    if pj_name and tipo_donacion:
        try:
            url_post = f"{SUPABASE_URL}/rest/v1/donaciones"
            payload = {
                "pj_name": pj_name, "tipo_donacion": tipo_donacion,
                "cantidad": int(cantidad), "registrado_por": session.get('user', 'Encargado')
            }
            requests.post(url_post, headers=HEADERS, json=payload, timeout=5)
        except Exception as e: print(f"Error registrando donación: {e}")

    return redirect(url_for('index') + '#donaciones')

@app.route('/action/editar_donacion', methods=['POST'])
def action_editar_donacion():
    if 'user' not in session: return redirect(url_for('index'))

    donacion_id = request.form.get("id")
    nueva_cantidad = request.form.get("nueva_cantidad")

    if donacion_id and nueva_cantidad:
        try:
            ahora_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            url_patch = f"{SUPABASE_URL}/rest/v1/donaciones?id=eq.{donacion_id}"
            payload = {
                "cantidad": int(nueva_cantidad),
                "modificado_por": session.get('user', 'Encargado'),
                "fecha_modificacion": ahora_iso
            }
            requests.patch(url_patch, headers=HEADERS, json=payload, timeout=5)
        except Exception as e: print(f"Error modificando donación: {e}")

    return redirect(url_for('index') + '#donaciones')

@app.route('/action/kill', methods=['POST'])
def action_kill():
    svr = request.form.get("server") or request.args.get("server")
    boss = request.form.get("boss") or request.args.get("boss")
    custom_timer = request.form.get("custom_timer") or request.args.get("custom_timer")
    custom_min = int(custom_timer) if custom_timer else None

    if svr and boss: guardar_boss(svr, boss, "Navegador Web", "Web", custom_minutes=custom_min)
    return jsonify({"status": "ok"}), 200

@app.route('/action/reset', methods=['POST'])
def action_reset():
    svr = request.form.get("server") or request.args.get("server")
    boss = request.form.get("boss") or request.args.get("boss")
    if svr and boss: borrar_boss(svr, boss)
    return jsonify({"status": "ok"}), 200

@app.route('/api/kill', methods=['POST'])
def api_kill():
    data = request.get_json(silent=True) or {}
    svr, boss, pc_id, pj_name = data.get("server"), data.get("boss"), data.get("pc_id", "Desconocida"), data.get("pj_name", "Desconocido")
    if boss in BOSSES_MANUALES and pc_id != "Navegador Web": return jsonify({"status": "ignored_manual_only"}), 200
    if svr and boss: guardar_boss(svr, boss, pc_id, pj_name); return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

@app.route('/api/heartbeat', methods=['POST'])
def api_heartbeat():
    data = request.get_json(silent=True) or {}
    svr, pc_id, pj_name = data.get("server"), data.get("pc_id", "Desconocida"), data.get("pj_name", "Desconocido")
    if svr: actualizar_heartbeat(svr, pc_id, pj_name); return jsonify({"status": "ok"}), 200
    return jsonify({"status": "error"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
