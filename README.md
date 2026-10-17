# SafeGuard: permiso de trabajo inteligente (caso M1 · Minería)

Antes de autorizar una tarea, 4 agentes de IA revisan qué salió mal antes en tareas parecidas y arman un checklist dinámico. El supervisor decide.

## Correr en PowerShell

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python crear_usuarios.py              # crea usuarios.json (operador, supervisor, jefe) y muestra las contraseñas una vez
# Opcional: archivo .env (no se sube) con ANTHROPIC_API_KEY=..., TELEGRAM_BOT_TOKEN=..., TELEGRAM_CHAT_ID=...
streamlit run app.py
python telegram_bot.py                # opcional, en otra terminal: recibe Aprobar/Rechazar
```

## Configuración

Ninguna clave va en el código ni en el repositorio.

1. **Claves en `.env` local.** Copia la plantilla y completa solo lo que uses:
   ```powershell
   Copy-Item .env.example .env
   ```
   `.env.example` tiene solo los nombres de las variables, con valores vacíos. El `.env` con tus valores está en `.gitignore` y la app lo lee al arrancar.

   | Variable | Para qué | Si falta |
   |---|---|---|
   | `ANTHROPIC_API_KEY` | Agentes con Claude | Modo demo sin IA |
   | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Avisos de tareas bloqueadas | Sin Telegram |
   | `DATASET_PATH` | CSV de Kaggle | Muestra incluida |
   | `TIEMPO_MANUAL_MIN`, `PAUSA_MONITOR`, `ANTHROPIC_MODEL` | Ajustes de la demo | Valores por defecto |

2. **Usuarios en `usuarios.json`**, que se genera en cada máquina:
   ```powershell
   python crear_usuarios.py
   ```
   Crea `operador`, `supervisor` y `jefe` con contraseñas al azar (se muestran una sola vez) y guarda solo su hash PBKDF2. `usuarios.json` está en `.gitignore`.

3. **No se suben nunca:** `.env`, `usuarios.json`, `audit_log.jsonl`, `data/incidentes_nuevos.csv`, `.streamlit/secrets.toml`.

## Login y usuarios

Tres usuarios: `operador` (evalúa), `supervisor` (autoriza), `jefe` (Jefe de Seguridad: autoriza casos críticos y ve la auditoría). Las contraseñas se guardan como hash PBKDF2 en `usuarios.json`, que está en `.gitignore`. Después de 5 intentos fallidos se bloquea el ingreso en la sesión.

## Condiciones del día

- **Clima automático** por sede (Cerro de Pasco, Arequipa, Cajamarca) con Open-Meteo (gratis, sin clave): código de clima, lluvia, viento, temperatura. Se clasifica en Normal, Lluvia, Viento fuerte (> 40 km/h), Tormenta eléctrica (códigos 95-99) o Helada (< 0 °C). Se muestra la hora de consulta y la fuente; se puede forzar a mano para la demo. Sin red: se usa Normal y se avisa.
- **Horas trabajadas** (> 10 h = fatiga) y **tareas simultáneas** en la zona.
- Reglas duras (también sin IA): tormenta eléctrica + altura o eléctrico → BLOQUEAR (nadie puede autorizar); lluvia o viento fuerte + altura → riesgo mínimo ALTO y controles extra; fatiga → el Crítico exige relevo o pausa; tareas simultáneas → coordinación entre supervisores y bloqueo compartido de energía. Cada control dice qué condición lo causó.

## Telegram (opcional)

Solo las tareas BLOQUEADAS envían un aviso (tarea, sede, clima, riesgo, 3 motivos) con botones Aprobar/Rechazar. `telegram_bot.py` escucha con long polling y registra la respuesta en la auditoría con el usuario de Telegram; la app la muestra al refrescar. La respuesta queda como registro: no salta las reglas duras ni los permisos de la app. Solo el chat configurado puede responder. Sin token o sin red, la app funciona igual.

1. En Telegram, abre **@BotFather** → `/newbot` → nombre y usuario (terminado en `bot`) → copia el token.
2. Pon el token en `.env` como `TELEGRAM_BOT_TOKEN=...` y ejecuta `python telegram_bot.py`.
3. Escríbele `/start` a tu bot: responde con tu `chat_id`. Ponlo en `.env` como `TELEGRAM_CHAT_ID=...` y reinicia el bot y la app.

## Correr en 3 pasos (bash)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="tu_clave"        # sin clave corre en modo demo (sin internet)
streamlit run app.py
```

