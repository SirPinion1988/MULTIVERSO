# Memoria de control por Server + Boss + PJ
# Estructura: {"Server_Boss_PJ": timestamp_ultima_lectura}
ultimos_kills_recientes = {}

@app.route('/api/kill', methods=['POST'])
def registrar_kill():
    data = request.json or {}
    server = data.get('server')
    boss_raw = data.get('boss', '').strip()
    pc_id = data.get('pc_id', 'Manual Web')
    pj_name = data.get('pj_name', 'Manual Web')

    if not server or not boss_raw:
        return jsonify({"error": "Faltan datos"}), 400

    import re
    boss = re.sub(r'\s+\d+$', '', boss_raw)

    now_unix = int(time.time())
    
    # Clave combinada: Server + Boss + PJ
    clave_cartel = f"{server}_{boss}_{pj_name}"

    # 1. BLOQUEO DE CARTEL REPETIDO (Mismo PJ + Mismo Boss en menos de 120s)
    if pc_id != 'Manual Web':
        ultimo_registro = ultimos_kills_recientes.get(clave_cartel, 0)
        
        if (now_unix - ultimo_registro) < 120:
            return jsonify({
                "status": "ignored", 
                "message": f"Cartel duplicado de {boss} por {pj_name} ignorado."
            }), 200

        ultimos_kills_recientes[clave_cartel] = now_unix

    # 2. REGISTRO EFECTIVO DE KILL
    if server not in status_timers:
        status_timers[server] = {}

    status_timers[server][boss] = now_unix

    clave_card = f"{server}_{boss}"
    if clave_card in tarjetas_ocultas_global:
        tarjetas_ocultas_global.remove(clave_card)

    guardar_json(DATA_FILE, status_timers)

    if pc_id != 'Manual Web':
        heartbeats[server] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ultimas_pcs[server] = pc_id
        ultimos_pjs[server] = pj_name

    # Sincronización en Supabase
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

    return jsonify({"status": "ok", "message": f"Kill de {boss} por {pj_name} registrado"}), 200
