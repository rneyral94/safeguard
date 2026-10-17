"""Capa de seguridad: validación de entrada, anti prompt-injection, enmascaramiento de datos y permisos."""
import re
import unicodedata

MAX_LEN = 1500

PATRONES_INYECCION = [
    r"ignora(r)? (las|todas las)? ?instrucciones", r"ignore (all |previous )?instructions",
    r"olvida (todo|tus reglas)", r"system prompt", r"act[uú]a como", r"jailbreak",
    r"apru[eé]ba(lo)? (sin|igual)", r"no (eval[uú]es|revises)", r"<\s*/?\s*(system|instructions)",
]

PII = [
    (re.compile(r"\b\d{8}\b"), "[DNI]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"(\+?51)?\s?9\d{2}\s?\d{3}\s?\d{3}\b"), "[TELÉFONO]"),
]

# Quién puede hacer qué (principio de mínimo privilegio)
PERMISOS = {
    "Operador": {"evaluar"},
    "Supervisor": {"evaluar", "autorizar"},
    "Jefe de Seguridad": {"evaluar", "autorizar", "autorizar_critico", "ver_auditoria"},
}


def sanitizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKC", texto or "")
    texto = "".join(c for c in texto if c.isprintable() or c in "\n\t")
    return texto.strip()[:MAX_LEN]


def detectar_inyeccion(texto: str) -> list[str]:
    t = texto.lower()
    return [p for p in PATRONES_INYECCION if re.search(p, t)]


def enmascarar_pii(texto: str) -> str:
    for patron, reemplazo in PII:
        texto = patron.sub(reemplazo, texto)
    return texto


def validar_entrada(texto: str) -> tuple[str, list[str]]:
    """Devuelve el texto limpio y la lista de alertas de seguridad encontradas."""
    limpio = enmascarar_pii(sanitizar(texto))
    alertas = []
    if len(limpio) < 15:
        alertas.append("Descripción demasiado corta para evaluar el riesgo.")
    if detectar_inyeccion(limpio):
        alertas.append("Posible intento de manipular al agente (prompt injection). Entrada bloqueada.")
    return limpio, alertas


def puede(rol: str, accion: str) -> bool:
    return accion in PERMISOS.get(rol, set())


# ---------------- Login: usuarios con contraseña (hash PBKDF2, nunca en texto plano ni en el repositorio) ----------------
import hashlib
import hmac
import json
from pathlib import Path

USUARIOS_FILE = Path(__file__).parent / "usuarios.json"  # lo crea crear_usuarios.py; está en .gitignore


def hash_clave(clave: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), salt, 200_000).hex()


def hay_usuarios() -> bool:
    return USUARIOS_FILE.exists()


def verificar_login(usuario: str, clave: str) -> str | None:
    """Devuelve el rol si usuario y contraseña son correctos; si no, None."""
    if not hay_usuarios():
        return None
    u = json.loads(USUARIOS_FILE.read_text(encoding="utf-8")).get((usuario or "").strip().lower())
    if not u:
        return None
    ok = hmac.compare_digest(hash_clave(clave or "", bytes.fromhex(u["salt"])), u["hash"])
    return u["rol"] if ok else None
