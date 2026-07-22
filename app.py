from flask import Flask, request, jsonify
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
DATABASE = 'hotel.db'


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hotels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            direccion TEXT NOT NULL,
            ciudad TEXT NOT NULL,
            estrellas INTEGER CHECK(estrellas BETWEEN 1 AND 5),
            habitaciones_totales INTEGER NOT NULL,
            telefono TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hotel_id INTEGER NOT NULL,
            huesped_nombre TEXT NOT NULL,
            huesped_email TEXT NOT NULL,
            check_in DATE NOT NULL,
            check_out DATE NOT NULL,
            habitaciones INTEGER NOT NULL DEFAULT 1,
            estado TEXT DEFAULT 'confirmada',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hotel_id) REFERENCES hotels(id)
        )
    ''')
    conn.commit()
    conn.close()


@app.route('/hotels', methods=['GET'])
def get_hotels():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM hotels ORDER BY created_at DESC')
    hotels = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(hotels), 200


@app.route('/hotels/<int:hotel_id>', methods=['GET'])
def get_hotel(hotel_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM hotels WHERE id = ?', (hotel_id,))
    hotel = cursor.fetchone()
    conn.close()
    if hotel is None:
        return jsonify({'error': 'Hotel no encontrado'}), 404
    return jsonify(dict(hotel)), 200


@app.route('/hotels', methods=['POST'])
def create_hotel():
    data = request.get_json()
    required = ['nombre', 'direccion', 'ciudad', 'estrellas', 'habitaciones_totales']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Campo requerido: {field}'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO hotels (nombre, direccion, ciudad, estrellas, habitaciones_totales, telefono)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (data['nombre'], data['direccion'], data['ciudad'],
          data['estrellas'], data['habitaciones_totales'], data.get('telefono', '')))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.execute('SELECT * FROM hotels WHERE id = ?', (new_id,))
    hotel = dict(cursor.fetchone())
    conn.close()
    return jsonify(hotel), 201


@app.route('/hotels/<int:hotel_id>', methods=['PUT'])
def update_hotel(hotel_id):
    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM hotels WHERE id = ?', (hotel_id,))
    if cursor.fetchone() is None:
        conn.close()
        return jsonify({'error': 'Hotel no encontrado'}), 404

    fields = ['nombre', 'direccion', 'ciudad', 'estrellas', 'habitaciones_totales', 'telefono']
    updates = []
    values = []
    for f in fields:
        if f in data:
            updates.append(f'{f} = ?')
            values.append(data[f])
    if not updates:
        conn.close()
        return jsonify({'error': 'No hay campos para actualizar'}), 400

    values.append(hotel_id)
    cursor.execute(f'UPDATE hotels SET {", ".join(updates)} WHERE id = ?', values)
    conn.commit()
    cursor.execute('SELECT * FROM hotels WHERE id = ?', (hotel_id,))
    hotel = dict(cursor.fetchone())
    conn.close()
    return jsonify(hotel), 200


@app.route('/hotels/<int:hotel_id>', methods=['DELETE'])
def delete_hotel(hotel_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM hotels WHERE id = ?', (hotel_id,))
    if cursor.fetchone() is None:
        conn.close()
        return jsonify({'error': 'Hotel no encontrado'}), 404

    cursor.execute('DELETE FROM reservas WHERE hotel_id = ?', (hotel_id,))
    cursor.execute('DELETE FROM hotels WHERE id = ?', (hotel_id,))
    conn.commit()
    conn.close()
    return jsonify({'mensaje': 'Hotel eliminado correctamente'}), 200


@app.route('/reservas', methods=['GET'])
def get_reservas():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, h.nombre as hotel_nombre, h.ciudad as hotel_ciudad
        FROM reservas r
        JOIN hotels h ON r.hotel_id = h.id
        ORDER BY r.created_at DESC
    ''')
    reservas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(reservas), 200


