"""Crea usuarios.json con los 3 usuarios de la demo. Ejecutar: python crear_usuarios.py
Las contraseñas se generan al azar (o se toman de SAFEGUARD_CLAVE_<USUARIO>) y se muestran UNA vez.
En el archivo solo queda el hash; usuarios.json está en .gitignore y nunca se sube al repositorio."""
import json
import os
import secrets

from security import USUARIOS_FILE, hash_clave

USUARIOS = {"operador": "Operador", "supervisor": "Supervisor", "jefe": "Jefe de Seguridad"}

datos = {}
print("Usuarios creados (guarda estas contraseñas, no se vuelven a mostrar):")
for usuario, rol in USUARIOS.items():
    clave = os.getenv(f"SAFEGUARD_CLAVE_{usuario.upper()}") or secrets.token_urlsafe(6)
    salt = secrets.token_bytes(16)
    datos[usuario] = {"rol": rol, "salt": salt.hex(), "hash": hash_clave(clave, salt)}
    print(f"  {usuario:<11} rol: {rol:<18} contraseña: {clave}")
USUARIOS_FILE.write_text(json.dumps(datos, indent=2), encoding="utf-8")
print(f"Guardado en {USUARIOS_FILE}")
