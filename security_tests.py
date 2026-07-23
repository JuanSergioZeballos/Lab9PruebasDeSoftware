"""
Ejercicio 4 - Pruebas basicas de seguridad con Python (Requests)
API: Sistema de Reserva de Hoteles (Flask)

Ejecuta 5 casos de prueba de seguridad contra la API en ejecucion:
  1. Validacion de recursos inexistentes      -> 404
  2. Validacion de datos incompletos          -> 400 + mensaje descriptivo
  3. Validacion de tipos de datos incorrectos -> rechazo de la solicitud
  4. Metodos HTTP no permitidos               -> 405
  5. Fuerza bruta (opcional)                  -> N/A, la API no tiene login

Uso:
    python app.py                # en una terminal, deja el servidor corriendo
    python security_tests.py     # en otra terminal
"""
import json
import time
import requests

BASE_URL = "http://localhost:5000"
TIMEOUT = 5

results = []


def safe_request(metodo, url, **kwargs):
    """Envuelve requests.* para que timeouts/desconexiones no aborten todo el script."""
    try:
        return getattr(requests, metodo)(url, **kwargs), None
    except requests.exceptions.RequestException as exc:
        return None, exc


def log(caso, descripcion, esperado, obtenido, ok, detalle=""):
    results.append({
        "caso": caso,
        "descripcion": descripcion,
        "esperado": esperado,
        "obtenido": obtenido,
        "resultado": "PASS" if ok else "FAIL",
        "detalle": detalle,
    })
    marca = "[OK]" if ok else "[FALLO]"
    print(f"{marca} {caso} - {descripcion}")
    print(f"       esperado={esperado}  obtenido={obtenido}  {detalle}")


def caso1_recursos_inexistentes():
    print("\n=== CASO 1: Validacion de recursos inexistentes (GET) ===")

    rv = requests.get(f"{BASE_URL}/hotels/999999", timeout=TIMEOUT)
    log("Caso 1.1", "GET /hotels/999999 (id inexistente)",
        "404", str(rv.status_code), rv.status_code == 404)

    rv = requests.get(f"{BASE_URL}/reservas/999999", timeout=TIMEOUT)
    log("Caso 1.2", "GET /reservas/999999 (id inexistente)",
        "404", str(rv.status_code), rv.status_code == 404)

    rv = requests.get(f"{BASE_URL}/hotels/999999/disponibilidad?check_in=2027-01-01&check_out=2027-01-02",
                       timeout=TIMEOUT)
    log("Caso 1.3", "GET disponibilidad de hotel inexistente",
        "404", str(rv.status_code), rv.status_code == 404)


def caso2_datos_incompletos():
    print("\n=== CASO 2: Validacion de datos incompletos (POST) ===")

    # Campo requerido totalmente ausente
    rv = requests.post(f"{BASE_URL}/hotels", json={"nombre": "Hotel Incompleto"}, timeout=TIMEOUT)
    tiene_mensaje = "error" in rv.json() if rv.headers.get("content-type", "").startswith("application/json") else False
    log("Caso 2.1", "POST /hotels sin campos obligatorios (direccion, ciudad, etc.)",
        "400 + mensaje de error", f"{rv.status_code} (mensaje={tiene_mensaje})",
        rv.status_code == 400 and tiene_mensaje)

    # Campo requerido presente pero vacio (string vacio)
    rv = requests.post(f"{BASE_URL}/hotels", json={
        "nombre": "", "direccion": "", "ciudad": "",
        "estrellas": 3, "habitaciones_totales": 10
    }, timeout=TIMEOUT)
    log("Caso 2.2", "POST /hotels con campos obligatorios vacios ('')",
        "400 + mensaje de error", str(rv.status_code),
        rv.status_code == 400,
        detalle="La API valida solo la AUSENCIA del campo, no strings vacios" if rv.status_code != 400 else "")

    # Body vacio en reservas
    rv = requests.post(f"{BASE_URL}/reservas", json={}, timeout=TIMEOUT)
    log("Caso 2.3", "POST /reservas con body vacio",
        "400 + mensaje de error", str(rv.status_code), rv.status_code == 400)


