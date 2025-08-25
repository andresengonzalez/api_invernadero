import os
import re
import csv
import base64
import psycopg2
from io import StringIO
from datetime import datetime, timedelta, date
from flask import Flask, request, jsonify, Response

# Opcional: carga .env en local (pip install python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = Flask(__name__)

# --- Config ---
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL no está definida en las variables de entorno.")

# Columna de timestamp para filtrar por fechas (por defecto created_at)
TIMESTAMP_COL = os.getenv("TIMESTAMP_COL", "created_at")
# Sanear el nombre de columna (evitar inyección vía env var)
if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", TIMESTAMP_COL):
    raise ValueError("TIMESTAMP_COL contiene caracteres inválidos.")

# --- Helpers DB ---
def get_conn():
    return psycopg2.connect(DB_URL)

# --- UI muy simple ---
@app.get("/")
def index():
    # Valores por defecto: últimos 7 días
    today = date.today()
    default_end = today
    default_start = today - timedelta(days=7)

    html = f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Exportar registros CSV</title>
      <style>
        body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 24px; }}
        .card {{ max-width: 520px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 12px; }}
        label {{ display:block; margin: 12px 0 6px; font-weight:600; }}
        input[type="date"] {{ padding: 8px; width: 100%; box-sizing: border-box; }}
        button {{ margin-top: 16px; padding: 10px 14px; border: 0; border-radius: 8px; cursor: pointer; }}
        .primary {{ background: #0d6efd; color: white; }}
        .hint {{ color:#666; font-size: 0.9rem; margin-top:8px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <h2>Descargar CSV de registros</h2>
        <form action="/export" method="get">
          <label for="start">Desde</label>
          <input id="start" name="start" type="date" value="{default_start.isoformat()}" required>

          <label for="end">Hasta</label>
          <input id="end" name="end" type="date" value="{default_end.isoformat()}" required>

          <button class="primary" type="submit">Descargar CSV</button>
          <div class="hint">Filtra usando la columna: <code>{TIMESTAMP_COL}</code></div>
        </form>
      </div>
    </body>
    </html>
    """
    return html, 200

# --- Endpoint que genera y devuelve el CSV ---
@app.get("/export")
def export_csv():
    try:
        start_str = request.args.get("start")
        end_str = request.args.get("end")

        # Validación básica
        if not start_str or not end_str:
            return jsonify({"error": "Faltan parámetros 'start' y/o 'end' (YYYY-MM-DD)."}), 400

        # Parseo de fechas (YYYY-MM-DD)
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()

        if end_date < start_date:
            return jsonify({"error": "La fecha 'Hasta' no puede ser menor que 'Desde'."}), 400

        # Rango: [start, end + 1 día) para incluir todo el día 'end'
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

        # Query
        sql = f"""
            SELECT {TIMESTAMP_COL}, bateria, temperatura, humedad,
                   viento_direccion, presion, viento_velocidad, lluvia
            FROM registros
            WHERE {TIMESTAMP_COL} >= %s AND {TIMESTAMP_COL} < %s
            ORDER BY {TIMESTAMP_COL} ASC
        """

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (start_dt, end_dt_exclusive))
                rows = cur.fetchall()

        # Generar CSV en memoria
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([TIMESTAMP_COL, "bateria", "temperatura", "humedad",
                         "viento_direccion", "presion", "viento_velocidad", "lluvia"])
        writer.writerows(rows)

        filename = f"registros_{start_date.isoformat()}_{end_date.isoformat()}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        print("❌ Error export_csv:", e)
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

# --- Tu endpoint existente para insertar datos ---
@app.post("/datos")
def recibir_datos():
    try:
        data = request.json or {}
        payload_base64 = data.get("data", "")

        if not payload_base64:
            return jsonify({"error": "No se recibió payload"}), 400

        decoded = base64.b64decode(payload_base64)

        # Nota: accedes hasta decoded[27], así que asegúrate de longitud >= 28
        if len(decoded) < 28:
            return jsonify({"error": "Payload inválido, tamaño incorrecto"}), 400

        battery = decoded[2]
        temp_raw = int.from_bytes(decoded[5:7], byteorder='little')
        temp = temp_raw / 10
        humidity = decoded[9] / 2
        wind_dir_raw = int.from_bytes(decoded[12:14], byteorder='little')
        wind_dir = wind_dir_raw / 10
        pressure_raw = int.from_bytes(decoded[16:18], byteorder='little')
        pressure = pressure_raw / 10
        wind_speed_raw = int.from_bytes(decoded[20:22], byteorder='little')
        wind_speed = wind_speed_raw / 10
        rainfall_raw = int.from_bytes(decoded[24:28], byteorder='little')
        rainfall = rainfall_raw / 100

        # Validaciones
        if not (0 <= temp <= 60): temp = None
        if not (0 <= humidity <= 100): humidity = None
        if not (0 <= wind_dir <= 360): wind_dir = None
        if not (0 <= pressure <= 2100): pressure = None
        if not (0 <= wind_speed <= 100): wind_speed = None
        if not (0 <= rainfall <= 1000): rainfall = None

        print("📌 Datos decodificados:",
              f"batería={battery}, temp={temp}, hum={humidity}, dir={wind_dir},",
              f"pres={pressure}, viento={wind_speed}, lluvia={rainfall}")

        sql_insert = """
            INSERT INTO registros (bateria, temperatura, humedad, viento_direccion, presion, viento_velocidad, lluvia)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        valores = (battery, temp, humidity, wind_dir, pressure, wind_speed, rainfall)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_insert, valores)
                conn.commit()

        return jsonify({"mensaje": "Datos guardados exitosamente"}), 200

    except Exception as e:
        print("❌ Error /datos:", e)
        return jsonify({"error": f"Error interno: {str(e)}"}), 500

# --- Desarrollo local ---
if __name__ == "__main__":
    # En Render usas gunicorn App:app; este bloque es para dev local
    app.run(host="0.0.0.0", port=5000)
