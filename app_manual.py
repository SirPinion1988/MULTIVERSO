from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'multiverso_mu_produccion_secret'

# Los 3 usuarios autorizados
USUARIOS_AUTORIZADOS = {
    "admin1": "Mistermagu2022*",
    "admin2": "MuOnline2026",
    "soporte": "MultiversoSecure"
}

# Catálogo manual inicial en memoria (rápido, sin caídas de base de datos)
CATALOGO_MANUAL = [
    {
        "id": "1", 
        "nombre": "Excellent Dragon Armor", 
        "tipo": "Armor", 
        "baul": "Baúl Principal", 
        "asignado": "SirPinion",
        "opciones": ["Reducción de daño (Damage Decrease: 4%)", "Aumento de HP máximo (4%)"], 
        "bonus": ["Fuerza +50", "Vitalidad +30"]
    }
]

SETS_POR_CLASE = {
    "Dark Knight (BK / Guerrero)": ["Leather", "Bronze", "Scale", "Brass", "Plate", "Dragon", "Phoenix", "Great Dragon", "Black Dragon", "Dragon Knight", "Titan", "Brave"],
    "Dark Wizard (SM / Mago)": ["Pad", "Bone", "Sphinx", "Legendary", "Grand Soul", "Dark Soul", "Eclipse", "Hades"],
    "Fairy Elf (ELF / Arquera)": ["Vine", "Silk", "Wind", "Spirit", "Guardian", "Divine", "Iris", "Seraphim"],
    "Magic Gladiator (MG)": ["Scale", "Dragon", "Legendary", "Storm Crow", "Thunder Hawk", "Valiant", "Destroyer"],
    "Dark Lord (DL)": ["Light Plate", "Adamantine", "Dark Steel", "Glorious", "Sovereign", "Emperor"],
    "Summoner (SU)": ["Mystery", "Red Wing", "Ancient", "Demonic", "Queen"],
    "Rage Fighter (RF)": ["Sacred", "Holly Storm", "Piercing", "Phoenix Soul"]
}

TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>MULTIVERSO - Armaduras & Clan</title>
    <style>
        body { background-color: #0f0f1a; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; }
        h1, h2 { color: #00d2ff; text-align: center; }
        .container { max-width: 1100px; margin: 0 auto; background: #1a1a2e; padding: 30px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.7); }
        
        .user-bar { display: flex; justify-content: space-between; align-items: center; background: #0f0f1a; padding: 10px 15px; border-radius: 6px; margin-bottom: 20px; border: 1px solid #4a4e69; }
        .user-bar span { color: #00d2ff; font-weight: bold; }
        .btn-logout { background: #ff4d4d; color: #fff; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 14px; }
        .btn-login { background: #00d2ff; color: #0f0f1a; padding: 6px 15px; text-decoration: none; border-radius: 4px; font-weight: bold; }

        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .form-group { margin-bottom: 15px; }
        .form-group.full { grid-column: span 2; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #a29bfe; }
        input[type="text"], input[type="password"], select { width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #4a4e69; background: #16213e; color: #fff; box-sizing: border-box; }
        .checkbox-container { display: flex; gap: 15px; flex-wrap: wrap; background: #16213e; padding: 10px; border-radius: 6px; border: 1px solid #4a4e69; }
        .checkbox-container label { color: #fff; font-weight: normal; display: flex; align-items: center; gap: 6px; cursor: pointer; }
        button { background: linear-gradient(135deg, #00b4d8, #0077b6); color: white; border: none; padding: 12px 20px; font-size: 16px; border-radius: 6px; cursor: pointer; width: 100%; font-weight: bold; transition: 0.3s; margin-top: 10px; }
        button:hover { background: linear-gradient(135deg, #0077b6, #03045e); }
        
        .alert-error { background: #ff4d4d; color: #fff; padding: 10px; border-radius: 6px; margin-bottom: 15px; text-align: center; font-weight: bold; }
        .alert-success { background: #2ec4b6; color: #000; padding: 10px; border-radius: 6px; margin-bottom: 15px; text-align: center; font-weight: bold; }

        .filters-bar { display: flex; gap: 15px; margin-top: 30px; margin-bottom: 20px; flex-wrap: wrap; }
        .filters-bar input, .filters-bar select { flex: 1; min-width: 200px; padding: 10px; border-radius: 6px; border: 1px solid #4a4e69; background: #16213e; color: #fff; }
        
        .items-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }
        .item-card { background: #16213e; border: 1px solid #4a4e69; border-radius: 8px; padding: 15px; position: relative; }
        .item-card h3 { margin: 0 0 10px 0; color: #00d2ff; font-size: 18px; }
        .tag { background: #0f3460; color: #00d2ff; padding: 3px 8px; border-radius: 4px; font-size: 12px; display: inline-block; margin-right: 5px; margin-bottom: 5px; }
        .badge-opt { background: #00b4d8; color: #000; }
        .badge-bonus { background: #a29bfe; color: #000; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ MULTIVERSO - ARMADURAS & CLAN</h1>

        <div class="user-bar">
            {% if session.get('usuario') %}
                <span>👤 Admin Activo: <strong>{{ session['usuario'] }}</strong></span>
                <a href="/logout" class="btn-logout">Cerrar Sesión</a>
            {% else %}
                <span>🔒 Modo Lectura (Edición restringida a administradores)</span>
                <a href="/login" class="btn-login">🔑 Login Admin</a>
            {% endif %}
        </div>

        {% if error %}
            <div class="alert-error">{{ error }}</div>
        {% endif %}
        {% if mensaje %}
            <div class="alert-success">{{ mensaje }}</div>
        {% endif %}

        {% if session.get('usuario') %}
        <div style="background: #16213e; padding: 20px; border-radius: 8px; border: 1px dashed #00d2ff; margin-bottom: 30px;">
            <h2>➕ Agregar Ítem al Listado Manual</h2>
            <form method="POST" action="/guardar-manual">
                <div class="form-grid">
                    
                    <div class="form-group">
                        <label for="set_base">📜 Scroll 1: Seleccionar Set de Armadura:</label>
                        <select id="set_base" name="set_base" required>
                            <option value="">-- Seleccionar Set --</option>
                            {% for clase, sets in sets_clases.items() %}
                                <optgroup label="{{ clase }}">
                                    {% for s in sets %}
                                        <option value="{{ s }} ({{ clase.split(' ')[0] }})">Set {{ s }}</option>
                                    {% endfor %}
                                </optgroup>
                            {% endfor %}
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="tipo">📦 Scroll 2: Tipo de Pieza:</label>
                        <select id="tipo" name="tipo" required>
                            <option value="Armor">Armor (Pechera)</option>
                            <option value="Pants">Pants (Pantalón)</option>
                            <option value="Helm">Helm (Casco)</option>
                            <option value="Gloves">Gloves (Guantes)</option>
                            <option value="Boots">Boots (Botas)</option>
                            <option value="Shield">Shield (Escudo)</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="baul">🏰 Nombre del Baúl:</label>
                        <input type="text" id="baul" name="baul" required placeholder="Ej: Baúl Principal">
                    </div>

                    <div class="form-group">
                        <label for="asignado">👤 Asignado a (Miembro del Clan):</label>
                        <input type="text" id="asignado" name="asignado" required placeholder="Ej: SirPinion">
                    </div>

                    <div class="form-group full">
                        <label>✨ Opciones Excellent (Exc):</label>
                        <div class="checkbox-container">
                            <label><input type="checkbox" name="opciones" value="Aumento de HP máximo (3-5%)"> Aumento de HP máximo (3-5%)</label>
                            <label><input type="checkbox" name="opciones" value="Aumento de SD máximo (3-5%)"> Aumento de SD máximo (3-5%)</label>
                            <label><input type="checkbox" name="opciones" value="Reducción de daño (Damage Decrease: 3-5%)"> Reducción de daño (Damage Decrease: 3-5%)</label>
                            <label><input type="checkbox" name="opciones" value="Reflejo de daño (Reflect Damage: 3-5%)"> Reflejo de daño (Reflect Damage: 3-5%)</label>
                            <label><input type="checkbox" name="opciones" value="Resistencia a daño crítico (7-10%)"> Resistencia a daño crítico (7-10%)</label>
                            <label><input type="checkbox" name="opciones" value="Tasa de drop de Zen (21-30%)"> Tasa de drop de Zen (21-30%)</label>
                        </div>
                    </div>

                    <div class="form-group full">
                        <label>💪 Atributos y Bonus (Fuerza, Agilidad, Vitalidad, Energía, Command):</label>
                        <div class="checkbox-container">
                            <label><input type="checkbox" name="bonus" value="Fuerza (Strength) +50"> Fuerza +50</label>
                            <label><input type="checkbox" name="bonus" value="Agilidad (Agility) +50"> Agilidad +50</label>
                            <label><input type="checkbox" name="bonus" value="Vitalidad (Vitality) +150"> Vitalidad +150</label>
                            <label><input type="checkbox" name="bonus" value="Energía (Energy) +50"> Energía +50</label>
                            <label><input type="checkbox" name="bonus" value="Command (DL) +25"> Command (DL) +25</label>
                        </div>
                    </div>

                </div>
                <button type="submit">💾 Guardar Ítem</button>
            </form>
        </div>
        {% endif %}

        <h2>🔍 Buscador de Baúles e Inventario</h2>
        <div class="filters-bar">
            <input type="text" id="inputBuscador" placeholder="Buscar por nombre, baúl o asignado..." onkeyup="filtrarItems()">
            <select id="filtroTipo" onchange="filtrarItems()">
                <option value="">-- Filtrar por Tipo de Pieza --</option>
                <option value="Armor">Armor</option>
                <option value="Pants">Pants</option>
                <option value="Helm">Helm</option>
                <option value="Gloves">Gloves</option>
                <option value="Boots">Boots</option>
                <option value="Shield">Shield</option>
            </select>
        </div>

        <div class="items-grid" id="grillaItems">
            {% for item in items %}
            <div class="item-card" data-nombre="{{ item.nombre | lower }}" data-tipo="{{ item.tipo }}" data-baul="{{ item.baul | lower }}" data-asignado="{{ item.asignado | lower }}">
                <h3>{{ item.nombre }}</h3>
                <p><strong>Tipo:</strong> <span class="tag">{{ item.tipo }}</span> | <strong>Baúl:</strong> <span class="tag">{{ item.baul }}</span></p>
                <p><strong>Asignado a:</strong> <span style="color: #00d2ff;">{{ item.asignado }}</span></p>
                <p><strong>Opciones Exc:</strong><br>
                    {% for opt in item.opciones %}
                        <span class="tag badge-opt">{{ opt }}</span>
                    {% endfor %}
                </p>
                <p><strong>Bonus / Atributos:</strong><br>
                    {% for bon in item.bonus %}
                        <span class="tag badge-bonus">{{ bon }}</span>
                    {% endfor %}
                </p>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        function filtrarItems() {
            let texto = document.getElementById('inputBuscador').value.toLowerCase();
            let tipoSeleccionado = document.getElementById('filtroTipo').value;
            let tarjetas = document.getElementsByClassName('item-card');

            for (let card of tarjetas) {
                let nombre = card.getAttribute('data-nombre');
                let tipo = card.getAttribute('data-tipo');
                let baul = card.getAttribute('data-baul');
                let asignado = card.getAttribute('data-asignado');

                let coincideTexto = nombre.includes(texto) || baul.includes(texto) || asignado.includes(texto);
                let coincideTipo = (tipoSeleccionado === "" || tipo === tipoSeleccionado);

                card.style.display = (coincideTexto && coincideTipo) ? "block" : "none";
            }
        }
    </script>
</body>
</html>
"""

TEMPLATE_LOGIN = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Login - Administradores</title>
    <style>
        body { background-color: #0f0f1a; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-box { background: #1a1a2e; padding: 40px; border-radius: 12px; width: 320px; box-shadow: 0 8px 24px rgba(0,0,0,0.8); border: 1px solid #4a4e69; }
        h2 { color: #00d2ff; text-align: center; margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; color: #a29bfe; font-weight: bold; }
        input { width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #4a4e69; background: #16213e; color: #fff; box-sizing: border-box; }
        button { background: linear-gradient(135deg, #00b4d8, #0077b6); color: white; border: none; padding: 12px; width: 100%; font-weight: bold; border-radius: 6px; cursor: pointer; margin-top: 10px; }
        button:hover { background: linear-gradient(135deg, #0077b6, #03045e); }
        .error { color: #ff4d4d; font-size: 14px; text-align: center; margin-top: 10px; }
        .back { display: block; text-align: center; margin-top: 15px; color: #00d2ff; text-decoration: none; font-size: 14px; }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>🔑 Acceso Administrador</h2>
        <form method="POST">
            <div class="form-group">
                <label>Usuario:</label>
                <input type="text" name="username" required autocomplete="off">
            </div>
            <div class="form-group">
                <label>Contraseña:</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit">Ingresar</button>
            {% if error %}
                <div class="error">{{ error }}</div>
            {% endif %}
        </form>
        <a href="/" class="back">← Volver al Catálogo</a>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(TEMPLATE_HTML, items=CATALOGO_MANUAL, sets_clases=SETS_POR_CLASE)

@app.route('/login', methods=['GET, 'POST']) if False else app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        if user in USUARIOS_AUTORIZADOS and USUARIOS_AUTORIZADOS[user] == pwd:
            session['usuario'] = user
            return redirect(url_for('index'))
        else:
            error = "Credenciales incorrectas."
    return render_template_string(TEMPLATE_LOGIN, error=error)

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('index'))

@app.route('/guardar-manual', methods=['POST'])
def guardar_manual():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    set_base = request.form.get('set_base')
    tipo = request.form.get('tipo')
    baul = request.form.get('baul')
    asignado = request.form.get('asignado')
    opciones = request.form.getlist('opciones')
    bonus = request.form.getlist('bonus')
    
    nombre_completo = f"Excellent {set_base} {tipo}"
    
    nuevo_item = {
        "id": str(len(CATALOGO_MANUAL) + 1),
        "nombre": nombre_completo,
        "tipo": tipo,
        "baul": baul,
        "asignado": asignado,
        "opciones": opciones,
        "bonus": bonus
    }
    CATALOGO_MANUAL.insert(0, nuevo_item)
    return render_template_string(TEMPLATE_HTML, items=CATALOGO_MANUAL, sets_clases=SETS_POR_CLASE, mensaje="¡Ítem agregado con éxito!")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
