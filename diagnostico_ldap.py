"""
Script de diagnóstico LDAP — ejecutar manualmente para ver el error real.

Uso:
    python diagnostico_ldap.py

Te pedirá usuario y contraseña, e imprimirá el error EXACTO que devuelve
el Active Directory, en lugar de ocultarlo como hace auth_ldap.py normalmente.
"""

import getpass
from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import LDAPException

LDAP_SERVER = "PRCPDC03.esan.edu.pe"
DOMINIO_UPN = "esan.edu.pe"
DOMINIO_NETBIOS = "ESAN"
BASE_DN = "DC=esan,DC=edu,DC=pe"
LDAP_PORT = 389


def probar(usuario, password, formato_usuario):
    print(f"\n--- Probando formato: {formato_usuario} ---")
    try:
        server = Server(LDAP_SERVER, port=LDAP_PORT, get_info=ALL)
        conn = Connection(
            server,
            user=formato_usuario,
            password=password,
            auto_bind=True,
        )
        print("✅ ¡ÉXITO! Este formato funciona:", formato_usuario)
        conn.unbind()
        return True
    except LDAPException as e:
        print("❌ Falló. Error LDAP:", e)
        return False
    except Exception as e:
        print("❌ Falló. Error general:", type(e).__name__, "-", e)
        return False


if __name__ == "__main__":
    print(f"Servidor configurado: {LDAP_SERVER}")
    print(f"Intentando resolver el servidor antes de autenticar...\n")

    # Primero probamos solo la conexión al servidor (sin login)
    try:
        server = Server(LDAP_SERVER, port=LDAP_PORT, get_info=ALL)
        conn_anon = Connection(server)
        conn_anon.open()
        print("✅ Conexión TCP al servidor LDAP exitosa (sin autenticar).")
        conn_anon.unbind()
    except Exception as e:
        print("❌ NO se pudo conectar al servidor LDAP en absoluto.")
        print("   Error:", type(e).__name__, "-", e)
        print("\n   Esto indica un problema de RED, no de credenciales:")
        print("   - ¿Estás conectado a la red/VPN de ESAN?")
        print("   - ¿El firewall bloquea el puerto 389?")
        print("   - ¿El nombre del servidor es correcto?")
        exit(1)

    usuario = input("\nUsuario (sin dominio, ej. arojass): ").strip()
    password = getpass.getpass("Contraseña: ")

    upn = f"{usuario}@{DOMINIO_UPN}"
    netbios = f"{DOMINIO_NETBIOS}\\{usuario}"

    exito = probar(usuario, password, upn)
    if not exito:
        exito = probar(usuario, password, netbios)

    if not exito:
        print("\n--- Ningún formato funcionó. Revisa el mensaje de error de arriba. ---")
        print("Causas comunes:")
        print("  - invalidCredentials (data 52e) -> contraseña incorrecta")
        print("  - invalidCredentials (data 532) -> contraseña expirada")
        print("  - invalidCredentials (data 533) -> cuenta deshabilitada")
        print("  - invalidCredentials (data 701) -> cuenta expirada")
        print("  - invalidCredentials (data 773) -> debe cambiar contraseña")
