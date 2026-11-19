import json
import os
import tempfile
import unicodedata

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH = True
except ImportError:
    AUTOREFRESH = False

st.set_page_config(page_title="Ahorcado en familia", page_icon="🪢", layout="centered")

JUGADORES = ["Isabel", "Mami", "Papi"]
ICONOS = {"Isabel": "👧", "Mami": "👩", "Papi": "👨"}
MAX_FALLOS = 6
ESTADO_PATH = os.path.join(os.path.dirname(__file__), "ahorcado_estado.json")

# 27 teclas sin tildes (Ñ incluida), en cuadrícula de 6 columnas
TECLADO = list("ABCDEFGHIJKLMNÑOPQRSTUVWXYZ")
COLUMNAS_TECLADO = 6


def sin_tilde(texto):
    """Quita tildes para poder adivinar p.ej. CAFÉ pulsando la E."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )

ESTADO_INICIAL = {
    "estado": "esperando",   # esperando | jugando | ganado | perdido
    "palabra": "",
    "proponente": "",
    "letras": [],            # letras ya intentadas
    "fallos": 0,
    "turno": "",             # a quién le toca adivinar ahora
    "quien_letra": {},       # letra -> jugador que la dijo
}

# CSS para que todo quepa en una pantalla de móvil, sin deslizar, y el teclado
# se vea siempre en cuadrícula de 6 columnas (Streamlit apila las columnas y
# añade huecos grandes entre bloques si no se fuerza lo contrario).
CSS_TECLADO = """
<style>
.block-container {
    padding-top: 0.6rem !important;
    padding-bottom: 0.6rem !important;
}
/* menos espacio entre TODOS los bloques de la página */
[data-testid="stVerticalBlock"] { gap: 0.25rem !important; }
div[data-testid="element-container"] { margin-bottom: 0 !important; }
h3 { margin: 0 0 0.2rem 0 !important; }

