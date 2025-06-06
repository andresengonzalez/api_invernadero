import os
import psycopg2
from flask import Flask, request, jsonify
import base64

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return "API Flask en Render funcionando", 200

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
        decoded = base64.b64decode(payload_base64)

        # Asegurar que los datos decodificados tengan la longitud esperada
        if len(decoded) < 22:
            return jsonify({"error": "Payload inválido, tamaño incorrecto"}), 400

        # Extraer valores con corrección de índices
        battery = decoded[2]
        temp_raw = int.from_bytes(decoded[5:7], byteorder='little')
        temp = temp_raw / 10
        humidity = decoded[9] / 2
        wind_dir_raw = int.from_bytes(decoded[12:14],byteorder='little')
        wind_dir = wind_dir_raw /10
        pressure_raw = int.from_bytes(decoded[16:18], byteorder='little')
        pressure = pressure_raw / 10
        wind_speed_raw = int.from_bytes(decoded[20:22], byteorder='little')
        wind_speed = wind_speed_raw / 10
        rainfall_raw = int.from_bytes(decoded[24:28], byteorder='little')
        rainfall = rainfall_raw / 100

        # Validar valores dentro de rangos normales
        if not (0 <= temp <= 60):
            temp = None
        if not (0 <= humidity <= 100):
            humidity = None
        if not (0 <= wind_dir <= 360):
            wind_dir = None
        if not (0 <= pressure <= 2100):
            pressure = None
        if not (0 <= wind_speed <= 100):
            wind_speed = None
        if not (0 <= rainfall <= 1000):
            rainfall = None

        # 🔍 Imprimir valores corregidos antes de insertarlos
        print(f"📌 Datos decodificados:")
        print(f"   - Batería: {battery}%")
        print(f"   - Temperatura: {temp}°C")
        print(f"   - Humedad: {humidity}%")
        print(f"   - Dirección del viento: {wind_dir}°")
        print(f"   - Presión: {pressure} hPa")
        print(f"   - Velocidad del viento: {wind_speed} m/s")
        print(f"   - Lluvia acumulada: {rainfall} mm")

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
        return jsonify({"error": f"Error en la base de datos: {str(e)}"}), 500

    except Exception as e:
        print("❌ Error general:", e)
        return jsonify({"error": f"Error interno en el servidor: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)