@app.route('/reservas/<int:reserva_id>', methods=['GET'])
def get_reserva(reserva_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, h.nombre as hotel_nombre, h.ciudad as hotel_ciudad
        FROM reservas r
        JOIN hotels h ON r.hotel_id = h.id
        WHERE r.id = ?
    ''', (reserva_id,))
    reserva = cursor.fetchone()
    conn.close()
    if reserva is None:
        return jsonify({'error': 'Reserva no encontrada'}), 404
    return jsonify(dict(reserva)), 200


@app.route('/reservas', methods=['POST'])
def create_reserva():
    data = request.get_json()
    required = ['hotel_id', 'huesped_nombre', 'huesped_email', 'check_in', 'check_out']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Campo requerido: {field}'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM hotels WHERE id = ?', (data['hotel_id'],))
    hotel = cursor.fetchone()
    if hotel is None:
        conn.close()
        return jsonify({'error': 'Hotel no encontrado'}), 404

    try:
        check_in = datetime.strptime(data['check_in'], '%Y-%m-%d')
        check_out = datetime.strptime(data['check_out'], '%Y-%m-%d')
    except ValueError:
        conn.close()
        return jsonify({'error': 'Formato de fecha invalido. Use YYYY-MM-DD'}), 400

    if check_out <= check_in:
        conn.close()
        return jsonify({'error': 'check_out debe ser posterior a check_in'}), 400

    habitaciones = data.get('habitaciones', 1)
    cursor.execute('''
        SELECT COALESCE(SUM(habitaciones), 0)
        FROM reservas
        WHERE hotel_id = ?
          AND estado = 'confirmada'
          AND check_in < ? AND check_out > ?
    ''', (data['hotel_id'], data['check_out'], data['check_in']))
    ocupadas = cursor.fetchone()[0]
    disponibles = hotel['habitaciones_totales'] - ocupadas
    if habitaciones > disponibles:
        conn.close()
        return jsonify({'error': f'Solo hay {disponibles} habitaciones disponibles para esas fechas'}), 400

    cursor.execute('''
        INSERT INTO reservas (hotel_id, huesped_nombre, huesped_email, check_in, check_out, habitaciones)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (data['hotel_id'], data['huesped_nombre'], data['huesped_email'],
          data['check_in'], data['check_out'], habitaciones))
    conn.commit()
    new_id = cursor.lastrowid
    cursor.execute('SELECT * FROM reservas WHERE id = ?', (new_id,))
    reserva = dict(cursor.fetchone())
    conn.close()
    return jsonify(reserva), 201


@app.route('/reservas/<int:reserva_id>', methods=['PUT'])
def update_reserva(reserva_id):
    data = request.get_json()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM reservas WHERE id = ?', (reserva_id,))
    if cursor.fetchone() is None:
        conn.close()
        return jsonify({'error': 'Reserva no encontrada'}), 404

    fields = ['huesped_nombre', 'huesped_email', 'check_in', 'check_out', 'habitaciones', 'estado']
    updates = []
    values = []
    for f in fields:
        if f in data:
            updates.append(f'{f} = ?')
            values.append(data[f])
    if not updates:
        conn.close()
        return jsonify({'error': 'No hay campos para actualizar'}), 400

    values.append(reserva_id)
    cursor.execute(f'UPDATE reservas SET {", ".join(updates)} WHERE id = ?', values)
    conn.commit()
    cursor.execute('SELECT * FROM reservas WHERE id = ?', (reserva_id,))
    reserva = dict(cursor.fetchone())
    conn.close()
    return jsonify(reserva), 200


@app.route('/reservas/<int:reserva_id>', methods=['DELETE'])
def delete_reserva(reserva_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM reservas WHERE id = ?', (reserva_id,))
    if cursor.fetchone() is None:
        conn.close()
        return jsonify({'error': 'Reserva no encontrada'}), 404

    cursor.execute('DELETE FROM reservas WHERE id = ?', (reserva_id,))
    conn.commit()
    conn.close()
    return jsonify({'mensaje': 'Reserva cancelada correctamente'}), 200


@app.route('/hotels/<int:hotel_id>/disponibilidad', methods=['GET'])
def check_disponibilidad(hotel_id):
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')
    habitaciones_req = int(request.args.get('habitaciones', 1))

    if not check_in or not check_out:
        return jsonify({'error': 'Parametros check_in y check_out son requeridos'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM hotels WHERE id = ?', (hotel_id,))
    hotel = cursor.fetchone()
    if hotel is None:
        conn.close()
        return jsonify({'error': 'Hotel no encontrado'}), 404

    cursor.execute('''
        SELECT COALESCE(SUM(habitaciones), 0)
        FROM reservas
        WHERE hotel_id = ?
          AND estado = 'confirmada'
          AND check_in < ? AND check_out > ?
    ''', (hotel_id, check_out, check_in))
    ocupadas = cursor.fetchone()[0]
    disponibles = hotel['habitaciones_totales'] - ocupadas
    conn.close()

    return jsonify({
        'hotel_id': hotel_id,
        'habitaciones_totales': hotel['habitaciones_totales'],
        'habitaciones_ocupadas': ocupadas,
        'habitaciones_disponibles': disponibles,
        'suficiente': disponibles >= habitaciones_req
    }), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Ruta no encontrada'}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Error interno del servidor'}), 500


if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True, port=5000)