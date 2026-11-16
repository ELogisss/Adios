import platform
import sqlite3
import subprocess
import sys
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


def _pendientes_db() -> list[str]:
    with sqlite3.connect(DB) as con:
        rows = con.execute(
            "SELECT titulo FROM tareas WHERE hecho=0 ORDER BY id"
        ).fetchall()
    return [r[0] for r in rows]


def notificar(titulo: str, mensaje: str) -> None:
    if platform.system() == "Windows":
        from winotify import Notification
        Notification(app_id="Pendientes", title=titulo,
                     msg=mensaje, duration="long").show()
    else:
        subprocess.run(
            ["notify-send", "-u", "normal", "-a", "Pendientes", titulo, mensaje],
            check=True,
        )


def avisar() -> None:
    pendientes = _pendientes_db()
    if not pendientes:
        notificar("Todo al día 🎉", "No tenés pendientes")
        return
    lista = "\n".join(f"• {t}" for t in pendientes[:MAX])
    if len(pendientes) > MAX:
        lista += f"\n…y {len(pendientes) - MAX} más"
    notificar(f"{len(pendientes)} pendiente(s)", lista)


def configurar() -> None:
    hora = _hora_db()
    try:
        hh, mm = (int(x) for x in hora.split(":"))
        assert 0 <= hh < 24 and 0 <= mm < 60
    except (ValueError, AssertionError):
        raise ValueError(f"Hora inválida en config['hora_notif']: {hora!r}")
    if platform.system() == "Windows":
        _programar_windows(hora)
    else:
        _programar_linux(hh, mm)


def _programar_windows(hora: str) -> None:
    cmd = (
        f'schtasks /Create /F /SC DAILY /ST {hora} /IT '
        f'/TN "Pendientes" '
        f'/TR "\\"{sys.executable}\\" \\"{Path(__file__).resolve()}\\""'
    )
    subprocess.run(cmd, shell=True, check=True)
    print(f"✔ Programado en el Programador de Tareas a las {hora}")


def _programar_linux(hh: int, mm: int) -> None:
    script = str(Path(__file__).resolve())
    nueva  = f"{mm} {hh} * * * DISPLAY=:0 {sys.executable} {script}"
    actual = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    lineas = [l for l in actual.splitlines() if script not in l]
    lineas.append(nueva)
    subprocess.run(["crontab", "-"], input="\n".join(lineas) + "\n",
                   text=True, check=True)
    print(f"✔ Programado en crontab: todos los días a las {hh:02d}:{mm:02d}")


if __name__ == "__main__":
    avisar() 
