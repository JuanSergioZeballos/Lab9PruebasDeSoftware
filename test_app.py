import pytest
import json
import os
import tempfile
import sqlite3
import app as app_module
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    original_get_db = app_module.get_db

    def get_test_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    app_module.get_db = get_test_db

    with app.test_client() as client:
        with app.app_context():
            conn = get_test_db()
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
        yield client

    os.close(db_fd)
    os.unlink(db_path)
    app_module.get_db = original_get_db


def create_hotel(client, nombre="Hotel Prueba", direccion="Av. Principal 123",
                 ciudad="Lima", estrellas=4, habitaciones_totales=20, telefono="999888777"):
    return client.post('/hotels', json={
        'nombre': nombre, 'direccion': direccion, 'ciudad': ciudad,
        'estrellas': estrellas, 'habitaciones_totales': habitaciones_totales,
        'telefono': telefono
    })


class TestHotels:
    def test_create_hotel(self, client):
        rv = create_hotel(client)
        assert rv.status_code == 201
        data = json.loads(rv.data)
        assert data['nombre'] == 'Hotel Prueba'
        assert data['estrellas'] == 4
        assert 'id' in data

    def test_create_hotel_missing_field(self, client):
        rv = client.post('/hotels', json={'nombre': 'Incompleto'})
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert 'error' in data

    def test_get_hotels(self, client):
        create_hotel(client)
        create_hotel(client, nombre="Hotel Segundo")
        rv = client.get('/hotels')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert len(data) == 2

    def test_get_hotel_by_id(self, client):
        create = create_hotel(client)
        hotel_id = json.loads(create.data)['id']
        rv = client.get(f'/hotels/{hotel_id}')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['id'] == hotel_id

    def test_get_hotel_not_found(self, client):
        rv = client.get('/hotels/9999')
        assert rv.status_code == 404

    def test_update_hotel(self, client):
        create = create_hotel(client)
        hotel_id = json.loads(create.data)['id']
        rv = client.put(f'/hotels/{hotel_id}', json={'nombre': 'Hotel Actualizado', 'estrellas': 5})
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['nombre'] == 'Hotel Actualizado'
        assert data['estrellas'] == 5

    def test_update_hotel_not_found(self, client):
        rv = client.put('/hotels/9999', json={'nombre': 'No existe'})
        assert rv.status_code == 404

    def test_delete_hotel(self, client):
        create = create_hotel(client)
        hotel_id = json.loads(create.data)['id']
        rv = client.delete(f'/hotels/{hotel_id}')
        assert rv.status_code == 200
        rv = client.get(f'/hotels/{hotel_id}')
        assert rv.status_code == 404

    def test_delete_hotel_not_found(self, client):
        rv = client.delete('/hotels/9999')
        assert rv.status_code == 404