/* teclado: cuadrícula fija de 6 columnas, sin huecos entre filas ni teclas */
.st-key-teclado [data-testid="stVerticalBlock"] { gap: 0 !important; }
.st-key-teclado [data-testid="stHorizontalBlock"] {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 0.15rem !important;
    margin-bottom: 0.1rem !important;
}
.st-key-teclado [data-testid="column"] {
    width: calc(100% / 6) !important;
    flex: 0 0 calc(100% / 6) !important;
    min-width: 0 !important;
}
.st-key-teclado button {
    padding: 0 !important;
    font-size: 0.85rem !important;
    min-height: 1.7rem !important;
    height: 1.7rem !important;
    line-height: 1.7rem !important;
}
.st-key-teclado [data-testid="stMarkdownContainer"] p {
    font-size: 0.65rem !important;
    line-height: 1 !important;
    text-align: center;
    margin: 0 !important;
}
@media (max-width: 480px) {
  h3 { font-size: 1.15rem !important; }
  h2 { font-size: 1rem !important; }
}
</style>
"""


def leer_estado():
    if not os.path.exists(ESTADO_PATH):
        return dict(ESTADO_INICIAL)
    try:
        with open(ESTADO_PATH, "r", encoding="utf-8") as f:
            datos = json.load(f)
        base = dict(ESTADO_INICIAL)
        base.update(datos)
        return base
    except (json.JSONDecodeError, OSError):
        return dict(ESTADO_INICIAL)


def guardar_estado(estado):
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
        elif sin_tilde(c.upper()) in letras_set or not c.isalpha():
            out.append(c)
        else:
            out.append("_")
    return " ".join(out)


def completada(palabra, letras):
    letras_set = set(letras)
    return all((not c.isalpha()) or sin_tilde(c.upper()) in letras_set for c in palabra)


def adivinadores(proponente):
    return [j for j in JUGADORES if j != proponente]


# ---------- quién soy ----------
st.markdown(CSS_TECLADO, unsafe_allow_html=True)
st.markdown("### 🪢 Ahorcado en familia")

if "yo" not in st.session_state:
    st.session_state.yo = None

if st.session_state.yo is None:
    st.write("¿Quién eres?")
    cols = st.columns(3)
    for col, nombre in zip(cols, JUGADORES):
        if col.button(f"{ICONOS[nombre]} {nombre}", use_container_width=True):
            st.session_state.yo = nombre
            st.rerun()
    st.stop()

yo = st.session_state.yo

if AUTOREFRESH:
    st_autorefresh(interval=2000, key="autorefresh_ahorcado")

c1, c2 = st.columns([3, 1])
c1.caption(f"Eres **{ICONOS[yo]} {yo}**")
if c2.button("🔄 Salir", key="cambiar_jugador", use_container_width=True):
    st.session_state.yo = None
    st.rerun()
if not AUTOREFRESH:
    st.button("🔄 Actualizar", use_container_width=True)

estado = leer_estado()

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
                guesser_ini = adivinadores(yo)[0]
                guardar_estado({
                    "estado": "jugando",
                    "palabra": palabra.upper(),
                    "proponente": yo,
                    "letras": [],
                    "fallos": 0,
                    "turno": guesser_ini,
                    "quien_letra": {},
                })
                st.rerun()

# ---------- fase: jugando / ganado / perdido ----------
else:
    palabra = estado["palabra"]
    letras = estado["letras"]
    fallos = estado["fallos"]
    proponente = estado["proponente"]
    turno = estado["turno"]
    quien_letra = estado["quien_letra"]

    vidas = "❤️" * (MAX_FALLOS - fallos) + "💀" * fallos
    st.caption(f"Palabra de {ICONOS.get(proponente, '')} {proponente}  ·  {vidas}")
    st.markdown(f"## {mascara(palabra, letras)}")

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
        st.caption(f"Le toca adivinar a {ICONOS.get(turno, '')} **{turno}**")
        if st.button("❌ Cancelar esta partida", use_container_width=True):
            guardar_estado(dict(ESTADO_INICIAL))
            st.rerun()
    else:
        if yo == turno:
            st.caption("👉 Es tu turno")
        else:
            st.caption(f"Espera, le toca a {ICONOS.get(turno, '')} **{turno}**")

        with st.container(key="teclado"):
            filas = [TECLADO[i:i + COLUMNAS_TECLADO] for i in range(0, len(TECLADO), COLUMNAS_TECLADO)]
            for fila in filas:
                cols = st.columns(COLUMNAS_TECLADO)
                for col, letra in zip(cols, fila):
                    usada = letra in letras
                    no_es_mi_turno = yo != turno
                    with col:
                        st.button(
                            letra,
                            key=f"letra_{letra}",
                            disabled=usada or no_es_mi_turno,
                            use_container_width=True,
                        )
                        if letra in letras and letra in sin_tilde(palabra) and letra in quien_letra:
                            st.markdown(
                                f"<p style='text-align:center;margin:0'>{ICONOS.get(quien_letra[letra], '')}</p>",
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown("<p style='margin:0'>&nbsp;</p>", unsafe_allow_html=True)

        for letra in TECLADO:
            if st.session_state.get(f"letra_{letra}"):
                estado_actual = leer_estado()
                if (
                    estado_actual["estado"] == "jugando"
                    and letra not in estado_actual["letras"]
                    and yo != estado_actual["proponente"]
                    and yo == estado_actual["turno"]
                ):
                    estado_actual["letras"].append(letra)
                    estado_actual["quien_letra"][letra] = yo
                    if letra not in sin_tilde(estado_actual["palabra"]):
                        estado_actual["fallos"] += 1
                    dos = adivinadores(estado_actual["proponente"])
                    estado_actual["turno"] = dos[0] if estado_actual["turno"] == dos[1] else dos[1]
                    guardar_estado(estado_actual)
                st.rerun()
