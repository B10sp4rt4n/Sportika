# Sportika
estadistica eventos deportivos

## Pruebas locales

1. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

2. Inicializa la base de datos (solo la primera vez):
   ```bash
   python init_db.py
   ```

3. Copia el archivo de ejemplo de variables de entorno:
   ```bash
   cp .env.example .env
   ```
   Edita `.env` si necesitas cambiar valores.

4. Ejecuta la aplicación:
   ```bash
   streamlit run app.py
   ```

La base de datos SQLite se crea automáticamente en el primer uso, pero debes inicializar las tablas con el script anterior.

### Variables de entorno
- `ENABLE_LOCAL_PREMIUM_SWITCH`: Habilita el botón para marcar usuarios como premium en local.
- `DEMO_PREMIUM`: Fuerza modo premium para pruebas.
- `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`: Solo necesarios si pruebas integración con Stripe.