class TestReservas:
    def test_create_reserva(self, client):
        create = create_hotel(client)
        hotel_id = json.loads(create.data)['id']
        rv = client.post('/reservas', json={
            'hotel_id': hotel_id, 'huesped_nombre': 'Juan Perez',
            'huesped_email': 'juan@mail.com', 'check_in': '2026-08-01',
            'check_out': '2026-08-05', 'habitaciones': 2
        })
        assert rv.status_code == 201
        data = json.loads(rv.data)
        assert data['huesped_nombre'] == 'Juan Perez'
        assert data['estado'] == 'confirmada'

    def test_create_reserva_missing_field(self, client):
        rv = client.post('/reservas', json={'hotel_id': 1})
        assert rv.status_code == 400

    def test_create_reserva_hotel_not_found(self, client):
        rv = client.post('/reservas', json={
            'hotel_id': 9999, 'huesped_nombre': 'Juan',
            'huesped_email': 'juan@mail.com', 'check_in': '2026-08-01',
            'check_out': '2026-08-05'
        })
        assert rv.status_code == 404

    def test_create_reserva_invalid_dates(self, client):
        create = create_hotel(client)
        hotel_id = json.loads(create.data)['id']
        rv = client.post('/reservas', json={
            'hotel_id': hotel_id, 'huesped_nombre': 'Juan',
            'huesped_email': 'juan@mail.com', 'check_in': '2026-08-10',
            'check_out': '2026-08-05'
        })
        assert rv.status_code == 400

    def test_create_reserva_invalid_date_format(self, client):
        create = create_hotel(client)
        hotel_id = json.loads(create.data)['id']
        rv = client.post('/reservas', json={
            'hotel_id': hotel_id, 'huesped_nombre': 'Juan',
            'huesped_email': 'juan@mail.com', 'check_in': '01-08-2026',
            'check_out': '05-08-2026'
        })
        assert rv.status_code == 400

    def test_create_reserva_no_availability(self, client):
        create = create_hotel(client, habitaciones_totales=1)
        hotel_id = json.loads(create.data)['id']
        client.post('/reservas', json={
            'hotel_id': hotel_id, 'huesped_nombre': 'Juan',
            'huesped_email': 'juan@mail.com', 'check_in': '2026-08-01',
            'check_out': '2026-08-05', 'habitaciones': 1
        })
        rv = client.post('/reservas', json={
            'hotel_id': hotel_id, 'huesped_nombre': 'Pedro',
            'huesped_email': 'pedro@mail.com', 'check_in': '2026-08-02',
            'check_out': '2026-08-04', 'habitaciones': 1
        })
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert 'disponibles' in data['error']

    def test_get_reservas(self, client):
        create = create_hotel(client)
        hotel_id = json.loads(create.data)['id']
        client.post('/reservas', json={
            'hotel_id': hotel_id, 'huesped_nombre': 'Juan',
            'huesped_email': 'juan@mail.com', 'check_in': '2026-08-01',
            'check_out': '2026-08-05'
        })
        rv = client.get('/reservas')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert len(data) == 1
        assert data[0]['hotel_nombre'] == 'Hotel Prueba'

    def test_get_reserva_by_id(self, client):
        create = create_hotel(client)
        hotel_id = json.loads(create.data)['id']
        create_res = client.post('/reservas', json={
            'hotel_id': hotel_id, 'huesped_nombre': 'Juan',
            'huesped_email': 'juan@mail.com', 'check_in': '2026-08-01',
            'check_out': '2026-08-05'
        })
        reserva_id = json.loads(create_res.data)['id']
        rv = client.get(f'/reservas/{reserva_id}')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['id'] == reserva_id

    def test_get_reserva_not_found(self, client):
        rv = client.get('/reservas/9999')
        assert rv.status_code == 404

    def test_update_reserva(self, client):
        create = create_hotel(client)
        hotel_id = json.loads(create.data)['id']
        create_res = client.post('/reservas', json={
            'hotel_id': hotel_id, 'huesped_nombre': 'Juan',
            'huesped_email': 'juan@mail.com', 'check_in': '2026-08-01',
            'check_out': '2026-08-05'
        })
        reserva_id = json.loads(create_res.data)['id']
        rv = client.put(f'/reservas/{reserva_id}', json={'estado': 'cancelada'})
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['estado'] == 'cancelada'

    def test_update_reserva_not_found(self, client):
        rv = client.put('/reservas/9999', json={'estado': 'cancelada'})
        assert rv.status_code == 404

    def test_delete_reserva(self, client):
        create = create_hotel(client)
        hotel_id = json.loads(create.data)['id']
        create_res = client.post('/reservas', json={
            'hotel_id': hotel_id, 'huesped_nombre': 'Juan',
            'huesped_email': 'juan@mail.com', 'check_in': '2026-08-01',
            'check_out': '2026-08-05'
        })
        reserva_id = json.loads(create_res.data)['id']
        rv = client.delete(f'/reservas/{reserva_id}')
        assert rv.status_code == 200
        rv = client.get(f'/reservas/{reserva_id}')
        assert rv.status_code == 404

    def test_delete_reserva_not_found(self, client):
        rv = client.delete('/reservas/9999')
        assert rv.status_code == 404


class TestDisponibilidad:
    def test_check_disponibilidad(self, client):
        create = create_hotel(client, habitaciones_totales=10)
        hotel_id = json.loads(create.data)['id']
        client.post('/reservas', json={
            'hotel_id': hotel_id, 'huesped_nombre': 'Juan',
            'huesped_email': 'juan@mail.com', 'check_in': '2026-08-01',
            'check_out': '2026-08-05', 'habitaciones': 3
        })
        rv = client.get(f'/hotels/{hotel_id}/disponibilidad?check_in=2026-08-02&check_out=2026-08-04')
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data['habitaciones_disponibles'] == 7
        assert data['suficiente'] == True

    def test_check_disponibilidad_no_params(self, client):
        create = create_hotel(client)
        hotel_id = json.loads(create.data)['id']
        rv = client.get(f'/hotels/{hotel_id}/disponibilidad')
        assert rv.status_code == 400

    def test_check_disponibilidad_hotel_not_found(self, client):
        rv = client.get('/hotels/9999/disponibilidad?check_in=2026-08-01&check_out=2026-08-05')
        assert rv.status_code == 404


class TestErrorHandling:
    def test_404(self, client):
        rv = client.get('/ruta-inexistente')
        assert rv.status_code == 404
        data = json.loads(rv.data)
        assert 'error' in data

    def test_create_hotel_empty_body(self, client):
        rv = client.post('/hotels', json={})
        assert rv.status_code == 400

    def test_create_reserva_empty_body(self, client):
        rv = client.post('/reservas', json={})
        assert rv.status_code == 400