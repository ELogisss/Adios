"""
notifica_pendientes.py — Toast con los expedientes pendientes (SQLite).

Fuente de verdad: la DB sqlite del proyecto (expedientes.hora_notif y estado).
Uso desde el programa principal:
    import notifica_pendientes as np
    np.DB = Path("mesa_partes.db")
    np.configurar()   # asegura la tarea programada cada minuto
    np.avisar()       # notifica ahora todos los pendientes (opcional)
Uso como script (lo dispara cron / Programador de Tareas):
    python3 notifica_pendientes.py --check
"""
import os
import platform
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB   = BASE / "mesa_partes.db"
MAX  = 5


def _hora_db() -> str:
    with sqlite3.connect(DB) as con:
        row = con.execute(
            "SELECT valor FROM config WHERE clave='hora_notif'"
        ).fetchone()
    return row[0] if row else "09:00"


def _pendientes_db() -> list[tuple[str, str, str]]:
    with sqlite3.connect(DB) as con:
        rows = con.execute(
            """SELECT codigo, asunto, hora_notif
               FROM expedientes
               WHERE estado NOT IN ('ATENDIDO', 'ARCHIVADO')
                 AND hora_notif <> ''
               ORDER BY hora_notif, id"""
        ).fetchall()
    return rows


def _vencidas_db() -> list[tuple[str, str]]:
    hora = datetime.now().strftime("%H:%M")
    with sqlite3.connect(DB) as con:
        rows = con.execute(
            """SELECT codigo, asunto
               FROM expedientes
               WHERE estado NOT IN ('ATENDIDO', 'ARCHIVADO')
                 AND hora_notif <> ''
                 AND hora_notif = ?
               ORDER BY id""",
            (hora,),
        ).fetchall()
    return rows


def notificar(titulo: str, mensaje: str) -> None:
    if platform.system() == "Windows":
        from winotify import Notification
        Notification(app_id="Pendientes", title=titulo,
                     msg=mensaje, duration="long").show()
    else:
        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        env.setdefault(
            "DBUS_SESSION_BUS_ADDRESS",
            f"unix:path=/run/user/{os.getuid()}/bus",
        )
        subprocess.run(
            ["notify-send", "-u", "normal", "-a", "Pendientes", titulo, mensaje],
            check=True,
            env=env,
        )


def avisar() -> None:
    pendientes = _pendientes_db()
    if not pendientes:
        notificar("Todo al día 🎉", "No tenés pendientes")
        return
    lista = "\n".join(
        f"• {codigo} ({hora}): {asunto}"
        for codigo, asunto, hora in pendientes[:MAX]
    )
    if len(pendientes) > MAX:
        lista += f"\n…y {len(pendientes) - MAX} más"
    notificar(f"{len(pendientes)} pendiente(s)", lista)


def avisar_vencidas() -> None:
    pendientes = _vencidas_db()
    if not pendientes:
        return
    lista = "\n".join(
        f"• {codigo}: {asunto}"
        for codigo, asunto in pendientes[:MAX]
    )
    if len(pendientes) > MAX:
        lista += f"\n…y {len(pendientes) - MAX} más"
    notificar(f"{len(pendientes)} expediente(s) para hoy", lista)


def configurar() -> None:
    if platform.system() == "Windows":
        _programar_windows()
    else:
        _programar_linux()


def _programar_windows() -> None:
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    if pythonw.exists():
        exe = pythonw
    cmd = [
        "schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO", "1", "/IT",
        "/TN", "Pendientes",
        "/TR", f'"{exe}" "{Path(__file__).resolve()}" --check',
    ]
    subprocess.run(cmd, check=True)
    print("✔ Programado en el Programador de Tareas cada minuto")


def _programar_linux() -> None:
    script = str(Path(__file__).resolve())
    uid = os.getuid()
    display = os.environ.get("DISPLAY", ":0")
    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    dbus = os.environ.get(
        "DBUS_SESSION_BUS_ADDRESS",
        f"unix:path=/run/user/{uid}/bus",
    )
    nueva = (
        f"* * * * * DISPLAY={display} XDG_RUNTIME_DIR={runtime} "
        f"DBUS_SESSION_BUS_ADDRESS={dbus} {sys.executable} {script} --check"
    )
    actual = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    lineas = [l for l in actual.splitlines() if script not in l]
    lineas.append(nueva)
    subprocess.run(["crontab", "-"], input="\n".join(lineas) + "\n",
                   text=True, check=True)
    print("✔ Programado en crontab cada minuto")


if __name__ == "__main__":
    if "--check" in sys.argv:
        avisar_vencidas()
    else:
        avisar()
