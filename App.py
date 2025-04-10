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

# Conectar a PostgreSQL usando la variable de entorno
DB_URL = os.getenv("DATABASE_URL")  # Recuperar la URL desde Render
conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

def decode_payload(base64_payload):
    decoded_bytes = base64.b64decode(base64_payload)
    battery = decoded_bytes[2]
    temp = (decoded_bytes[4] << 8 | decoded_bytes[5]) / 10
    humidity = decoded_bytes[7] / 2
    wind_dir = (decoded_bytes[9] << 8 | decoded_bytes[10]) / 10
    pressure = (decoded_bytes[12] << 8 | decoded_bytes[13]) / 10
    wind_speed = (decoded_bytes[15] << 8 | decoded_bytes[16]) / 10
    rainfall = (decoded_bytes[18] << 24 | decoded_bytes[19] << 16 | decoded_bytes[20] << 8 | decoded_bytes[21]) / 100

    return {
        "bateria": battery,
        "temperatura": temp,
        "humedad": humidity,
        "viento_direccion": wind_dir,
        "presion": pressure,
        "viento_velocidad": wind_speed,
        "lluvia": rainfall
    }

@app.route('/datos', methods=['POST'])
def recibir_datos():
    data = request.json
    payload_base64 = data.get("payload", "")

    if not payload_base64:
        return jsonify({"error": "No se recibió payload"}), 400

    datos_decodificados = decode_payload(payload_base64)

    sql_query = """
        INSERT INTO registros (bateria, temperatura, humedad, viento_direccion, presion, viento_velocidad, lluvia)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    
    valores = (
        datos_decodificados["bateria"],
        datos_decodificados["temperatura"],
        datos_decodificados["humedad"],
        datos_decodificados["viento_direccion"],
        datos_decodificados["presion"],
        datos_decodificados["viento_velocidad"],
        datos_decodificados["lluvia"]
    )

    cursor.execute(sql_query, valores)
    conn.commit()

    return jsonify({"mensaje": "Datos guardados exitosamente", "datos": datos_decodificados}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
