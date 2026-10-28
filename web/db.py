"""
Acceso a PostgreSQL (esquema en db/schema.sql).

La API se conecta con un rol de login (dental_api) sin privilegios propios y
miembro de dental_app y dental_plataforma. Cada transacción elige su rol:

  clinica(cid)  -> SET LOCAL ROLE dental_app + app.clinica_id (RLS activo)
  plataforma()  -> SET LOCAL ROLE dental_plataforma (altas, pagos, consola)

Inicialización (como superusuario):  python -m web.db init
"""
import contextlib
import os
import sys

import psycopg
from psycopg import conninfo, sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

AQUI = os.path.dirname(os.path.abspath(__file__))
ESQUEMA = os.path.join(os.path.dirname(AQUI), "db", "schema.sql")
DSN = os.environ.get("DATABASE_URL", "postgresql://dental_api:dental_api@localhost:5432/dental_home")
TZ = os.environ.get("DENTAL_TZ", "America/Lima")

_pool = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DSN, min_size=1, max_size=int(os.environ.get("DB_POOL_MAX", "10")), open=True,
            kwargs={"row_factory": dict_row, "options": f"-c TimeZone={TZ}", "autocommit": False},
        )
    return _pool


def usar_clinica(con, cid: int) -> None:
    con.execute("SET LOCAL ROLE dental_app")
    con.execute("SELECT set_config('app.clinica_id', %s, true)", (str(int(cid)),))


def usar_plataforma(con) -> None:
    con.execute("SET LOCAL ROLE dental_plataforma")


@contextlib.contextmanager
def transaccion():
    with pool().connection() as con:
        with con.transaction():
            yield con


@contextlib.contextmanager
def clinica(cid: int):
    with transaccion() as con:
        usar_clinica(con, cid)
        yield con


@contextlib.contextmanager
def plataforma():
    with transaccion() as con:
        usar_plataforma(con)
        yield con


@contextlib.contextmanager
def como_plataforma(con, cid: int):
    """Dentro de una transacción de clínica, ejecuta un bloque con el rol de plataforma."""
    usar_plataforma(con)
    try:
        yield con
    finally:
        usar_clinica(con, cid)


# ----------------------------------------------------------------------------
# Inicialización
# ----------------------------------------------------------------------------
def init(admin_dsn: str, api_password: str) -> None:
    info = conninfo.conninfo_to_dict(DSN)
    base, usuario_api = info.get("dbname", "dental_home"), info.get("user", "dental_api")
    with psycopg.connect(admin_dsn, autocommit=True) as con:
        if not con.execute("SELECT 1 FROM pg_database WHERE datname = %s", (base,)).fetchone():
            con.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(base)))
            print(f"Base de datos {base} creada.")
    destino = conninfo.make_conninfo(admin_dsn, dbname=base)
    with psycopg.connect(destino, autocommit=True) as con:
        if con.execute("SELECT to_regclass('public.planes')").fetchone()[0] is None:
            with open(ESQUEMA, encoding="utf-8") as f:
                con.execute(f.read())
            print("Esquema aplicado.")
        else:
            print("El esquema ya existía; no se modificó.")
        ident = sql.Identifier(usuario_api)
        if not con.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (usuario_api,)).fetchone():
            con.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT PASSWORD {}").format(
                ident, sql.Literal(api_password)))
            print(f"Rol de login {usuario_api} creado.")
        con.execute(sql.SQL("GRANT dental_app, dental_plataforma TO {}").format(ident))
        con.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(base), ident))


def crear_admin_plataforma(correo: str, clave: str) -> None:
    from web.seguridad import hashear
    with plataforma() as con:
        con.execute(
            "INSERT INTO usuarios_plataforma (correo, contrasena_hash) VALUES (%s, %s) "
            "ON CONFLICT (correo) DO UPDATE SET contrasena_hash = EXCLUDED.contrasena_hash, activo = true",
            (correo.strip().lower(), hashear(clave)),
        )
    print(f"Administrador de plataforma {correo} listo.")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "init":
        init(os.environ.get("DATABASE_ADMIN_URL", "postgresql:///postgres"),
             os.environ.get("DENTAL_API_PASSWORD", "dental_api"))
    elif len(sys.argv) >= 3 and sys.argv[1] == "admin-plataforma":
        import getpass
        clave = os.environ.get("DENTAL_PLATAFORMA_PASSWORD") or getpass.getpass("Contraseña: ")
        crear_admin_plataforma(sys.argv[2], clave)
    else:
        print("Uso: python -m web.db init | python -m web.db admin-plataforma <correo>")
        sys.exit(2)