def caso3_tipos_de_datos():
    print("\n=== CASO 3: Validacion de tipos de datos incorrectos ===")

    # Tipos invertidos: nombre numerico, estrellas como texto
    rv, err = safe_request("post", f"{BASE_URL}/hotels", json={
        "nombre": 12345,
        "direccion": "Av. Test 1",
        "ciudad": "Lima",
        "estrellas": "ABC",
        "habitaciones_totales": "diez"
    }, timeout=TIMEOUT)
    if err:
        log("Caso 3.1", "POST /hotels con tipos incorrectos (nombre:int, estrellas:str, habitaciones_totales:str)",
            "400/422 (rechazado)", f"SIN RESPUESTA ({type(err).__name__})", False,
            detalle="El servidor no responde: excepcion no controlada (sqlite3.IntegrityError) deja la conexion "
                     "abierta y bloquea el hilo -> riesgo de denegacion de servicio (DoS)")
    else:
        rechazado = rv.status_code in (400, 422)
        log("Caso 3.1", "POST /hotels con tipos incorrectos (nombre:int, estrellas:str, habitaciones_totales:str)",
            "400/422 (rechazado)", str(rv.status_code), rechazado,
            detalle="SQLite acepta el INSERT sin verificar tipo, o el error de tipo se traduce en un 500 "
                     "no controlado" if not rechazado else "")

    # estrellas fuera de rango permitido (1-5) segun el CHECK de la tabla
    rv, err = safe_request("post", f"{BASE_URL}/hotels", json={
        "nombre": "Hotel Fuera de Rango",
        "direccion": "Av. Test 2",
        "ciudad": "Lima",
        "estrellas": 99,
        "habitaciones_totales": 10
    }, timeout=TIMEOUT)
    if err:
        log("Caso 3.2", "POST /hotels con estrellas=99 (fuera de rango 1-5)",
            "400/422/500 (rechazado)", f"SIN RESPUESTA ({type(err).__name__})", False,
            detalle="El servidor no responde tras el caso anterior (conexion/lock de SQLite sin liberar)")
    else:
        rechazado = rv.status_code in (400, 422, 500)
        log("Caso 3.2", "POST /hotels con estrellas=99 (fuera de rango 1-5)",
            "400/422/500 (rechazado)", str(rv.status_code), rechazado,
            detalle="El CHECK de SQLite rechaza el valor pero la API responde 500 en vez de 400" if rv.status_code == 500 else "")

    # habitaciones como numero negativo en una reserva
    hotel_rv, err = safe_request("post", f"{BASE_URL}/hotels", json={
        "nombre": "Hotel Caso3", "direccion": "Av. Test 3", "ciudad": "Lima",
        "estrellas": 4, "habitaciones_totales": 10
    }, timeout=TIMEOUT)
    hotel_id = hotel_rv.json().get("id") if (hotel_rv is not None and hotel_rv.status_code == 201) else None

    if hotel_id:
        rv, err = safe_request("post", f"{BASE_URL}/reservas", json={
            "hotel_id": hotel_id,
            "huesped_nombre": "Cliente Test",
            "huesped_email": "no-es-un-email",
            "check_in": "2027-01-10",
            "check_out": "2027-01-12",
            "habitaciones": -5
        }, timeout=TIMEOUT)
        if err:
            log("Caso 3.3", "POST /reservas con habitaciones=-5 y email invalido",
                "400/422 (rechazado)", f"SIN RESPUESTA ({type(err).__name__})", False)
        else:
            rechazado = rv.status_code in (400, 422)
            log("Caso 3.3", "POST /reservas con habitaciones=-5 y email invalido",
                "400/422 (rechazado)", str(rv.status_code), rechazado,
                detalle="La API no valida formato de email ni valores negativos de habitaciones" if not rechazado else "")
    else:
        log("Caso 3.3", "POST /reservas con habitaciones=-5 y email invalido",
            "400/422 (rechazado)", "N/A (no se pudo crear hotel base)", False)


