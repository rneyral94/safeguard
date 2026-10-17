"""Condiciones del día: clima (Open-Meteo, sin clave), fatiga y tareas simultáneas. Reglas deterministas."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime

SEDES = {"Cerro de Pasco": (-10.68, -76.26), "Arequipa": (-16.53, -71.59), "Cajamarca": (-6.98, -78.52)}
CLIMAS = ["Normal", "Lluvia", "Viento fuerte", "Tormenta eléctrica", "Helada"]
HORAS_FATIGA = 10


def clasificar(codigo: int, lluvia_mm: float, viento_kmh: float, temp_c: float) -> str:
    if 95 <= codigo <= 99:
        return "Tormenta eléctrica"
    if temp_c < 0:
        return "Helada"
    if viento_kmh > 40:
        return "Viento fuerte"
    if lluvia_mm > 0 or 51 <= codigo <= 67 or 80 <= codigo <= 82:
        return "Lluvia"
    return "Normal"


def consultar_clima(sede: str, timeout: float = 4.0) -> dict:
    """Clima actual de la sede. Si no hay red o la API falla, devuelve Normal con ok=False (la app sigue)."""
    lat, lon = SEDES[sede]
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&current=temperature_2m,rain,weather_code,wind_speed_10m&wind_speed_unit=kmh")
    hora = datetime.now().strftime("%H:%M")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            actual = json.load(resp)["current"]
        codigo, temp = int(actual["weather_code"]), float(actual["temperature_2m"])
        lluvia, viento = float(actual.get("rain") or 0), float(actual["wind_speed_10m"])
        return {"ok": True, "estado": clasificar(codigo, lluvia, viento, temp), "codigo": codigo, "lluvia_mm": lluvia,
                "viento_kmh": viento, "temp_c": temp, "hora": hora, "fuente": "Open-Meteo"}
    except Exception as e:  # sin red, timeout, respuesta inesperada
        return {"ok": False, "estado": "Normal", "hora": hora, "fuente": "Open-Meteo", "error": type(e).__name__}


def evaluar(tarea: dict, riesgos: list[str]) -> dict:
    """Aplica las reglas duras de condiciones. Cada control dice qué condición lo causó."""
    c = tarea.get("condiciones") or {}
    clima, horas = c.get("clima", "Normal"), float(c.get("horas") or 0)
    texto = (tarea.get("texto", "") + " " + " ".join(riesgos)).lower()
    altura = "altura" in texto
    electrico = "eléctric" in texto or "electric" in texto or "energiz" in texto
    out = {"bloqueo": None, "riesgo_minimo": None, "controles": [], "observaciones": []}

    def ctrl(control, condicion):
        out["controles"].append({"control": control, "riesgo": f"Condición: {condicion}", "critico": True,
                                 "condicion": condicion})

    if clima == "Tormenta eléctrica" and (altura or electrico):
        out["bloqueo"] = f"Tormenta eléctrica + trabajo {'en altura' if altura else 'eléctrico'}"
        ctrl("Suspender la tarea hasta 30 min después del último rayo", "Tormenta eléctrica")
    elif clima == "Tormenta eléctrica":
        ctrl("Refugio identificado y alerta de tormenta comunicada a la cuadrilla", "Tormenta eléctrica")
    if clima in ("Lluvia", "Viento fuerte") and altura:
        out["riesgo_minimo"] = f"{clima} + trabajo en altura"
        ctrl("Inspeccionar plataformas y anclajes por agua o viento antes de subir", clima)
        ctrl("Suspender el trabajo en altura si la lluvia o el viento aumentan (viento > 40 km/h)", clima)
    if clima == "Helada":
        ctrl("Verificar hielo en superficies, escaleras y plataformas antes de iniciar", "Helada")
    if horas > HORAS_FATIGA:
        out["observaciones"].append(f"Fatiga: la cuadrilla lleva {horas:g} h en el turno (más de {HORAS_FATIGA} h). "
                                    "Exijo relevo o pausa antes de iniciar.")
        ctrl("Relevo de la cuadrilla o pausa de descanso antes de iniciar", f"Fatiga ({horas:g} h trabajadas)")
    if c.get("simultaneas"):
        desc = c.get("simultaneas_desc") or "otra tarea en la zona"
        out["observaciones"].append(f"Tareas simultáneas en la zona ({desc}). Exijo coordinación entre supervisores "
                                    "y bloqueo compartido de energía.")
        ctrl("Coordinación previa entre los supervisores de las tareas simultáneas", "Tareas simultáneas")
        ctrl("Bloqueo compartido de energía: un candado por cada cuadrilla", "Tareas simultáneas")
    return out
