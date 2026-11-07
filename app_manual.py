from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
# Clave secreta para manejar las sesiones de los administradores
app.secret_key = 'multiverso_github_secret_key'

# ================= 1. LOS 3 USUARIOS AUTORIZADOS =================
USUARIOS_AUTORIZADOS = {
    "admin1": "Mistermagu2022*",
    "admin2": "MuOnline2026",
    "soporte": "MultiversoSecure"
}

# ================= 2. CATÁLOGO MANUAL EN MEMORIA =================
CATALOGO_MANUAL = [
    {"id": "1", "nombre": "Excellent Dragon Armor", "tipo": "Armor", "opciones": ["Damage Decrease +4%", "Reflect Damage +4%"], "bonus": ["Strength +50", "Vitality +30"]},
    {"id": "2", "nombre": "Excellent Dragon Pants", "tipo": "Pants", "opciones": ["Max Life +3%"], "bonus": ["Strength +40", "Agility +20"]},
    {"id": "3", "nombre": "Excellent Legendary Helm", "tipo": "Helm", "opciones": ["Luck (+25%)", "Critical Damage Resistance +10%"], "bonus": ["Energy +60", "Vitality +40"]},
    {"id": "4", "nombre": "Excellent Vine Boots", "tipo": "Boots", "opciones": ["Zen Drop Rate +30%"], "bonus": ["Agility +30", "Energy +15"]},
]

