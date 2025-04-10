import os
import psycopg2
from flask import Flask, request, jsonify
import base64

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "API Flask en Render funcionando", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

# Intentar conectar a PostgreSQL y manejar errores
try:
    DB_URL = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    print("Conexión exitosa a la base de datos")
except Exception as e:
    print("❌ Error conectando a la base de datos:", e)
    conn = None

@app.route('/datos', methods=['POST'])
def recibir_datos():
    if not conn:
        return jsonify({"error": "No hay conexión a la base de datos"}), 500

    try:
        data = request.json
        payload_base64 = data.get("payload", "")

        if not payload_base64:
            return jsonify({"error": "No se recibió payload"}), 400

        # Decodificar los datos
        decoded_bytes = base64.b64decode(payload_base64)
        battery = decoded_bytes[2]
        temp = (decoded_bytes[4] << 8 | decoded_bytes[5]) / 10
        humidity = decoded_bytes[7] / 2
        wind_dir = (decoded_bytes[9] << 8 | decoded_bytes[10]) / 10
        pressure = (decoded_bytes[12] << 8 | decoded_bytes[13]) / 10
        wind_speed = (decoded_bytes[15] << 8 | decoded_bytes[16]) / 10
        rainfall = (decoded_bytes[18] << 24 | decoded_bytes[19] << 16 | decoded_bytes[20] << 8 | decoded_bytes[21]) / 100

        sql_query = """
            INSERT INTO registros (bateria, temperatura, humedad, viento_direccion, presion, viento_velocidad, lluvia)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        valores = (battery, temp, humidity, wind_dir, pressure, wind_speed, rainfall)
        cursor.execute(sql_query, valores)
        conn.commit()  # Confirmar la transacción

        return jsonify({"mensaje": "Datos guardados exitosamente"}), 200

    except psycopg2.Error as e:
        conn.rollback()  # Revertir la transacción en caso de error
        print("❌ Error en la base de datos:", e)
        return jsonify({"error": "Error al insertar en la base de datos"}), 500

    except Exception as e:
        print("❌ Error general:", e)
        return jsonify({"error": "Error interno en el servidor"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)