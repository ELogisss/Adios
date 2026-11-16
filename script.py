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
                estado TEXT NOT NULL,
                hora_notif TEXT NOT NULL DEFAULT '09:00'
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

            INSERT OR IGNORE INTO config (clave, valor)
            VALUES ('hora_notif', '09:00');
            """
        )
        columnas = {r["name"] for r in conn.execute("PRAGMA table_info(expedientes)")}
        if "hora_notif" not in columnas:
            conn.execute(
                "ALTER TABLE expedientes ADD COLUMN hora_notif TEXT NOT NULL DEFAULT '09:00'"
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


def hora_valida(hora: str) -> bool:
    try:
        hh, mm = (int(x) for x in hora.split(":"))
        return 0 <= hh < 24 and 0 <= mm < 60
    except (ValueError, TypeError):
        return False


def normalizar_hora(hora: str) -> str:
    hh, mm = (int(x) for x in hora.split(":"))
    return f"{hh:02d}:{mm:02d}"


def hora_default() -> str:
    with conectar() as conn:
        row = conn.execute(
            "SELECT valor FROM config WHERE clave='hora_notif'"
        ).fetchone()
    return row["valor"] if row else "09:00"


def registrar_expediente():
    print("\n--- Registrar expediente ---")
    remitente = input("Remitente: ").strip()
    asunto = input("Asunto: ").strip()
    area = input("Área responsable: ").strip()
    default = hora_default()
    hora = input(f"Hora de notificación (HH:MM) [{default}]: ").strip() or default
    if not remitente or not asunto or not area:
        print("Remitente, asunto y área son obligatorios.")
        return
    if not hora_valida(hora):
        print("Hora inválida. Usá HH:MM, por ejemplo 09:30.")
        return
    hora = normalizar_hora(hora)

    with conectar() as conn:
        codigo = generar_codigo(conn)
        fecha = ahora()
        estado = "INGRESADO"
        cur = conn.execute(
            """INSERT INTO expedientes (codigo, fecha_ingreso, remitente, asunto, area, estado, hora_notif)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (codigo, fecha, remitente, asunto, area, estado, hora),
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
            f"[{r['codigo']}] {r['fecha_ingreso']} | {r['estado']} | {r['hora_notif']}\n"
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
            f"[{r['codigo']}] {r['fecha_ingreso']} | {r['estado']} | {r['hora_notif']}\n"
            f"  Remitente: {r['remitente']} | Área: {r['area']}\n"
            f"  Asunto: {r['asunto']}"
        )


def cambiar_estado():
    print("\n--- Cambiar estado ---")
    codigo = input("Código del expediente: ").strip().upper()
    if not codigo:
        return

    with conectar() as conn:
        exp = conn.execute(
            "SELECT * FROM expedientes WHERE codigo = ?", (codigo,)
        ).fetchone()
        if not exp:
            print("No existe ese expediente.")
            return

        print(f"Estado actual: {exp['estado']}")
        nuevo = elegir_estado(exp["estado"])
        if nuevo == exp["estado"]:
            print("Sin cambios.")
            return

        observacion = input("Observación (opcional): ").strip() or None
        conn.execute(
            "UPDATE expedientes SET estado = ? WHERE id = ?",
            (nuevo, exp["id"]),
        )
        conn.execute(
            """INSERT INTO historial (expediente_id, fecha, estado_anterior, estado_nuevo, observacion)
               VALUES (?, ?, ?, ?, ?)""",
            (exp["id"], ahora(), exp["estado"], nuevo, observacion),
        )
    print(f"Expediente {codigo}: {exp['estado']} -> {nuevo}")


def ver_historial():
    print("\n--- Ver historial ---")
    codigo = input("Código del expediente: ").strip().upper()
    if not codigo:
        return

    with conectar() as conn:
        exp = conn.execute(
            "SELECT * FROM expedientes WHERE codigo = ?", (codigo,)
        ).fetchone()
        if not exp:
            print("No existe ese expediente.")
            return
        filas = conn.execute(
            """SELECT fecha, estado_anterior, estado_nuevo, observacion
               FROM historial WHERE expediente_id = ? ORDER BY id""",
            (exp["id"],),
        ).fetchall()

    print(f"\n--- Historial de {codigo} ---")
    if not filas:
        print("Sin movimientos.")
        return
    for h in filas:
        anterior = h["estado_anterior"] or "-"
        obs = f" | {h['observacion']}" if h["observacion"] else ""
        print(f"{h['fecha']} | {anterior} -> {h['estado_nuevo']}{obs}")


def cambiar_hora():
    with conectar() as conn:
        row = conn.execute(
            "SELECT valor FROM config WHERE clave='hora_notif'"
        ).fetchone()
    actual = row["valor"] if row else "09:00"

    print(f"\nHora por defecto para nuevos expedientes: {actual}")
    nueva = input("Nueva hora (HH:MM, Enter para cancelar): ").strip()
    if not nueva:
        return
    if not hora_valida(nueva):
        print("Hora inválida. Usá HH:MM, por ejemplo 09:30.")
        return

    nueva = normalizar_hora(nueva)
    set_hora(nueva)
    print(f"Hora por defecto actualizada a {nueva}.")


def cambiar_hora_expediente():
    print("\n--- Cambiar hora de un expediente ---")
    codigo = input("Código del expediente: ").strip().upper()
    if not codigo:
        return

    with conectar() as conn:
        exp = conn.execute(
            "SELECT * FROM expedientes WHERE codigo = ?", (codigo,)
        ).fetchone()
        if not exp:
            print("No existe ese expediente.")
            return

        print(f"Hora actual de {codigo}: {exp['hora_notif']}")
        nueva = input("Nueva hora (HH:MM, Enter para cancelar): ").strip()
        if not nueva:
            return
        if not hora_valida(nueva):
            print("Hora inválida. Usá HH:MM, por ejemplo 09:30.")
            return

        nueva = normalizar_hora(nueva)
        conn.execute(
            "UPDATE expedientes SET hora_notif = ? WHERE id = ?",
            (nueva, exp["id"]),
        )
    print(f"Hora de {codigo} actualizada a {nueva}.")


def menu():
    while True:
        print("\n=== Mesa de Partes ===")
        print("1. Registrar expediente")
        print("2. Listar expedientes")
        print("3. Buscar expediente")
        print("4. Cambiar estado")
        print("5. Ver historial")
        print("6. Cambiar hora por defecto")
        print("7. Cambiar hora de un expediente")
        print("0. Salir")
        opcion = input("Opción: ").strip()

        if opcion == "1":
            registrar_expediente()
        elif opcion == "2":
            listar_expedientes()
        elif opcion == "3":
            buscar_expediente()
        elif opcion == "4":
            cambiar_estado()
        elif opcion == "5":
            ver_historial()
        elif opcion == "6":
            cambiar_hora()
        elif opcion == "7":
            cambiar_hora_expediente()
        elif opcion == "0":
            print("Chau.")
            break
        else:
            print("Opción inválida.")


if __name__ == "__main__":
    inicializar_db()
    try:
        np.configurar()
    except Exception as exc:
        print(f"Aviso: no se pudo programar la notificación: {exc}")
    menu()
