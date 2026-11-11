# --- API ASISTENCIAS DE INVASIONES (RANKING ACUMULADO) ---
@app.route('/api/asistencias-ranking', methods=['GET', 'POST'])
def api_asistencias_ranking():
    conn = get_db()
    if request.method == 'GET':
        ranking = []
        if conn:
            try:
                with conn.cursor() as cur:
                    # Agrupa y suma las asistencias por PJ ordenadas de mayor a menor
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
    delta = int(data.get('delta', 1)) # Puede ser +1 o -1

    if not pj_name: return jsonify({"error": "Falta PJ"}), 400

    conn = get_db()
    if conn:
        try:
            with conn.cursor() as cur:
                if delta < 0:
                    # Restar asistencia (buscamos un registro positivo para disminuir o insertamos negativo)
                    cur.execute("""
                        INSERT INTO public.asistencias_invasiones (pj_name, cantidad, registrado_por)
                        VALUES (%s, %s, %s);
                    """, (pj_name, delta, session.get('user', 'Sistema')))
                else:
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


# --- API DONACIONES DE JOYAS Y BANCO GUILD ---
@app.route('/api/donaciones-joyas', methods=['GET', 'POST', 'DELETE'])
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
                    # Historial de donaciones detalladas por miembro
                    cur.execute("SELECT id, pj_name, bless, soul, life, chaos, creation, zen, registrado_por, created_at FROM public.donaciones_joyas ORDER BY created_at DESC;")
                    registros = cur.fetchall()

                    # Calcular totales de donaciones
                    cur.execute("SELECT SUM(bless) as bless, SUM(soul) as soul, SUM(life) as life, SUM(chaos) as chaos, SUM(creation) as creation, SUM(zen) as zen FROM public.donaciones_joyas;")
                    t = cur.fetchone()
                    if t:
                        banco_total = {k: (t[k] or 0) for k in banco_total}

                    # Obtener gastos de la guild
                    cur.execute("SELECT id, motivo, bless, soul, life, chaos, creation, zen, registrado_por, created_at FROM public.guild_gastos ORDER BY created_at DESC;")
                    gastos_lista = cur.fetchall()

                    # Calcular total de gastos
                    cur.execute("SELECT SUM(bless) as bless, SUM(soul) as soul, SUM(life) as life, SUM(chaos) as chaos, SUM(creation) as creation, SUM(zen) as zen FROM public.guild_gastos;")
                    g = cur.fetchone()
                    if g:
                        gastos_total = {k: (g[k] or 0) for k in gastos_total}

                conn.close()
            except Exception as e:
                print(e)
                if conn: conn.close()

        # Banco Neto (Donaciones menos Gastos)
        banco_neto = {k: banco_total[k] - gastos_total[k] for k in banco_total}

        return jsonify({
            "donaciones": registros,
            "banco_guild": banco_neto,
            "gastos": gastos_lista
        })

    if not usuario_es_autorizado(): return jsonify({"error": "No autorizado."}), 403
    data = request.json or {}
    
    if request.method == 'POST':
        pj_name = data.get('pj_name', '').strip()
        bless = int(data.get('bless', 0))
        soul = int(data.get('soul', 0))
        life = int(data.get('life', 0))
        chaos = int(data.get('chaos', 0))
        creation = int(data.get('creation', 0))
        zen = int(data.get('zen', 0))

        if not pj_name: return jsonify({"error": "Falta PJ"}), 400

        conn = get_db()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.donaciones_joyas (pj_name, bless, soul, life, chaos, creation, zen, registrado_por)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """, (pj_name, bless, soul, life, chaos, creation, zen, session.get('user', 'Sistema')))
                    conn.commit()
                conn.close()
            except Exception as e:
                if conn: conn.close()
                return jsonify({"error": str(e)}), 500
        return jsonify({"status": "ok"}), 201


# --- API GASTOS / USOS DEL ACUMULADO ---
@app.route('/api/guild-gastos', methods=['POST', 'DELETE'])
def api_guild_gastos():
    if not usuario_es_autorizado(): return jsonify({"error": "No autorizado."}), 403
    conn = get_db()
    data = request.json or {}
    
    if request.method == 'POST':
        motivo = data.get('motivo', '').strip()
        bless = int(data.get('bless', 0))
        soul = int(data.get('soul', 0))
        life = int(data.get('life', 0))
        chaos = int(data.get('chaos', 0))
        creation = int(data.get('creation', 0))
        zen = int(data.get('zen', 0))

        if not motivo: return jsonify({"error": "Falta motivo del gasto"}), 400

        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.guild_gastos (motivo, bless, soul, life, chaos, creation, zen, registrado_por)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """, (motivo, bless, soul, life, chaos, creation, zen, session.get('user', 'Sistema')))
                    conn.commit()
                conn.close()
            except Exception as e:
                if conn: conn.close()
                return jsonify({"error": str(e)}), 500
        return jsonify({"status": "ok"}), 201

    if request.method == 'DELETE':
        if not usuario_es_admin(): return jsonify({"error": "Solo Pinion."}), 403
        g_id = data.get('id')
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM public.guild_gastos WHERE id = %s;", (g_id,))
                    conn.commit()
                conn.close()
            except Exception: pass
        return jsonify({"status": "ok"}), 200
