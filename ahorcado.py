import json
import os
import random
import string
import tempfile
import time

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH = True
except ImportError:
    AUTOREFRESH = False

st.set_page_config(page_title="Ahorcado en familia", page_icon="🪢", layout="centered")

JUGADORES = ["Isabel", "Mami", "Papi"]
MAX_FALLOS = 6
ESTADO_PATH = os.path.join(os.path.dirname(__file__), "ahorcado_estado.json")

TECLADO = list("ABCDEFGHIJKLMNÑOPQRSTUVWXYZ") + ["Á", "É", "Í", "Ó", "Ú", "Ü"]

DIBUJO = [
    """
  +---+
  |   |
      |
      |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
      |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
  |   |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
 /|   |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
 /|\\  |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
 /|\\  |
 /    |
      |
=========""",
    """
  +---+
  |   |
  O   |
 /|\\  |
 / \\  |
      |
=========""",
]

ESTADO_INICIAL = {
    "estado": "esperando",   # esperando | jugando | ganado | perdido
    "palabra": "",
    "proponente": "",
    "letras": [],            # letras ya intentadas
    "fallos": 0,
}


def leer_estado():
    if not os.path.exists(ESTADO_PATH):
        return dict(ESTADO_INICIAL)
    try:
        with open(ESTADO_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(ESTADO_INICIAL)


def guardar_estado(estado):
    # escritura atómica para evitar que dos jugadores se pisen al guardar a la vez
    carpeta = os.path.dirname(ESTADO_PATH) or "."
    fd, tmp = tempfile.mkstemp(dir=carpeta)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False)
    os.replace(tmp, ESTADO_PATH)


def mascara(palabra, letras):
    letras_set = set(letras)
    out = []
    for c in palabra:
        if c == " ":
            out.append("  ")
        elif c.upper() in letras_set or not c.isalpha():
            out.append(c)
        else:
            out.append("_")
    return " ".join(out)


def completada(palabra, letras):
    letras_set = set(letras)
    return all((not c.isalpha()) or c.upper() in letras_set for c in palabra)


# ---------- quién soy ----------
st.title("🪢 Ahorcado en familia")

if "yo" not in st.session_state:
    st.session_state.yo = None

if st.session_state.yo is None:
    st.subheader("¿Quién eres?")
    cols = st.columns(3)
    for col, nombre in zip(cols, JUGADORES):
        if col.button(nombre, use_container_width=True):
            st.session_state.yo = nombre
            st.rerun()
    st.stop()

yo = st.session_state.yo
st.caption(f"Has entrado como **{yo}**  ·  [cambiar]")
if st.button("🔄 Cambiar de jugador", key="cambiar_jugador"):
    st.session_state.yo = None
    st.rerun()

if AUTOREFRESH:
    st_autorefresh(interval=2000, key="autorefresh_ahorcado")
else:
    st.button("🔄 Actualizar")

estado = leer_estado()

st.divider()

# ---------- fase: esperando palabra ----------
if estado["estado"] == "esperando":
    st.info("No hay ninguna partida en marcha. Cualquiera puede proponer una palabra nueva.")
    with st.form("form_palabra", clear_on_submit=True):
        palabra = st.text_input("Escribe la palabra o frase que tienen que adivinar los demás")
        enviar = st.form_submit_button("🎬 Empezar partida", type="primary")
    if enviar:
        palabra = palabra.strip()
        if not palabra or not any(c.isalpha() for c in palabra):
            st.warning("Escribe al menos una palabra con letras.")
        else:
            estado_actual = leer_estado()
            if estado_actual["estado"] != "esperando":
                st.warning("Justo ahora ha empezado otra partida. Espera a que termine.")
            else:
                guardar_estado({
                    "estado": "jugando",
                    "palabra": palabra.upper(),
                    "proponente": yo,
                    "letras": [],
                    "fallos": 0,
                })
                st.rerun()

# ---------- fase: jugando / ganado / perdido ----------
else:
    palabra = estado["palabra"]
    letras = estado["letras"]
    fallos = estado["fallos"]
    proponente = estado["proponente"]

    st.markdown(f"Palabra propuesta por **{proponente}**")
    st.code(DIBUJO[min(fallos, MAX_FALLOS)], language=None)
    st.markdown(f"## {mascara(palabra, letras)}")
    st.caption(f"Fallos: {fallos} / {MAX_FALLOS}" + (f"   ·   Letras probadas: {', '.join(letras)}" if letras else ""))

    if estado["estado"] == "jugando" and completada(palabra, letras):
        estado["estado"] = "ganado"
        guardar_estado(estado)
        st.rerun()
    elif estado["estado"] == "jugando" and fallos >= MAX_FALLOS:
        estado["estado"] = "perdido"
        guardar_estado(estado)
        st.rerun()

    if estado["estado"] == "ganado":
        st.success(f"🎉 ¡Habéis adivinado **{palabra}**!")
        if st.button("🔁 Nueva palabra", type="primary"):
            guardar_estado(dict(ESTADO_INICIAL))
            st.rerun()
    elif estado["estado"] == "perdido":
        st.error(f"💀 Se acabaron los intentos. La palabra era **{palabra}**.")
        if st.button("🔁 Nueva palabra", type="primary"):
            guardar_estado(dict(ESTADO_INICIAL))
            st.rerun()
    elif yo == proponente:
        st.info("Tú has puesto la palabra: espera a que los demás la adivinen.")
        if st.button("❌ Cancelar esta partida"):
            guardar_estado(dict(ESTADO_INICIAL))
            st.rerun()
    else:
        st.write("Elige una letra:")
        filas = [TECLADO[i:i + 7] for i in range(0, len(TECLADO), 7)]
        for fila in filas:
            cols = st.columns(len(fila))
            for col, letra in zip(cols, fila):
                usada = letra in letras
                if col.button(letra, key=f"letra_{letra}", disabled=usada, use_container_width=True):
                    estado_actual = leer_estado()
                    if estado_actual["estado"] == "jugando" and letra not in estado_actual["letras"]:
                        estado_actual["letras"].append(letra)
                        if letra not in estado_actual["palabra"].upper():
                            estado_actual["fallos"] += 1
                        guardar_estado(estado_actual)
                    st.rerun()
