import http from 'k6/http';
import { check } from 'k6';
import { Counter, Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const HOTEL_ID = __ENV.HOTEL_ID || '1';

// Métricas personalizadas
const solicitudesExitosas = new Counter('solicitudes_exitosas');
const solicitudesFallidas = new Counter('solicitudes_fallidas');
const porcentajeErrores = new Rate('porcentaje_errores');

function evaluarRespuesta(respuesta, nombre) {
    const exitosa = respuesta.status >= 200 && respuesta.status < 400;

    check(respuesta, {
        [`${nombre} respondió correctamente`]: () => exitosa,
    });

    solicitudesExitosas.add(exitosa ? 1 : 0);
    solicitudesFallidas.add(exitosa ? 0 : 1);
    porcentajeErrores.add(!exitosa);
}

export default function () {
    // Endpoint 1: listar hoteles
    const hoteles = http.get(`${BASE_URL}/hotels`);
    evaluarRespuesta(hoteles, 'GET /hotels');

    // Endpoint 2: consultar hotel por ID
    const hotel = http.get(`${BASE_URL}/hotels/${HOTEL_ID}`);
    evaluarRespuesta(hotel, 'GET /hotels/{id}');

    // Endpoint 3: listar reservas
    const reservas = http.get(`${BASE_URL}/reservas`);
    evaluarRespuesta(reservas, 'GET /reservas');

    // Endpoint 4: consultar disponibilidad
    const disponibilidad = http.get(
        `${BASE_URL}/hotels/${HOTEL_ID}/disponibilidad` +
        '?check_in=2027-01-10&check_out=2027-01-15'
    );

    evaluarRespuesta(
        disponibilidad,
        'GET /hotels/{id}/disponibilidad'
    );
}