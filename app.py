import io
import pandas as pd

# --- EXPORTAR ÍTEMS ASIGNADOS A MIEMBROS EN EXCEL ---
@app.route('/api/backup/exportar-items-asignados', methods=['GET'])
def exportar_items_asignados():
    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado."}), 403
    conn = get_db()
    items = []
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nombre, tipo, asignado_a, opciones FROM public.items_mu WHERE asignado_a IS NOT NULL AND asignado_a != '' ORDER BY asignado_a ASC;")
                items = cur.fetchall()
            conn.close()
        except Exception:
            if conn: conn.close()

    # Preparar datos para DataFrame
    rows = []
    for itm in items:
        opciones_str = ", ".join(normalizar_campo_json(itm.get('opciones'), []))
        rows.append({
            "ID Ítem": itm.get('id'),
            "Nombre": itm.get('nombre'),
            "Tipo": itm.get('tipo'),
            "Miembro Asignado": itm.get('asignado_a'),
            "Opciones": opciones_str
        })
    
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Items_Asignados')
    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name=f"Items_Asignados_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# --- EXPORTAR LISTADO DE ASISTENCIAS EN EXCEL ---
@app.route('/api/backup/exportar-asistencias', methods=['GET'])
def exportar_asistencias():
    if not usuario_es_autorizado():
        return jsonify({"error": "No autorizado."}), 403
    conn = get_db()
    ranking = []
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT pj_name as "Miembro (PJ)", SUM(cantidad) as "Asistencias Totales"
                    FROM public.asistencias_invasiones
                    GROUP BY pj_name
                    ORDER BY "Asistencias Totales" DESC;
                """)
                ranking = cur.fetchall()
            conn.close()
        except Exception:
            if conn: conn.close()

    df = pd.DataFrame(ranking)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Asistencias_Invasiones')
    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name=f"Asistencias_Invasiones_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# --- IMPORTAR EXCEL GENERAL DESDE LA WEB ---
@app.route('/api/backup/importar-excel', methods=['POST'])
def importar_excel_web():
    if not usuario_es_admin():
        return jsonify({"error": "Solo el administrador (Pinion) puede importar respaldos."}), 403
    if 'file' not in request.files:
        return jsonify({"error": "No se adjuntó ningún archivo Excel."}), 400
    
    file = request.files['file']
    try:
        # Leer el archivo Excel usando pandas
        xls = pd.ExcelFile(file)
        conn = get_db()
        if not conn: return jsonify({"error": "Sin conexión a la base de datos."}), 500
        
        with conn.cursor() as cur:
            # Si trae la pestaña de ítems o asistencias, las procesamos de forma flexible
            if 'Items_Asignados' in xls.sheet_names:
                df_items = pd.read_excel(xls, 'Items_Asignados')
                for _, row in df_items.iterrows():
                    item_id = row.get('ID Ítem')
                    asignado = row.get('Miembro Asignado')
                    if pd.notna(item_id) and pd.notna(asignado):
                        cur.execute("UPDATE public.items_mu SET asignado_a = %s WHERE id = %s;", (str(asignado), int(item_id)))
            
            if 'Asistencias_Invasiones' in xls.sheet_names:
                df_asist = pd.read_excel(xls, 'Asistencias_Invasiones')
                for _, row in df_asist.iterrows():
                    pj = row.get('Miembro (PJ)')
                    cant = row.get('Asistencias Totales')
                    if pd.notna(pj) and pd.notna(cant):
                        # Actualizar o insertar registro limpio en asistencias
                        cur.execute("DELETE FROM public.asistencias_invasiones WHERE pj_name = %s;", (str(pj),))
                        cur.execute("INSERT INTO public.asistencias_invasiones (pj_name, cantidad, registrado_por) VALUES (%s, %s, 'Importación Web');", (str(pj), int(cant)))
            
            conn.commit()
        conn.close()
    except Exception as e:
        return jsonify({"error": f"Error al procesar el archivo Excel: {str(e)}"}), 500
        
    return jsonify({"status": "ok"}), 200
