"""Agente del Contratista: representa a la empresa contratista y responde por sus trabajadores.

Vive fuera de SafeGuard (otra organización, otros datos). Se comunica solo por mensajes estructurados:
recibe riesgos + trabajadores y devuelve apto/no apto con un motivo. Nunca entrega el expediente completo
(fechas, otras capacitaciones, datos personales): así se respeta la privacidad entre empresas.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

DATOS = Path(__file__).parent / "data" / "contratistas.json"
NOMBRES_CAP = {"trabajo_en_altura": "Trabajo en altura", "espacio_confinado": "Espacio confinado",
               "trabajo_en_caliente": "Trabajo en caliente", "electrico": "Riesgo eléctrico"}
# Palabra clave en el riesgo detectado -> capacitación obligatoria
CAPACITACION_POR_RIESGO = [("altura", "trabajo_en_altura"), ("confinado", "espacio_confinado"),
                           ("quemadura", "trabajo_en_caliente"), ("caliente", "trabajo_en_caliente"),
                           ("soldadura", "trabajo_en_caliente"), ("eléctric", "electrico"), ("electric", "electrico")]


def _empresas() -> dict:
    return {e["id"]: e for e in json.loads(DATOS.read_text(encoding="utf-8"))["empresas"]}


def identidad(empresa_id: str) -> dict:
    """Tarjeta pública del agente (lo único que la mina sabe de él)."""
    e = _empresas()[empresa_id]
    return {"agente_id": f"agente.{e['id']}.contratista", "organizacion": e["nombre"],
            "capacidades": ["consulta_aptitud"]}


def directorio() -> list[dict]:
    """Lista pública mínima para el formulario: empresa y nombre de sus trabajadores (sin expediente)."""
    return [{"id": e["id"], "nombre": e["nombre"],
             "trabajadores": [{"id": t["id"], "nombre": t["nombre"]} for t in e["trabajadores"]]}
            for e in _empresas().values()]


def capacitaciones_requeridas(riesgos: list[str]) -> list[str]:
    req = []
    for r in riesgos:
        bajo = r.lower()
        for clave, cap in CAPACITACION_POR_RIESGO:
            if clave in bajo and cap not in req:
                req.append(cap)
    return req


def responder(mensaje: dict, hoy: date | None = None) -> dict:
    """Atiende un mensaje {tipo: consulta_aptitud, empresa, riesgos, trabajadores} y responde solo apto/motivo."""
    hoy = hoy or date.today()
    empresa = _empresas()[mensaje["empresa"]]
    requeridas = capacitaciones_requeridas(mensaje.get("riesgos", []))
    seguro_ok = date.fromisoformat(empresa["seguro_sctr_vence"]) >= hoy
    por_id = {t["id"]: t for t in empresa["trabajadores"]}
    respuestas = []
    for tid in mensaje.get("trabajadores", []):
        t = por_id.get(tid)
        if not t:
            respuestas.append({"trabajador": tid, "apto": False, "motivo": "No figura en la planilla del contratista"})
            continue
        problemas = [] if seguro_ok else ["Seguro SCTR de la empresa vencido"]
        for cap in requeridas:
            vence = t["capacitaciones"].get(cap)
            if not vence:
                problemas.append(f"Sin capacitación en {NOMBRES_CAP[cap]}")
            elif date.fromisoformat(vence) < hoy:
                problemas.append(f"Capacitación en {NOMBRES_CAP[cap]} vencida")
        respuestas.append({"trabajador": t["nombre"], "apto": not problemas,
                           "motivo": "; ".join(problemas) or "Capacitaciones y seguro vigentes para los riesgos consultados"})
    return {"tipo": "respuesta_aptitud", "de": identidad(empresa["id"])["agente_id"], "para": mensaje.get("de"),
            "capacitaciones_verificadas": [NOMBRES_CAP[c] for c in requeridas], "respuestas": respuestas}