def caso4_metodos_no_permitidos():
    print("\n=== CASO 4: Metodos HTTP no permitidos ===")

    rv = requests.patch(f"{BASE_URL}/hotels", json={"nombre": "x"}, timeout=TIMEOUT)
    log("Caso 4.1", "PATCH /hotels (no soportado, solo GET/POST)",
        "405", str(rv.status_code), rv.status_code == 405)

    rv = requests.patch(f"{BASE_URL}/reservas", json={"estado": "x"}, timeout=TIMEOUT)
    log("Caso 4.2", "PATCH /reservas (no soportado, solo GET/POST)",
        "405", str(rv.status_code), rv.status_code == 405)

    rv = requests.delete(f"{BASE_URL}/hotels", timeout=TIMEOUT)
    log("Caso 4.3", "DELETE /hotels (no soportado a nivel de coleccion)",
        "405", str(rv.status_code), rv.status_code == 405)


def caso5_fuerza_bruta():
    print("\n=== CASO 5: Simulacion de fuerza bruta (opcional) ===")
    print("La API de reservas de hoteles NO implementa autenticacion/login,")
    print("por lo tanto este caso no aplica de forma literal (no hay endpoint de credenciales).")
    print("En su lugar se evalua si existe algun tipo de rate limiting sobre un endpoint")
    print("sensible (creacion de reservas), enviando solicitudes repetidas y consecutivas.")

    hotel_rv, err = safe_request("post", f"{BASE_URL}/hotels", json={
        "nombre": "Hotel Caso5", "direccion": "Av. Test 5", "ciudad": "Lima",
        "estrellas": 4, "habitaciones_totales": 5
    }, timeout=TIMEOUT)
    if err:
        log("Caso 5.1", "Preparacion (crear hotel base)", "201", f"SIN RESPUESTA ({type(err).__name__})", False,
            detalle="El servidor sigue sin responder por el bloqueo de conexion detectado en el Caso 3")
        return
    hotel_id = hotel_rv.json().get("id") if hotel_rv.status_code == 201 else None

    intentos = 20
    codigos = []
    fallos_conexion = 0
    inicio = time.time()
    for i in range(intentos):
        rv, err = safe_request("post", f"{BASE_URL}/reservas", json={
            "hotel_id": hotel_id if hotel_id else 999999,
            "huesped_nombre": f"Bot{i}",
            "huesped_email": f"bot{i}@mail.com",
            "check_in": "2027-02-01",
            "check_out": "2027-02-02",
            "habitaciones": 1
        }, timeout=TIMEOUT)
        if err:
            fallos_conexion += 1
            codigos.append(f"ERR:{type(err).__name__}")
        else:
            codigos.append(rv.status_code)
    duracion = time.time() - inicio

    bloqueado_en_algun_punto = any(c in (429, 403) for c in codigos)
    log("Caso 5.1", f"{intentos} solicitudes consecutivas a POST /reservas en {duracion:.2f}s",
        "Se esperaria 429/403 si hubiese rate limiting",
        f"codigos={codigos}",
        False,  # se marca como hallazgo, no como pass/fail estricto
        detalle="No se detecto bloqueo temporal ni limitacion de intentos (no hay mecanismo anti fuerza-bruta)"
        if not bloqueado_en_algun_punto else "Se detecto un mecanismo de limitacion")
    results[-1]["resultado"] = "N/A (hallazgo)"


def resumen():
    print("\n" + "=" * 70)
    print("RESUMEN DE PRUEBAS DE SEGURIDAD")
    print("=" * 70)
    total = len(results)
    passed = sum(1 for r in results if r["resultado"] == "PASS")
    failed = sum(1 for r in results if r["resultado"] == "FAIL")
    na = sum(1 for r in results if r["resultado"].startswith("N/A"))
    for r in results:
        print(f"  [{r['resultado']:<12}] {r['caso']:<10} {r['descripcion']}")
    print("-" * 70)
    print(f"Total: {total}  |  PASS: {passed}  |  FAIL: {failed}  |  N/A: {na}")

    with open("security_test_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nReporte detallado guardado en security_test_report.json")


if __name__ == "__main__":
    try:
        requests.get(BASE_URL, timeout=TIMEOUT)
    except requests.exceptions.ConnectionError:
        print(f"ERROR: no se pudo conectar a {BASE_URL}")
        print("Asegurate de ejecutar 'python app.py' en otra terminal antes de correr este script.")
        raise SystemExit(1)

    caso1_recursos_inexistentes()
    caso2_datos_incompletos()
    caso3_tipos_de_datos()
    caso4_metodos_no_permitidos()
    caso5_fuerza_bruta()
    resumen()
