import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "app_data.db")

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# Crear tabla de usuarios
cur.execute('''
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Crear tabla de escenarios
cur.execute('''
CREATE TABLE IF NOT EXISTS scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    sport TEXT,
    label TEXT,
    payload_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

# Crear tabla de privilegios
cur.execute('''
CREATE TABLE IF NOT EXISTS entitlements (
    username TEXT PRIMARY KEY,
    is_premium INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

con.commit()
con.close()

print("Base de datos inicializada correctamente.")
