# API REST - Reserva de Hoteles

API RESTful para gestion de reservas de hoteles con persistencia en SQLite.

## Requisitos

- Python 3.8+
- pip

## Instalacion

```bash
pip install -r requirements.txt
```

## Ejecucion

```bash
python app.py
```

El servidor se iniciara en `http://localhost:5000`.

## Endpoints

### Hoteles

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | /hotels | Lista todos los hoteles |
| GET | /hotels/{id} | Obtiene un hotel por ID |
| POST | /hotels | Crea un nuevo hotel |
| PUT | /hotels/{id} | Actualiza un hotel existente |
| DELETE | /hotels/{id} | Elimina un hotel y sus reservas |
| GET | /hotels/{id}/disponibilidad | Consulta disponibilidad por fechas |

### Reservas

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| GET | /reservas | Lista todas las reservas |
| GET | /reservas/{id} | Obtiene una reserva por ID |
| POST | /reservas | Crea una nueva reserva |
| PUT | /reservas/{id} | Actualiza una reserva existente |
| DELETE | /reservas/{id} | Cancela una reserva |

## Ejemplos de uso

### Crear un hotel

```bash
curl -X POST http://localhost:5000/hotels \
  -H "Content-Type: application/json" \
  -d '{"nombre": "Hotel Lima", "direccion": "Av. Principal 456", "ciudad": "Lima", "estrellas": 4, "habitaciones_totales": 30}'
```

### Crear una reserva

```bash
curl -X POST http://localhost:5000/reservas \
  -H "Content-Type: application/json" \
  -d '{"hotel_id": 1, "huesped_nombre": "Carlos Lopez", "huesped_email": "carlos@mail.com", "check_in": "2027-01-10", "check_out": "2027-01-15", "habitaciones": 2}'
```

### Consultar disponibilidad

```bash
curl "http://localhost:5000/hotels/1/disponibilidad?check_in=2027-01-10&check_out=2027-01-15"
```

## Tests

```bash
python -m pytest test_app.py -v
```