Para usar el dataset real de Kaggle (Industrial Safety and Health Analytics Database):

```bash
export DATASET_PATH="ruta/IHMStefanini_industrial_safety_and_health_database_with_accidents_description.csv"
```

Las columnas en inglés se renombran solas y cada `Critical Risk` en inglés (Pressed, Fall, Pressurized Systems, Suspended Loads...) se mapea al catálogo de controles en español (`skills.MAPEO_RIESGOS`). Un glosario español→inglés permite que una tarea escrita en español encuentre incidentes descritos en inglés.

## Qué mostrar en la demo

- **Mapa de razonamiento** (pestaña 🧠): diagrama de agentes y herramientas, el debate Crítico vs Analista (cada objeción con su réplica: acepta/discrepa) y la línea de tiempo completa.
- **🛡️ Simular ataque**: envía un prompt injection con datos personales; se bloquea antes de llegar a la IA (0 tokens), se enmascaran los datos y queda en auditoría.
- **Impacto** (pestaña 📈): tiempo del agente vs. tiempo manual estimado y costo en tokens por evaluación.
  Supuesto del tiempo manual: 45 min = revisar historial (~20) + armar ATS/checklist (~15) + validar con otro supervisor (~10). Ajustable con `TIEMPO_MANUAL_MIN`.
  Costo con precios públicos por millón de tokens (Sonnet 5.5: US$2 entrada / US$10 salida).

## Novedades

- **Agente del Contratista** (`contractor_agent.py`, datos en `data/contratistas.json`): representa a otra empresa. El Autorizador le envía un mensaje estructurado (`consulta_aptitud`: riesgos + trabajadores) y el contratista responde por cada trabajador apto/no apto y el motivo, sin compartir su expediente (fechas, otras capacitaciones, datos personales). Si alguien no está apto para un riesgo detectado, la tarea se bloquea por regla y nadie puede autorizarla. El intercambio se ve como una conversación entre dos organizaciones, cada una con su identidad de agente.
- **El sistema aprende**: después de autorizar, el supervisor cierra la tarea (sin novedad / casi-accidente / incidente). Los casi-accidentes e incidentes se guardan en `data/incidentes_nuevos.csv` (el dataset original no se toca) y la siguiente evaluación parecida ya los encuentra (aparecen como `NUEVO-xxxx`). El texto pasa por el mismo filtro anti-manipulación antes de entrar al historial.
- **Normativa**: cada control del catálogo muestra su respaldo en el Reglamento de Seguridad y Salud Ocupacional en Minería (D.S. 024-2016-EM y modificatorias) y el tema que cubre. **Ninguna referencia tiene número de artículo: todas están marcadas "por verificar"** hasta contrastarlas con el texto oficial (`skills.NORMATIVA`).
- **Monitor de agentes**: tarjetas en vivo con el estado de cada agente y quién le habla a quién.

## Agentes

| Agente | Qué hace | Skills que usa |
|---|---|---|
| Analista de incidentes | Encuentra incidentes parecidos y el patrón de riesgo | buscar_incidentes_similares, estadisticas_riesgo |
| Generador de checklist | Controles obligatorios del catálogo + máx. 3 por las condiciones del día | controles_base |
| Crítico de seguridad | Desconfía del checklist y busca lo que se pasó por alto | — |
| Autorizador | Decide por regla (no por IA), consulta al contratista y explica en lenguaje simple | calcular_nivel_riesgo |
| Agente del Contratista (otra empresa) | Responde si cada trabajador está apto para los riesgos detectados | consulta_aptitud |
| Humano | Marca controles en campo, autoriza según su rol y cierra la tarea reportando cómo terminó | registrar_auditoria, registrar_incidente_nuevo |

## Seguridad

- Datos personales enmascarados (DNI, correo, teléfono) y columna de género eliminada.
- Bloqueo de intentos de manipular al agente (prompt injection); el texto del usuario se trata como dato.
- La decisión crítica la toma una regla fija; la IA no puede relajarla. El puntaje de riesgo se calcula siempre sobre la búsqueda determinista de incidentes, no sobre los que la IA elija.
- Si la API falla o no responde (timeout 45 s), cada agente usa su lógica de respaldo y la evaluación termina igual.
- Permisos por rol: Operador evalúa, Supervisor autoriza, solo el Jefe de Seguridad autoriza casos críticos.
- No se puede autorizar sin marcar todos los controles obligatorios.
- Auditoría de cada evaluación, autorización y bloqueo (audit_log.jsonl).
- La clave de la API va en variable de entorno, nunca en el código.
