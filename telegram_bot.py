"""Bot de Telegram (long polling, sin webhook) que recibe Aprobar/Rechazar y lo registra en la auditoría.
Ejecutar en otra terminal: python telegram_bot.py   (requiere TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID)
/start responde con el chat_id, útil para configurar TELEGRAM_CHAT_ID."""
import os

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

import agents  # noqa: F401  (carga .env igual que la app)
import skills


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"SafeGuard activo. Tu chat_id es: {update.effective_chat.id}")


async def boton(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if str(q.message.chat.id) != os.getenv("TELEGRAM_CHAT_ID"):  # solo el chat autorizado puede responder
        await q.answer("Chat no autorizado", show_alert=True)
        return
    accion, aviso = (q.data or "|").split("|", 1)
    if accion not in ("aprobar", "rechazar"):
        await q.answer()
        return
    usuario = q.from_user
    nombre = f"telegram:@{usuario.username}" if usuario.username else f"telegram:{usuario.id}"
    skills.registrar_auditoria("telegram_respuesta", {"aviso": aviso, "respuesta": accion}, nombre)
    await q.answer("Registrado en la auditoría")
    await q.edit_message_text(q.message.text + f"\n\n{'✅ APROBADO' if accion == 'aprobar' else '❌ RECHAZADO'} por {nombre}")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN (variable de entorno o .env).")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(boton))
    print("Bot de SafeGuard escuchando (long polling). Ctrl+C para salir.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
