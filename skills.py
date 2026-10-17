"""Skills (herramientas) que usan los agentes. Todas son deterministas y auditables."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE = Path(__file__).parent
AUDIT_FILE = BASE / "audit_log.jsonl"
NUEVOS_FILE = BASE / "data" / "incidentes_nuevos.csv"  # reportes de cierre: no se toca el dataset original
NIVELES = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}

# Catálogo de controles por riesgo crítico (base del checklist dinámico)
CONTROLES = {
    "Caída de altura": ["Arnés de cuerpo completo con doble línea de vida", "Punto de anclaje certificado", "Inspección de andamio o plataforma firmada", "Vigía permanente en la zona"],
    "Atrapamiento": ["Bloqueo y etiquetado (LOTO) de la energía", "Verificar energía cero antes de intervenir", "Guardas de protección instaladas", "Prohibido retirar guardas con equipo en marcha"],
    "Proyección de partículas": ["Careta facial y lentes de seguridad", "Delimitar zona de exclusión de 5 m", "Verificar presión del sistema antes de abrir"],
    "Eléctrico": ["Bloqueo eléctrico (LOTO) con candado personal", "Medición de ausencia de tensión", "Herramientas dieléctricas", "Electricista certificado presente"],
    "Sustancias químicas": ["Revisar hoja de seguridad (MSDS)", "Respirador con filtro adecuado", "Ducha y lavaojos operativos", "Ventilación forzada"],
    "Vehículos y equipo móvil": ["Segregar peatones de equipos móviles", "Contacto radial con operador", "Alarma de retroceso verificada", "Cuñas y freno de parqueo"],
    "Herramientas manuales": ["Inspección de herramientas antes del uso", "Guantes anticorte", "Postura y apoyo estable"],
    "Corte": ["Guantes anticorte", "Herramienta con protector", "Zona de trabajo ordenada"],
    "Quemadura": ["Ropa ignífuga", "Permiso de trabajo en caliente", "Extintor a menos de 10 m", "Vigía contra incendio"],
    "Espacio confinado": ["Medición de gases (O2, CO, H2S, LEL)", "Vigía en el ingreso", "Plan de rescate aprobado", "Ventilación forzada"],
    "Cargas suspendidas": ["Plan de izaje firmado", "Nadie bajo la carga suspendida", "Eslingas y grilletes inspeccionados", "Rigger certificado dirigiendo la maniobra"],
    "Caída de rocas": ["Desatado de rocas antes de ingresar", "Inspección geomecánica del frente", "Sostenimiento verificado"],
    "Caída al mismo nivel": ["Orden y limpieza del área", "Iluminación adecuada del tránsito", "Calzado de seguridad con buena adherencia"],
    "Animales venenosos": ["Inspección del área por presencia de animales o insectos", "Botiquín con antialérgico disponible", "Guantes y ropa manga larga"],
    "Otros": ["Charla de 5 minutos con la cuadrilla", "Análisis de trabajo seguro (ATS) firmado"],
}

# Riesgos críticos del dataset de Kaggle (en inglés) -> catálogo CONTROLES. Se revisa en orden: la primera
# palabra clave que aparezca gana (p. ej. "Projection/Burning" cae en Proyección antes que en Quemadura).
MAPEO_RIESGOS = [
    ("same level", "Caída al mismo nivel"),
    ("rock", "Caída de rocas"),
    ("fall", "Caída de altura"),
    ("suspended", "Cargas suspendidas"),
    ("pressed", "Atrapamiento"),
    ("machine protection", "Atrapamiento"),
    ("blocking", "Atrapamiento"),
    ("power lock", "Atrapamiento"),
    ("plates", "Atrapamiento"),
    ("electric", "Eléctrico"),
    ("chemical", "Sustancias químicas"),
    ("projection", "Proyección de partículas"),
    ("pressurized", "Proyección de partículas"),
    ("vehicle", "Vehículos y equipo móvil"),
    ("traffic", "Vehículos y equipo móvil"),
    ("mobile equipment", "Vehículos y equipo móvil"),
    ("manual tools", "Herramientas manuales"),
    ("cut", "Corte"),
    ("burn", "Quemadura"),
    ("liquid metal", "Quemadura"),
    ("confined", "Espacio confinado"),
    ("bees", "Animales venenosos"),
    ("venomous", "Animales venenosos"),
    ("sting", "Animales venenosos"),
]

# Glosario español -> inglés para que una tarea escrita en español encuentre incidentes descritos en inglés
GLOSARIO = {
    "altura": "height fall scaffold platform", "andamio": "scaffold", "plataforma": "platform",
    "faja": "conveyor belt", "polin": "pulley roller idler", "polín": "pulley roller idler", "polines": "pulley roller idler",
    "bomba": "pump", "impulsor": "impeller", "relaves": "tailings", "tecle": "hoist chain",
    "llave": "wrench key", "llaves": "wrench key", "presión": "pressure", "presion": "pressure",
    "energizado": "energized electrical", "eléctrico": "electrical", "electrico": "electrical",
    "tanque": "tank", "químicas": "chemical acid", "químico": "chemical acid", "quimicas": "chemical acid",
    "solución": "solution", "lixiviación": "leaching", "ácido": "acid",
    "camión": "truck vehicle", "camion": "truck vehicle", "volquete": "truck", "equipo móvil": "mobile equipment",
    "carga": "load", "izaje": "lifting crane load", "grúa": "crane", "roca": "rock", "rocas": "rock",
    "mano": "hand", "dedo": "finger", "manguera": "hose", "válvula": "valve", "valvula": "valve",
    "soldadura": "welding", "corte": "cut", "quemadura": "burn", "caliente": "hot",
    "mantenimiento": "maintenance", "limpieza": "cleaning", "desmontaje": "disassembly removal",
    "perforación": "drilling", "perforacion": "drilling", "chancado": "crusher", "molino": "mill",
    "cuadrilla": "crew", "operador": "operator", "mecánico": "mechanic", "noche": "night",
    "ingreso": "entered entry", "sedimentos": "sediments", "metros": "meters", "gases": "gas",
}


def mapear_riesgo(riesgo: str) -> str:
    """Traduce un riesgo crítico (inglés del dataset de Kaggle o español de la muestra) al catálogo CONTROLES."""
    r = str(riesgo).strip()
    if r in CONTROLES:
        return r
    bajo = r.lower()
    return next((destino for clave, destino in MAPEO_RIESGOS if clave in bajo), "Otros")


def expandir_consulta(texto: str) -> str:
    """Agrega los equivalentes en inglés de los términos de la tarea (el dataset real está en inglés)."""
    bajo = texto.lower()
    extra = [en for es, en in GLOSARIO.items() if es in bajo]
    return texto + (" " + " ".join(extra) if extra else "")


def cargar_incidentes(path: str | None = None) -> pd.DataFrame:
    """Carga el dataset (Kaggle Industrial Safety o la muestra de demo) más los reportes nuevos de los supervisores."""
    path = path or os.getenv("DATASET_PATH") or str(BASE / "data" / "incidentes_muestra.csv")
    df = _normalizar(pd.read_csv(path), "INC")
    if NUEVOS_FILE.exists():
        df = pd.concat([df, _normalizar(pd.read_csv(NUEVOS_FILE), "NUEVO")], ignore_index=True)
    return df


def _normalizar(df: pd.DataFrame, prefijo: str) -> pd.DataFrame:
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    df = df.rename(columns={"Data": "fecha", "Countries": "pais", "Local": "planta", "Industry Sector": "sector",
                            "Accident Level": "nivel_real", "Potential Accident Level": "nivel_potencial",
                            "Genre": "genero", "Employee or Third Party": "tipo_trabajador",
                            "Employee ou Terceiro": "tipo_trabajador",
                            "Critical Risk": "riesgo_critico", "Description": "descripcion"})
    df = df.drop(columns=["genero"], errors="ignore")  # dato personal no necesario
    df["descripcion"] = df["descripcion"].fillna("").astype(str)
    df["riesgo_original"] = df["riesgo_critico"].fillna("Others").astype(str).str.strip()
    df["riesgo_critico"] = df["riesgo_original"].map(mapear_riesgo)
    for col in ("nivel_real", "nivel_potencial"):
        if col in df:
            df[col] = df[col].astype(str).str.strip()
    df["id"] = [f"{prefijo}-{i + 1:04d}" for i in range(len(df))]
    return df


def registrar_incidente_nuevo(tipo: str, descripcion: str, riesgo: str, nivel_potencial: str, area: str) -> str:
    """Agrega un casi-accidente o incidente reportado al cerrar una tarea. Devuelve su id."""
    nuevo = pd.DataFrame([{"Data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Countries": "Mina propia", "Local": area,
                           "Industry Sector": "Mining", "Accident Level": "I" if tipo == "Casi-accidente" else "II",
                           "Potential Accident Level": nivel_potencial, "Employee or Third Party": "Reporte de supervisor",
                           "Critical Risk": riesgo, "Description": f"[{tipo}] {descripcion}"}])
    previos = len(pd.read_csv(NUEVOS_FILE)) if NUEVOS_FILE.exists() else 0
    nuevo.to_csv(NUEVOS_FILE, mode="a", header=not NUEVOS_FILE.exists(), index=False, encoding="utf-8")
    return f"NUEVO-{previos + 1:04d}"


def buscar_incidentes_similares(df: pd.DataFrame, descripcion_tarea: str, k: int = 5) -> list[dict]:
    """Busca los incidentes históricos más parecidos a la tarea (similitud de texto TF-IDF)."""
    corpus = (df["riesgo_critico"] + " " + df["riesgo_original"] + " " + df["descripcion"]).tolist()
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    matriz = vec.fit_transform(corpus + [expandir_consulta(descripcion_tarea)])
    sims = cosine_similarity(matriz[-1], matriz[:-1]).ravel()
    top = sims.argsort()[::-1][:k]
    out = []
    for i in top:
        if sims[i] <= 0:
            continue
        fila = df.iloc[i]
        out.append({
            "id": fila["id"], "similitud": round(float(sims[i]), 2), "planta": str(fila.get("planta", "")),
            "sector": str(fila.get("sector", "")), "riesgo_critico": fila["riesgo_critico"],
            "riesgo_original": fila["riesgo_original"],
            "nivel_potencial": str(fila.get("nivel_potencial", "")), "descripcion": fila["descripcion"][:300],
        })
    return out


def estadisticas_riesgo(df: pd.DataFrame, riesgo_critico: str | None = None) -> dict:
    """Frecuencia y severidad potencial de los incidentes, opcionalmente filtrado por riesgo crítico."""
    sub = df[df["riesgo_critico"].str.contains(riesgo_critico, case=False, na=False, regex=False)] if riesgo_critico else df
    if sub.empty:
        return {"riesgo_critico": riesgo_critico, "total": 0}
    niveles = sub["nivel_potencial"].map(NIVELES).dropna()
    return {
        "riesgo_critico": riesgo_critico or "todos", "total": int(len(sub)),
        "porcentaje_graves_IV_o_mas": round(float((niveles >= 4).mean() * 100), 1) if len(niveles) else 0.0,
        "por_nivel_potencial": sub["nivel_potencial"].value_counts().to_dict(),
    }


def calcular_nivel_riesgo(similares: list[dict]) -> dict:
    """Score de riesgo 0-100 a partir de la severidad potencial de los casos similares."""
    if not similares:
        return {"score": 20, "nivel": "BAJO", "base": "Sin incidentes similares en el historial"}
    pesos = sum(s["similitud"] for s in similares) or 1
    sev = sum(NIVELES.get(s["nivel_potencial"], 2) * s["similitud"] for s in similares) / pesos
    score = round(min(100, sev / 6 * 100))
    nivel = "CRÍTICO" if score >= 70 else "ALTO" if score >= 50 else "MEDIO" if score >= 30 else "BAJO"
    return {"score": score, "nivel": nivel, "base": f"Severidad potencial promedio {sev:.1f}/6 en {len(similares)} casos similares"}


def controles_base(riesgos: list[str]) -> list[dict]:
    """Devuelve los controles obligatorios del catálogo para los riesgos críticos detectados."""
    salida, vistos = [], set()
    for r in riesgos:
        clave = next((c for c in CONTROLES if c.lower() in r.lower() or r.lower() in c.lower()), "Otros")
        for ctrl in CONTROLES[clave]:
            if ctrl not in vistos:
                vistos.add(ctrl)
                salida.append({"control": ctrl, "riesgo": clave, "critico": clave != "Otros"})
    return salida


def registrar_auditoria(evento: str, detalle: dict, usuario: str = "sistema") -> None:
    """Guarda cada decisión con fecha, actor y motivo (trazabilidad)."""
    registro = {"fecha": datetime.now().isoformat(timespec="seconds"), "usuario": usuario, "evento": evento, "detalle": detalle}
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def leer_auditoria(n: int = 50) -> list[dict]:
    if not AUDIT_FILE.exists():
        return []
    lineas = AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()[-n:]
    return [json.loads(l) for l in reversed(lineas)]
