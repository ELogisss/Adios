import sqlite3
from datetime import datetime
from pathlib import Path

import notifica_pendientes as np

np.DB = Path(__file__).parent / "mesa_partes.db"

DB_PATH = Path(__file__).with_name("mesa_partes.db")
ESTADOS = ["INGRESADO", "EN_REVISION", "OBSERVADO", "DERIVADO", "ATENDIDO", "ARCHIVADO"]


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def inicializar_db():
    with conectar() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS expedientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                fecha_ingreso TEXT NOT NULL,
                remitente TEXT NOT NULL,
                asunto TEXT NOT NULL,
                area TEXT NOT NULL,
                estado TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                estado_anterior TEXT,
                estado_nuevo TEXT NOT NULL,
                observacion TEXT,
                FOREIGN KEY (expediente_id) REFERENCES expedientes(id)
            );
            CREATE TABLE IF NOT EXISTS config (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            );
            """
        )

def set_hora(hora: str) -> None:
    with conectar() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config (clave, valor) VALUES ('hora_notif', ?)",
            (hora,),
        )
    np.configurar()

def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generar_codigo(conn):
    anio = datetime.now().year
    cur = conn.execute(
        "SELECT COUNT(*) AS n FROM expedientes WHERE codigo LIKE ?",
        (f"EXP-{anio}-%",),
    )
    n = cur.fetchone()["n"] + 1
    return f"EXP-{anio}-{n:04d}"


def elegir_estado(actual=None):
    print("\nEstados disponibles:")
    for i, e in enumerate(ESTADOS, 1):
        marca = " (actual)" if e == actual else ""
        print(f"  {i}. {e}{marca}")
    while True:
        op = input("Seleccione número de estado: ").strip()
        if op.isdigit() and 1 <= int(op) <= len(ESTADOS):
            return ESTADOS[int(op) - 1]
        print("Opción inválida.")


def registrar_expediente():
    print("\n--- Registrar expediente ---")
    remitente = input("Remitente: ").strip()
    asunto = input("Asunto: ").strip()
    area = input("Área responsable: ").strip()
    if not remitente or not asunto or not area:
        print("Remitente, asunto y área son obligatorios.")
        return

    with conectar() as conn:
        codigo = generar_codigo(conn)
        fecha = ahora()
        estado = "INGRESADO"
        cur = conn.execute(
            """INSERT INTO expedientes (codigo, fecha_ingreso, remitente, asunto, area, estado)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (codigo, fecha, remitente, asunto, area, estado),
        )
        exp_id = cur.lastrowid
        conn.execute(
            """INSERT INTO historial (expediente_id, fecha, estado_anterior, estado_nuevo, observacion)
               VALUES (?, ?, ?, ?, ?)""",
            (exp_id, fecha, None, estado, "Registro inicial"),
        )
    print(f"Expediente registrado: {codigo}")


def listar_expedientes(filtro_estado=None):
    query = "SELECT * FROM expedientes"
    params = ()
    titulo = "Todos los expedientes"
    if filtro_estado:
        query += " WHERE estado = ?"
        params = (filtro_estado,)
        titulo = f"Expedientes en estado {filtro_estado}"
    query += " ORDER BY fecha_ingreso DESC"

    with conectar() as conn:
        filas = conn.execute(query, params).fetchall()

    print(f"\n--- {titulo} ({len(filas)}) ---")
    if not filas:
        print("Sin registros.")
        return
    for r in filas:
        print(
            f"[{r['codigo']}] {r['fecha_ingreso']} | {r['estado']}\n"
            f"  Remitente: {r['remitente']} | Área: {r['area']}\n"
            f"  Asunto: {r['asunto']}"
        )


def buscar_expediente():
    term = input("\nBuscar por código o remitente: ").strip()
    if not term:
        return
    like = f"%{term}%"
    with conectar() as conn:
        filas = conn.execute(
            """SELECT * FROM expedientes
               WHERE codigo LIKE ? OR remitente LIKE ?""",
            (like, like),
        ).fetchall()
    print(f"\n--- Resultados ({len(filas)}) ---")
    if not filas:
        print("Sin resultados.")
        return
    for r in filas:
        print(
            f"[{r['codigo']}] {r['fecha_ingreso']} | {r['estado']}\n"
            f"  Remitente: {r['remitente']} | Área: {r['area']}\n"
            f"  Asunto: {r['asunto']}"
        )


if __name__ == "__main__":
    inicializar_db()
    set_hora("09:00")
