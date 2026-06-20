from flask import Flask, render_template, jsonify
import pandas as pd

app = Flask(__name__)

ARCHIVO_EXCEL = "ESAN_PROGRAMAS.xlsx"


@app.route("/")
def inicio():

    df = pd.read_excel(ARCHIVO_EXCEL, sheet_name="BD")

    programas = []

    for i, fila in df.iterrows():

        programas.append({
            "id": i,
            "item": fila.iloc[0],
            "nombre": fila.iloc[1]
        })

    return render_template(
        "index.html",
        programas=programas
    )


@app.route("/programa/<int:id_programa>")
def programa(id_programa):

    df = pd.read_excel(ARCHIVO_EXCEL, sheet_name="BD")

    df_aforo = pd.read_excel(ARCHIVO_EXCEL, sheet_name="AFORO")
    aforo_dict = {}
    for _, fila_aforo in df_aforo.iterrows():
        aforo_dict[fila_aforo["Laboratorio"]] = {
            "capacidad": fila_aforo["Capacidad"],
            "piso":      str(fila_aforo["PISO"]).strip()      if pd.notna(fila_aforo["PISO"])     else "—",
            "edificio":  str(fila_aforo["EDIFICIO"]).strip()  if pd.notna(fila_aforo["EDIFICIO"]) else "—",
        }

    fila = df.iloc[id_programa]

    ambientes = []

    for columna in df.columns[5:]:

        valor = str(fila[columna]).strip().lower()

        if valor in ["si", "sí", "x", "1", "true", "ok", "instalado"]:

            if columna == "PODIOS":
                capacidad = "Variado"
                piso      = "—"
                edificio  = "—"
            elif columna in aforo_dict:
                capacidad = int(aforo_dict[columna]["capacidad"])
                piso      = aforo_dict[columna]["piso"]
                edificio  = aforo_dict[columna]["edificio"]
            else:
                capacidad = "—"
                piso      = "—"
                edificio  = "—"

            ambientes.append({
                "nombre":   str(columna),
                "aforo":    capacidad,
                "piso":     piso,
                "edificio": edificio,
            })

    cantidad_raw = str(fila.iloc[4]).strip()

    if cantidad_raw.lower() == "ilimitado":
        cantidad = "Ilimitado"
    else:
        try:
            cantidad = int(float(cantidad_raw))
        except (ValueError, TypeError):
            cantidad = 0

    return jsonify({
        "programa": str(fila.iloc[1]),
        "version": str(fila.iloc[2]),
        "licencia": str(fila.iloc[3]),
        "cantidad_licencias": cantidad,
        "ambientes": ambientes
    })


@app.route("/laboratorio/<nombre_lab>")
def laboratorio(nombre_lab):

    df = pd.read_excel(ARCHIVO_EXCEL, sheet_name="BD")

    # Buscar la columna exacta que coincide con el nombre del lab
    if nombre_lab not in df.columns:
        return jsonify({"laboratorio": nombre_lab, "programas": []})

    programas = []

    for _, fila in df.iterrows():
        valor = str(fila[nombre_lab]).strip().lower()
        if valor in ["si", "sí", "x", "1", "true", "ok", "instalado"]:
            programas.append({
                "item":   fila.iloc[0],
                "nombre": str(fila.iloc[1]),
            })

    return jsonify({
        "laboratorio": nombre_lab,
        "programas":   programas
    })


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8080,
        debug=True
    )
