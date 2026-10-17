"""Aviso por Telegram de tareas BLOQUEADAS. Token y chat por variables de entorno (o .env), nunca en el código.
Si no hay token o falla la red, devuelve None y la app sigue igual. Las respuestas las recibe telegram_bot.py."""
from __future__ import annotations

import asyncio
import os
import time

import skills

try:
    from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
except Exception:  # librería no instalada: la app funciona sin Telegram
    Bot = None


def configurado() -> bool:
    return bool(Bot and os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def motivos(r: dict) -> list[str]:
    m = []
    if (r.get("condiciones") or {}).get("bloqueo"):
        m.append(f"Condición: {r['condiciones']['bloqueo']}")
    for x in (r.get("aptitud") or {}).get("no_aptos", []):
        m.append(f"No apto: {x['trabajador']} ({x['motivo']})")
    m.append(f"Riesgo {r['riesgo']['nivel']} ({r['riesgo']['score']}/100): {r['riesgo']['base']}")
    m += [o for o in r["critico"].get("observaciones", []) if "Sin brechas" not in o]
    return m[:3]


def enviar_bloqueo(r: dict) -> str | None:
    """Envía el aviso con botones Aprobar/Rechazar. Devuelve el id del aviso o None si no se pudo."""
    if not configurado():
        return None
    aviso = f"T{int(time.time())}"
    cd = (r.get("condiciones") or {}).get("resumen") or {}
    texto = (f"⛔ SafeGuard · TAREA BLOQUEADA\n\nTarea: {r['tarea']['titulo']}\nSede: {cd.get('sede', '-')}\n"
             f"Clima: {cd.get('clima', '-')}\nRiesgo: {r['riesgo']['nivel']} ({r['riesgo']['score']}/100)\n"
             f"Decisión por regla: {r['autorizacion']['decision']}\n\nMotivos:\n"
             + "\n".join(f"{i}. {m}" for i, m in enumerate(motivos(r), 1)) + f"\n\nAviso {aviso}")
    botones = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Aprobar", callback_data=f"aprobar|{aviso}"),
                                     InlineKeyboardButton("❌ Rechazar", callback_data=f"rechazar|{aviso}")]])

    async def _enviar():
        async with Bot(os.environ["TELEGRAM_BOT_TOKEN"]) as bot:
            await bot.send_message(chat_id=os.environ["TELEGRAM_CHAT_ID"], text=texto, reply_markup=botones,
                                   read_timeout=8, write_timeout=8, connect_timeout=8)
    try:
        asyncio.run(_enviar())
    except Exception as e:  # red caída, token inválido, chat equivocado
        skills.registrar_auditoria("telegram_error", {"error": type(e).__name__})
        return None
    skills.registrar_auditoria("telegram_enviado", {"aviso": aviso, "tarea": r["tarea"]["titulo"]})
    return aviso


def respuesta(aviso: str) -> dict | None:
    """Busca en la auditoría la respuesta que dejó telegram_bot.py para este aviso."""
    for reg in skills.leer_auditoria(500):
        if reg["evento"] == "telegram_respuesta" and reg["detalle"].get("aviso") == aviso:
            return reg
    return None
