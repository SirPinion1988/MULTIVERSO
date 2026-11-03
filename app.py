# --- MÓDULO VISOR DE ITEMS MU ONLINE ---

ITEMS_FILE = "items_mu_data.json"

# Estructura de ejemplo basada en tu captura (Excellent Bronze Gloves)
DEFAULT_ITEMS = [
    {
        "id": 1,
        "nombre": "Excellent Bronze Gloves",
        "tipo": "Gloves",
        "tier": "Excellent",
        "base_score": 7,
        "grade_score": 87,
        "defense": 21,
        "durability": "49/49",
        "requisitos": {
            "strength": 111,
            "agility": 42
        },
        "clases": ["Dark Knight", "Magic Gladiator", "Dark Lord"],
        "opciones": [
            "[Rare] Increases maximum SD +3%",
            "[Rare] Damage decrease +3%",
            "[Legendary] Critical damage resistance +8%"
        ],
        "bonus_excelente": [
            "Increases Strength +30",
            "Increases Agility +26"
        ],
        # Reemplazar con el ID del archivo en tu Google Drive
        "drive_id": "TU_ID_DE_IMAGEN_DRIVE" 
    }
]

items_mu_db = cargar_json(ITEMS_FILE, DEFAULT_ITEMS)


@app.route('/items')
def vista_items():
    """Renderiza la ventana / galería de ítems de MU Online."""
    return render_template('items.html')


@app.route('/api/items', methods=['GET', 'POST'])
def api_items():
    """API para obtener y registrar items del catálogo."""
    global items_mu_db
    if request.method == 'GET':
        return jsonify(items_mu_db)

    if request.method == 'POST':
        if 'user' not in session or session.get('rol') != 'admin':
            return jsonify({"error": "No autorizado"}), 403

        data = request.json or {}
        if not data.get('nombre') or not data.get('drive_id'):
            return jsonify({"error": "Nombre y Drive ID son requeridos"}), 400

        nuevo_item = {
            "id":
