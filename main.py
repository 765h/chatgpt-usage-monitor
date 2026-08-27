import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

INSTALL_DIR = Path(os.environ['APPDATA']) / 'ChatGPTUsageMonitor'
MARKER      = INSTALL_DIR / '.installed'
_MUTEX_NAME = "Global\\ChatGPTUsageMonitorMutex"


def _do_install():
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    exe_dst = INSTALL_DIR / 'ChatGPTUsageMonitor.exe'
    exe_src = Path(sys.executable)
    if exe_src.resolve() != exe_dst.resolve():
        shutil.copy2(exe_src, exe_dst)

    subprocess.run([
        'schtasks', '/create',
        '/tn', 'ChatGPTUsageMonitor',
        '/tr', f'"{exe_dst}"',
        '/sc', 'ONLOGON',
        '/ru', os.environ['USERNAME'],
        '/rl', 'LIMITED', '/f',
    ], check=True, creationflags=0x08000000)

    MARKER.write_text('installed')

    subprocess.Popen([str(exe_dst)], creationflags=0x08000000)


if __name__ == '__main__':
    if '--install' in sys.argv:
        _do_install()
        sys.exit(0)

    if getattr(sys, 'frozen', False) and not MARKER.exists():
        _do_install()
        sys.exit(0)

    # OS が保持するミューテックスで重複起動を防ぐ（ソケットと異なりGCの影響を受けない）
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)

    import codex_usage
    from tray import run_tray
    codex_usage.start()
    run_tray()
