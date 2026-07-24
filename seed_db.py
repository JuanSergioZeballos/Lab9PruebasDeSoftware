import sqlite3
import os

DATABASE = 'hotel.db'

def seed():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Crear tablas si no existen
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

    # Verificar si ya existe el hotel con ID 1
    cursor.execute('SELECT * FROM hotels WHERE id = 1')
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO hotels (id, nombre, direccion, ciudad, estrellas, habitaciones_totales, telefono)
            VALUES (1, 'Hotel El Sol', 'Av. Ejercito 123', 'Arequipa', 5, 20, '954123456')
        ''')
        print("Hotel con ID 1 insertado correctamente.")
    else:
        print("El Hotel con ID 1 ya existe.")

    # Verificar si existe al menos una reserva
    cursor.execute('SELECT * FROM reservas WHERE id = 1')
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO reservas (id, hotel_id, huesped_nombre, huesped_email, check_in, check_out, habitaciones)
            VALUES (1, 1, 'Juan Perez', 'juan@example.com', '2027-01-01', '2027-01-05', 2)
        ''')
        print("Reserva con ID 1 insertada correctamente.")
    else:
        print("La Reserva con ID 1 ya existe.")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    seed()
