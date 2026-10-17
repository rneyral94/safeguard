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
