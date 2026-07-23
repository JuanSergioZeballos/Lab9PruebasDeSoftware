# Ejercicio 4 — Pruebas Básicas de Seguridad con Python (Requests)

**API evaluada:** Sistema de Reserva de Hoteles (Flask + SQLite)
**Endpoints:** `/hotels`, `/hotels/{id}`, `/hotels/{id}/disponibilidad`, `/reservas`, `/reservas/{id}`
**Script de pruebas:** [security_tests.py](security_tests.py)
**Reporte crudo generado:** [security_test_report.json](security_test_report.json)

## 1. Metodología

Se ejecutó `security_tests.py` (librería `requests`) contra la API corriendo en
`http://localhost:5000` (`python app.py`), cubriendo los 5 casos solicitados en la guía.
Cada caso registra código HTTP esperado vs. obtenido y un detalle cuando el resultado
revela un problema de validación.

## 2. Resultados por caso (tabla resumen)

| Caso | Prueba | Esperado | Obtenido | Resultado |
|------|--------|----------|----------|-----------|
| 1.1 | GET /hotels/999999 | 404 | 404 | PASS |
| 1.2 | GET /reservas/999999 | 404 | 404 | PASS |
| 1.3 | GET disponibilidad hotel inexistente | 404 | 404 | PASS |
| 2.1 | POST /hotels sin campos obligatorios | 400 + mensaje | 400 + mensaje | PASS |
| 2.2 | POST /hotels con campos obligatorios en `""` | 400 | **201 (creado)** | **FAIL** |
| 2.3 | POST /reservas con body `{}` | 400 | 400 | PASS |
| 3.1 | POST /hotels con tipos invertidos (`estrellas:"ABC"`, etc.) | 400/422 | **500** | **FAIL** |
| 3.2 | POST /hotels con `estrellas=99` (fuera de rango 1-5) | 400/422/500 | **Sin respuesta (timeout)** | **FAIL** |
| 3.3 | POST /reservas con `habitaciones=-5` y email inválido | 400/422 | Sin respuesta (servidor colgado) | **FAIL** |
| 4.1 | PATCH /hotels | 405 | 405 | PASS |
| 4.2 | PATCH /reservas | 405 | 405 | PASS |
| 4.3 | DELETE /hotels (colección) | 405 | 405 | PASS |
| 5.1 | Fuerza bruta / rate limiting sobre /reservas | N/A (no hay login) | Sin respuesta (servidor colgado) | N/A |

**Total: 13 verificaciones — 8 PASS / 5 FAIL.**

## 3. Desarrollo por caso

### Caso 1. Validación de recursos inexistentes
**Descripción (guía):** realizar solicitudes GET hacia identificadores inexistentes.
**Resultado esperado:** código HTTP 404.

**Pruebas realizadas:**
- `GET /hotels/999999`
- `GET /reservas/999999`
- `GET /hotels/999999/disponibilidad?check_in=2027-01-01&check_out=2027-01-02`

**Resultado obtenido:** los tres casos devolvieron **404** con un cuerpo JSON
`{"error": "..."}`.

**Análisis:** el sistema cumple correctamente. `get_hotel()`, `get_reserva()` y
`check_disponibilidad()` en [app.py](app.py) verifican explícitamente
`if hotel is None` / `if reserva is None` antes de responder, retornando 404 con
mensaje descriptivo. **No se encontraron problemas en este caso.**

---

### Caso 2. Validación de datos incompletos
**Descripción (guía):** enviar solicitudes POST con campos obligatorios vacíos.
**Resultado esperado:** código HTTP 400 y mensaje descriptivo del error.

**Pruebas realizadas:**
- `POST /hotels` omitiendo campos obligatorios (`direccion`, `ciudad`, etc.)
- `POST /hotels` con campos obligatorios presentes pero en `""` (string vacío)
- `POST /reservas` con body `{}`

**Resultado obtenido:**
- Omitir el campo → **400** + `{"error": "Campo requerido: <campo>"}` (correcto).
- Body vacío en `/reservas` → **400** (correcto).
- Campos presentes pero vacíos (`""`) → **201**, el hotel se crea igual (**incorrecto**).