TEMPLATE_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>MULTIVERSO - Gestión Manual (GitHub)</title>
    <style>
        body { background-color: #0b0c10; color: #c5c6c7; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; }
        h1, h2 { color: #66fcf1; text-align: center; }
        .container { max-width: 1000px; margin: 0 auto; background: #1f2833; padding: 30px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.7); }
        
        .user-bar { display: flex; justify-content: space-between; align-items: center; background: #0b0c10; padding: 10px 15px; border-radius: 6px; margin-bottom: 20px; border: 1px solid #45a29e; }
        .user-bar span { color: #66fcf1; font-weight: bold; }
        .btn-logout { background: #e63946; color: #fff; padding: 6px 12px; text-decoration: none; border-radius: 4px; font-size: 14px; }
        .btn-login { background: #45a29e; color: #0b0c10; padding: 6px 15px; text-decoration: none; border-radius: 4px; font-weight: bold; }

        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .form-group { margin-bottom: 15px; }
        .form-group.full { grid-column: span 2; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #45a29e; }
        input[type="text"], input[type="password"], select { width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #45a29e; background: #0b0c10; color: #fff; box-sizing: border-box; }
        .checkbox-container { display: flex; gap: 15px; flex-wrap: wrap; background: #0b0c10; padding: 10px; border-radius: 6px; border: 1px solid #45a29e; }
        .checkbox-container label { color: #fff; font-weight: normal; display: flex; align-items: center; gap: 6px; cursor: pointer; }
        button { background: #66fcf1; color: #0b0c10; border: none; padding: 12px 20px; font-size: 16px; border-radius: 6px; cursor: pointer; width: 100%; font-weight: bold; transition: 0.3s; margin-top: 10px; }
        button:hover { background: #45a29e; color: #fff; }
        
        .alert-error { background: #ff4d4d; color: #fff; padding: 10px; border-radius: 6px; margin-bottom: 15px; text-align: center; font-weight: bold; }
        .alert-success { background: #2ec4b6; color: #000; padding: 10px; border-radius: 6px; margin-bottom: 15px; text-align: center; font-weight: bold; }

        .filters-bar { display: flex; gap: 15px; margin-top: 30px; margin-bottom: 20px; flex-wrap: wrap; }
        .filters-bar input, .filters-bar select { flex: 1; min-width: 200px; }
        
        .items-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; }
        .item-card { background: #0b0c10; border: 1px solid #45a29e; border-radius: 8px; padding: 15px; position: relative; }
        .item-card h3 { margin: 0 0 10px 0; color: #66fcf1; font-size: 18px; }
        .tag { background: #1f2833; color: #66fcf1; padding: 3px 8px; border-radius: 4px; font-size: 12px; display: inline-block; margin-right: 5px; margin-bottom: 5px; }
        .badge-opt { background: #45a29e; color: #0b0c10; }
        .badge-bonus { background: #c5c6c7; color: #0b0c10; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ MULTIVERSO - Gestión y Catálogo Manual</h1>

        <div class="user-bar">
            {% if session.get('usuario') %}
                <span>👤 Administrador Activo: <strong>{{ session['usuario'] }}</strong></span>
                <a href="/logout" class="btn-logout">Cerrar Sesión</a>
            {% else %}
                <span>🔒 Modo Lectura (Edición restringida a los 3 administradores)</span>
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
        <div style="background: #16213e; padding: 20px; border-radius: 8px; border: 1px dashed #66fcf1; margin-bottom: 30px;">
            <h2>➕ Agregar Nuevo Ítem al Listado</h2>
            <form method="POST" action="/guardar-manual">
                <div class="form-grid">
                    
                    <div class="form-group">
                        <label for="nombre">Nombre del Ítem (Escribe o Autocompleta):</label>
                        <input type="text" id="nombre" name="nombre" list="lista-nombres" required placeholder="Ej: Excellent Vine Armor">
                        <datalist id="lista-nombres">
                            <option value="Excellent Vine Armor">
                            <option value="Excellent Vine Boots">
                            <option value="Excellent Dragon Armor">
                            <option value="Excellent Dragon Pants">
                            <option value="Excellent Legendary Helm">
                            <option value="Excellent Sphinx Armor">
                        </datalist>
                    </div>

                    <div class="form-group">
                        <label for="tipo">Tipo de Pieza:</label>
                        <select id="tipo" name="tipo" required>
                            <option value="Armor">Armor (Pechera)</option>
                            <option value="Pants">Pants (Pantalón)</option>
                            <option value="Helm">Helm (Casco)</option>
                            <option value="Gloves">Gloves (Guantes)</option>
                            <option value="Boots">Boots (Botas)</option>
                            <option value="Shield">Shield (Escudo)</option>
                        </select>
                    </div>

                    <div class="form-group full">
                        <label>Opciones Excellent (Exc):</label>
                        <div class="checkbox-container">
                            <label><input type="checkbox" name="opciones" value="Luck (+25%)"> Luck (+25%)</label>
                            <label><input type="checkbox" name="opciones" value="Damage Decrease +4%"> Damage Decrease +4%</label>
                            <label><input type="checkbox" name="opciones" value="Reflect Damage +4%"> Reflect Damage +4%</label>
                            <label><input type="checkbox" name="opciones" value="Max Life +3%"> Max Life +3%</label>
                            <label><input type="checkbox" name="opciones" value="Zen Drop Rate +30%"> Zen Drop Rate +30%</label>
                        </div>
                    </div>

                    <div class="form-group full">
                        <label>Atributos y Bonus Exc (Fuerza, Agility, Vitality, Energy, Command):</label>
                        <div class="checkbox-container">
                            <label><input type="checkbox" name="bonus" value="Strength +50"> Strength +50</label>
                            <label><input type="checkbox" name="bonus" value="Agility +50"> Agility +50</label>
                            <label><input type="checkbox" name="bonus" value="Vitality +150"> Vitality +150</label>
                            <label><input type="checkbox" name="bonus" value="Energy +50"> Energy +50</label>
                            <label><input type="checkbox" name="bonus" value="Command +25"> Command +25</label>
                        </div>
                    </div>

                </div>
                <button type="submit">💾 Agregar al Listado</button>
            </form>
        </div>
        {% endif %}

        <h2>🔍 Buscador y Filtros del Inventario</h2>
        <div class="filters-bar">
            <input type="text" id="inputBuscador" placeholder="Buscar por nombre (ej. Vine, Dragon, Helm)..." onkeyup="filtrarItems()">
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
            <div class="item-card" data-nombre="{{ item.nombre | lower }}" data-tipo="{{ item.tipo }}">
                <h3>{{ item.nombre }}</h3>
                <p><strong>Tipo:</strong> <span class="tag">{{ item.tipo }}</span></p>
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
                let coincideTexto = nombre.includes(texto);
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
        body { background-color: #0b0c10; color: #c5c6c7; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-box { background: #1f2833; padding: 40px; border-radius: 12px; width: 320px; box-shadow: 0 8px 24px rgba(0,0,0,0.8); border: 1px solid #45a29e; }
        h2 { color: #66fcf1; text-align: center; margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; color: #45a29e; font-weight: bold; }
        input { width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #45a29e; background: #0b0c10; color: #fff; box-sizing: border-box; }
        button { background: #66fcf1; color: #0b0c10; border: none; padding: 12px; width: 100%; font-weight: bold; border-radius: 6px; cursor: pointer; margin-top: 10px; }
        button:hover { background: #45a29e; color: #fff; }
        .error { color: #ff4d4d; font-size: 14px; text-align: center; margin-top: 10px; }
        .back { display: block; text-align: center; margin-top: 15px; color: #66fcf1; text-decoration: none; font-size: 14px; }
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
    return render_template_string(TEMPLATE_HTML, items=CATALOGO_MANUAL)

@app.route('/login', methods=['GET', 'POST'])
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
        
    nombre = request.form.get('nombre')
    tipo = request.form.get('tipo')
    opciones = request.form.getlist('opciones')
    bonus = request.form.getlist('bonus')
    
    nuevo_item = {
        "id": str(len(CATALOGO_MANUAL) + 1),
        "nombre": nombre,
        "tipo": tipo,
        "opciones": opciones,
        "bonus": bonus
    }
    CATALOGO_MANUAL.insert(0, nuevo_item)
    return render_template_string(TEMPLATE_HTML, items=CATALOGO_MANUAL, mensaje="¡Ítem agregado con éxito!")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
