"""
Módulo de autenticación contra Active Directory (LDAP) — Universidad ESAN.

Valida usuario/contraseña contra el controlador de dominio interno.
No requiere ninguna librería externa de Microsoft ni Azure: se conecta
directamente al AD vía LDAP simple usando el bind del propio usuario.
"""

from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
from ldap3.core.exceptions import LDAPException

# ---------------------------------------------------------------------------
# CONFIGURACIÓN — ajusta estos valores según tu entorno
# ---------------------------------------------------------------------------

# Controlador de dominio confirmado con flag LDAP activo (nltest)
LDAP_SERVER = "PRCPDC03.esan.edu.pe"

# Dominio NetBIOS / sufijo para el login (formato DOMINIO\usuario)
DOMINIO_NETBIOS = "ESAN"

# Dominio UPN (formato usuario@dominio), alternativa más moderna
DOMINIO_UPN = "esan.edu.pe"

# Base DN donde buscar usuarios (ajustar a la estructura real de tu AD)
# Ejemplo: "DC=esan,DC=edu,DC=pe"
BASE_DN = "DC=esan,DC=edu,DC=pe"

# Puerto: 389 = LDAP simple, 636 = LDAPS (con certificado, recomendado)
LDAP_PORT = 389
USE_SSL = False


def autenticar_usuario(usuario, password):
    """
    Intenta autenticar a un usuario contra el Active Directory.

    Parámetros
    ----------
    usuario : str
        Nombre de usuario (sin dominio), ej. "arojass"
    password : str
        Contraseña del usuario

    Retorna
    -------
    dict | None
        Si la autenticación es correcta, retorna un diccionario con
        datos básicos del usuario (nombre, correo). Si falla, retorna None.
    """

    if not usuario or not password:
        return None

    # Construir el UPN (usuario@dominio) — formato más confiable para bind
    upn = f"{usuario}@{DOMINIO_UPN}"

    try:
        server = Server(LDAP_SERVER, port=LDAP_PORT, use_ssl=USE_SSL, get_info=ALL)

        # El "bind" con las credenciales del propio usuario ES la validación.
        # Si el usuario/contraseña son incorrectos, ldap3 lanza una excepción
        # o el bind retorna False.
        conn = Connection(
            server,
            user=upn,
            password=password,
            auto_bind=True,
        )

        # Si llegamos aquí, las credenciales son válidas.
        # Buscamos datos adicionales del usuario (nombre completo, correo).
        conn.search(
            search_base=BASE_DN,
            search_filter=f"(userPrincipalName={upn})",
            search_scope=SUBTREE,
            attributes=["displayName", "mail", "sAMAccountName"],
        )

        nombre_completo = usuario
        correo = upn

        if conn.entries:
            entry = conn.entries[0]
            if "displayName" in entry and entry.displayName.value:
                nombre_completo = str(entry.displayName.value)
            if "mail" in entry and entry.mail.value:
                correo = str(entry.mail.value)

        conn.unbind()

        return {
            "usuario": usuario,
            "nombre": nombre_completo,
            "correo": correo,
        }

    except LDAPException:
        # Credenciales incorrectas o problema de conexión al AD
        return None
    except Exception:
        # Cualquier otro error inesperado (timeout, DNS, etc.)
        return None