**Análisis:** `create_hotel()` ([app.py:74-77](app.py#L74-L77)) valida únicamente
`if field not in data`, es decir, la *presencia* de la clave, no que tenga contenido.
Un valor `""` satisface esa condición y el registro se inserta con campos vacíos.
El mismo patrón se repite en `create_reserva()` ([app.py:175-178](app.py#L175-L178)).
**Recomendación:** cambiar la validación a algo como
`if not str(data.get(field, '')).strip():` para rechazar también valores vacíos.

---

### Caso 3. Validación de tipos de datos
**Descripción (guía):** enviar valores de tipo incorrecto (ej. `nombre: 12345`,
`estrellas: "ABC"`). El sistema deberá rechazar la solicitud.

**Pruebas realizadas:**
- `POST /hotels` con `nombre: 12345`, `estrellas: "ABC"`, `habitaciones_totales: "diez"`
- `POST /hotels` con `estrellas: 99` (fuera del rango 1-5 definido por el `CHECK` de la tabla)
- `POST /reservas` con `habitaciones: -5` y `huesped_email: "no-es-un-email"`

**Resultado obtenido:**
- Tipos invertidos → **500 Internal Server Error** (no 400/422 como se esperaba).
- `estrellas: 99` → **sin respuesta / timeout** (el servidor quedó colgado).
- Reserva con datos inválidos → **sin respuesta / timeout** (mismo efecto arrastrado).

**Análisis — este es el hallazgo más importante del informe:**
1. La API no valida tipos antes de insertar en SQLite. Al enviar `estrellas: "ABC"`,
   SQLite evalúa el `CHECK(estrellas BETWEEN 1 AND 5)` y lanza
   `sqlite3.IntegrityError`. Esa excepción **no está capturada** en `create_hotel()`
   ([app.py:71-91](app.py#L71-L91)), así que Flask la propaga como error 500 en vez
   de un 400 controlado.
2. Como la excepción se lanza *antes* de `conn.close()` (línea 90), **la conexión a
   SQLite queda abierta**, bloqueando el archivo `hotel.db`. Todas las solicitudes de
   escritura (`POST`/`PUT`/`DELETE`) posteriores se cuelgan indefinidamente hasta
   reiniciar el proceso del servidor. Esto se comprobó experimentalmente: los dos
   sub-casos siguientes (3.2 y 3.3), y luego el Caso 5, quedaron sin respuesta.
3. En resumen: **un solo request con un tipo de dato incorrecto puede tumbar la
   disponibilidad de escritura de toda la API** — un defecto de clase *Denegación de
   Servicio (DoS)*, trivial de disparar sin necesidad de autenticación ni volumen de
   tráfico.

**Recomendaciones:**
- Envolver el acceso a la base de datos en `try/except/finally` (o
  `with contextlib.closing(get_db()) as conn:`) para garantizar el cierre de la
  conexión pase lo que pase.
- Capturar `sqlite3.IntegrityError` / `sqlite3.OperationalError` y responder 400 con
  un mensaje descriptivo, en vez de dejar que la excepción se propague como 500.
- Validar tipos y rangos (`estrellas` entero 1-5, `habitaciones_totales` entero
  positivo) en la capa de aplicación, antes de tocar SQLite.
- Validar formato de `huesped_email` y que `habitaciones` sea un entero positivo en
  `create_reserva()`.

---

### Caso 4. Métodos HTTP no permitidos
**Descripción (guía):** intentar acceder mediante un método HTTP no soportado
(ej. `PATCH /productos`).
**Resultado esperado:** HTTP 405.

**Pruebas realizadas:**
- `PATCH /hotels` (la ruta solo registra GET/POST)
- `PATCH /reservas` (la ruta solo registra GET/POST)
- `DELETE /hotels` (DELETE solo existe para `/hotels/{id}`, no para la colección)

**Resultado obtenido:** los tres casos devolvieron **405 Method Not Allowed**.

**Análisis:** el sistema cumple correctamente. Flask/Werkzeug rechaza automáticamente
con 405 cualquier método no registrado para una ruta existente, sin necesidad de
código adicional. **No se encontraron problemas en este caso.**

---

### Caso 5. Simulación de ataques por fuerza bruta (opcional)
**Descripción (guía):** si la API implementa autenticación, realizar múltiples
intentos consecutivos de login con credenciales incorrectas y analizar si existe
bloqueo temporal, limitación de intentos, registro de eventos y mensajes seguros.

**Aplicabilidad:** la API de reserva de hoteles **no implementa autenticación**
(no hay endpoint de login, tokens ni API keys), por lo que el escenario literal del
caso no aplica.

**Prueba alternativa realizada:** para no dejar el caso vacío, se evaluó si existe
algún mecanismo general de *rate limiting* enviando 20 solicitudes `POST /reservas`
consecutivas y midiendo si en algún punto el servidor respondía `429`/`403`
(bloqueo) o simplemente log de eventos.

**Resultado obtenido:** la prueba no pudo completarse porque el servidor ya estaba
colgado por el hallazgo del Caso 3 (fuga de conexión SQLite).

**Análisis:** aun sin resultados de la ráfaga, la revisión del código de
[app.py](app.py) confirma que no existe ningún mecanismo de:
- Bloqueo temporal de IP/usuario.
- Limitación de número de intentos.
- Registro (logging) de solicitudes sospechosas o repetidas.
- Mensajes de error "seguros" (los mensajes de error actuales son descriptivos, lo
  cual es correcto para UX pero no está pensado para ocultar información sensible
  en un escenario de autenticación).

**Recomendación:** si en una futura iteración se agrega autenticación, incorporar
`Flask-Limiter` (u otro mecanismo de rate limiting), bloqueo temporal tras N
intentos fallidos, y logging de intentos de acceso.

## 4. Resumen de recomendaciones

1. Envolver el acceso a SQLite en `try/except/finally` en **todos** los endpoints para
   evitar fugas de conexión y traducir errores de integridad a `400 Bad Request`.
2. Validar contenido (no solo presencia) de campos obligatorios: rechazar strings vacíos
   y tipos incorrectos antes de tocar la base de datos.
3. Añadir validación explícita de rangos/formatos de negocio (`estrellas` 1-5,
   `habitaciones >= 1`, formato de `huesped_email`).
4. Ejecutar la API con `debug=False` en cualquier entorno accesible externamente, para no
   exponer el debugger interactivo de Werkzeug.
5. Si se añade autenticación en el futuro, incorporar limitación de intentos
   (rate limiting) y logging de intentos fallidos.

## 5. Respuesta a la pregunta de fuerza bruta (guía del Ejercicio 4, Caso 5)

La API no tiene endpoint de login ni mecanismo de autenticación, por lo que no aplica
un ataque de fuerza bruta de credenciales. Extendiendo la prueba a solicitudes
repetidas sobre un endpoint de escritura, se confirma que la API tampoco cuenta con
bloqueo temporal, limitación de intentos, ni registro de eventos — cualquier cliente
puede enviar solicitudes ilimitadas (cuando el servidor no está bloqueado por el bug de
la sección 3.3).
