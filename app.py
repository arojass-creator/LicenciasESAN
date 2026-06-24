from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from functools import wraps
import pandas as pd

from auth_ldap import autenticar_usuario

app = Flask(__name__)

# Clave secreta para firmar la sesión (cámbiala por algo único y mantenla privada)
app.secret_key = "CAMBIA-ESTA-CLAVE-POR-ALGO-SECRETO-Y-UNICO"

ARCHIVO_EXCEL = "ESAN_PROGRAMAS.xlsx"


def login_requerido(vista):
    """Decorador: redirige a /login si no hay sesión activa."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return vista(*args, **kwargs)
    return envoltura


def admin_requerido(vista):
    """Decorador: solo permite el acceso si el rol de la sesión es 'admin'."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        if session.get("rol") != "admin":
            return redirect(url_for("inicio"))
        return vista(*args, **kwargs)
    return envoltura


def verificar_acceso(usuario):
    """
    Verifica si el usuario está en la hoja USUARIOS del Excel
    y tiene ACTIVO = SI.
    Retorna dict con datos del usuario o None si no tiene acceso.
    """
    try:
        df = pd.read_excel(ARCHIVO_EXCEL, sheet_name="USUARIOS")
        # Normalizar columnas por si acaso
        df.columns = [c.strip().upper() for c in df.columns]
        df["USUARIO"] = df["USUARIO"].astype(str).str.strip().str.lower()

        fila = df[df["USUARIO"] == usuario.strip().lower()]

        if fila.empty:
            return None

        fila = fila.iloc[0]
        activo = str(fila.get("ACTIVO", "NO")).strip().upper()

        if activo != "SI":
            return None

        return {
            "rol":    str(fila.get("ROL", "viewer")).strip().lower(),
            "nombre": str(fila.get("NOMBRE", usuario)).strip(),
        }
    except Exception:
        return None


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")

        datos_usuario = autenticar_usuario(usuario, password)

        if datos_usuario:
            # Verificar que el usuario esté autorizado en el Excel
            acceso = verificar_acceso(usuario)
            if not acceso:
                return render_template("login.html",
                    error="Tu usuario no tiene acceso autorizado a esta aplicación.")

            session["usuario"] = datos_usuario["usuario"]
            session["nombre"]  = acceso["nombre"] or datos_usuario["nombre"]
            session["correo"]  = datos_usuario["correo"]
            session["rol"]     = acceso["rol"]

            if acceso["rol"] == "admin":
                return redirect(url_for("admin_programas"))
            return redirect(url_for("inicio"))
        else:
            return render_template("login.html", error="Usuario o contraseña incorrectos.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_requerido
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
@login_requerido
def programa(id_programa):

    df = pd.read_excel(ARCHIVO_EXCEL, sheet_name="BD")

    df_aforo = pd.read_excel(ARCHIVO_EXCEL, sheet_name="AFORO")
    aforo_dict = {}
    tiene_tipo = "TIPO LABORATORIO" in df_aforo.columns
    for _, fila_aforo in df_aforo.iterrows():
        piso     = str(fila_aforo["PISO"]).strip()      if pd.notna(fila_aforo["PISO"])      else "—"
        edificio = str(fila_aforo["EDIFICIO"]).strip()  if pd.notna(fila_aforo["EDIFICIO"])  else "—"
        tipo     = str(fila_aforo["TIPO LABORATORIO"]).strip() if tiene_tipo and pd.notna(fila_aforo["TIPO LABORATORIO"]) else "—"
        ubicacion = f"Piso {piso} del Edificio {edificio}" if piso != "—" and edificio != "—" else "—"
        aforo_dict[fila_aforo["LABORATORIO"]] = {
            "capacidad": fila_aforo["CAPACIDAD"],
            "piso":      piso,
            "edificio":  edificio,
            "tipo":      tipo,
            "ubicacion": ubicacion,
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
                tipo      = "—"
                ubicacion = "—"
            elif columna in aforo_dict:
                capacidad = int(aforo_dict[columna]["capacidad"])
                piso      = aforo_dict[columna]["piso"]
                edificio  = aforo_dict[columna]["edificio"]
                tipo      = aforo_dict[columna]["tipo"]
                ubicacion = aforo_dict[columna]["ubicacion"]
            else:
                capacidad = "—"
                piso      = "—"
                edificio  = "—"
                tipo      = "—"
                ubicacion = "—"

            ambientes.append({
                "nombre":    str(columna),
                "aforo":     capacidad,
                "piso":      piso,
                "edificio":  edificio,
                "tipo":      tipo,
                "ubicacion": ubicacion,
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
@login_requerido
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


@app.route("/laboratorios")
@login_requerido
def laboratorios():
    """Devuelve la lista completa de laboratorios/ambientes con su
    tipo y aforo, para la pestaña 'Laboratorios' del panel izquierdo."""

    df_aforo = pd.read_excel(ARCHIVO_EXCEL, sheet_name="AFORO")

    tiene_tipo = "TIPO LABORATORIO" in df_aforo.columns

    labs = []

    for _, fila_aforo in df_aforo.iterrows():

        nombre = str(fila_aforo["LABORATORIO"]).strip()

        tipo = (
            str(fila_aforo["TIPO LABORATORIO"]).strip()
            if tiene_tipo and pd.notna(fila_aforo["TIPO LABORATORIO"])
            else "—"
        )

        try:
            aforo = int(fila_aforo["CAPACIDAD"])
        except (ValueError, TypeError):
            aforo = "—"

        labs.append({
            "nombre": nombre,
            "tipo":   tipo,
            "aforo":  aforo,
        })

    return jsonify(labs)


# ===========================================================================
# ADMINISTRACIÓN — MANTENIMIENTO DE PROGRAMAS (solo rol admin)
# ===========================================================================

def _nombres_laboratorios():
    """Lista de nombres de laboratorio (columnas de la hoja BD desde la 6ta)."""
    df = pd.read_excel(ARCHIVO_EXCEL, sheet_name="BD")
    return [str(c) for c in df.columns[5:]]


@app.route("/admin/programas")
@admin_requerido
def admin_programas():

    df = pd.read_excel(ARCHIVO_EXCEL, sheet_name="BD")

    programas = []
    for i, fila in df.iterrows():
        programas.append({
            "id":       i,
            "item":     fila.iloc[0],
            "nombre":   fila.iloc[1],
            "version":  fila.iloc[2],
            "licencia": fila.iloc[3],
            "cantidad": fila.iloc[4],
        })

    return render_template(
        "admin_programas.html",
        programas=programas,
        laboratorios=_nombres_laboratorios(),
    )


@app.route("/admin/programa/nuevo", methods=["GET", "POST"])
@admin_requerido
def admin_programa_nuevo():

    laboratorios = _nombres_laboratorios()

    if request.method == "POST":

        df = pd.read_excel(ARCHIVO_EXCEL, sheet_name="BD")

        nueva_fila = {
            "Item":                   len(df) + 1,
            "Nombre":                 request.form.get("nombre", "").strip(),
            "Version":                request.form.get("version", "").strip(),
            "Tipo de Licencia":       request.form.get("licencia", "").strip(),
            "Cantidad de licencias":  request.form.get("cantidad", "0").strip(),
        }

        labs_marcados = request.form.getlist("laboratorios")
        for lab in laboratorios:
            nueva_fila[lab] = "Si" if lab in labs_marcados else ""

        df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)

        with pd.ExcelWriter(ARCHIVO_EXCEL, engine="openpyxl", mode="a",
                             if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name="BD", index=False)

        return redirect(url_for("admin_programas"))

    return render_template(
        "admin_programa_form.html",
        programa=None,
        laboratorios=laboratorios,
        labs_actuales=[],
    )


@app.route("/admin/programa/<int:id_programa>/editar", methods=["GET", "POST"])
@admin_requerido
def admin_programa_editar(id_programa):

    df = pd.read_excel(ARCHIVO_EXCEL, sheet_name="BD")
    laboratorios = _nombres_laboratorios()

    if id_programa < 0 or id_programa >= len(df):
        return redirect(url_for("admin_programas"))

    if request.method == "POST":

        df.at[id_programa, "Nombre"]                = request.form.get("nombre", "").strip()
        df.at[id_programa, "Version"]                = request.form.get("version", "").strip()
        df.at[id_programa, "Tipo de Licencia"]       = request.form.get("licencia", "").strip()
        df.at[id_programa, "Cantidad de licencias"]  = request.form.get("cantidad", "0").strip()

        labs_marcados = request.form.getlist("laboratorios")
        for lab in laboratorios:
            df.at[id_programa, lab] = "Si" if lab in labs_marcados else ""

        with pd.ExcelWriter(ARCHIVO_EXCEL, engine="openpyxl", mode="a",
                             if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name="BD", index=False)

        return redirect(url_for("admin_programas"))

    fila = df.iloc[id_programa]

    programa_actual = {
        "id":       id_programa,
        "nombre":   fila.iloc[1],
        "version":  fila.iloc[2],
        "licencia": fila.iloc[3],
        "cantidad": fila.iloc[4],
    }

    labs_actuales = [
        lab for lab in laboratorios
        if str(fila[lab]).strip().lower() in ["si", "sí", "x", "1", "true", "ok", "instalado"]
    ]

    return render_template(
        "admin_programa_form.html",
        programa=programa_actual,
        laboratorios=laboratorios,
        labs_actuales=labs_actuales,
    )


@app.route("/admin/programa/<int:id_programa>/eliminar", methods=["POST"])
@admin_requerido
def admin_programa_eliminar(id_programa):

    df = pd.read_excel(ARCHIVO_EXCEL, sheet_name="BD")

    if 0 <= id_programa < len(df):
        df = df.drop(index=id_programa).reset_index(drop=True)
        df["Item"] = range(1, len(df) + 1)

        with pd.ExcelWriter(ARCHIVO_EXCEL, engine="openpyxl", mode="a",
                             if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name="BD", index=False)

    return redirect(url_for("admin_programas"))


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8080,
        debug=True
    )
