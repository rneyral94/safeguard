# SafeGuard: permiso de trabajo inteligente (caso M1 · Minería)

Antes de autorizar una tarea, 4 agentes de IA revisan qué salió mal antes en tareas parecidas y arman un checklist dinámico. El supervisor decide.

## Correr en 3 pasos

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

## Agentes

| Agente | Qué hace | Skills que usa |
|---|---|---|
| Analista de incidentes | Encuentra incidentes parecidos y el patrón de riesgo | buscar_incidentes_similares, estadisticas_riesgo |
| Generador de checklist | Controles obligatorios del catálogo + máx. 3 por las condiciones del día | controles_base |
| Crítico de seguridad | Desconfía del checklist y busca lo que se pasó por alto | — |
| Autorizador | Decide por regla (no por IA) y explica en lenguaje simple | calcular_nivel_riesgo |
| Humano | Marca controles en campo y autoriza según su rol | registrar_auditoria |

## Seguridad

- Datos personales enmascarados (DNI, correo, teléfono) y columna de género eliminada.
- Bloqueo de intentos de manipular al agente (prompt injection); el texto del usuario se trata como dato.
- La decisión crítica la toma una regla fija; la IA no puede relajarla. El puntaje de riesgo se calcula siempre sobre la búsqueda determinista de incidentes, no sobre los que la IA elija.
- Si la API falla o no responde (timeout 45 s), cada agente usa su lógica de respaldo y la evaluación termina igual.
- Permisos por rol: Operador evalúa, Supervisor autoriza, solo el Jefe de Seguridad autoriza casos críticos.
- No se puede autorizar sin marcar todos los controles obligatorios.
- Auditoría de cada evaluación, autorización y bloqueo (audit_log.jsonl).
- La clave de la API va en variable de entorno, nunca en el código.
