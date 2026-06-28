import base64
import ctypes
import hashlib
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import winreg

BUNDLE      = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
INSTALL_DIR = Path(os.environ['APPDATA']) / 'ClaudeMonitor'
MARKER      = INSTALL_DIR / '.installed'
LOCK_PORT   = 19876
_REG_KEY    = r'SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist'


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _ext_id(pem_path: Path) -> str:
    lines = [l.strip() for l in pem_path.read_text().splitlines()
             if l.strip() and not l.startswith('---')]
    der = base64.b64decode(''.join(lines))
    h = hashlib.sha256(der).digest()
    return ''.join(
        chr(ord('a') + ((b >> 4) & 0xf)) + chr(ord('a') + (b & 0xf))
        for b in h[:16]
    )


def _do_install():
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    crx_dst = INSTALL_DIR / 'claude_usage_bridge.crx'
    shutil.copy2(BUNDLE / 'chrome_extension.crx', crx_dst)

    ext_id  = _ext_id(BUNDLE / 'extension.pem')
    crx_uri = 'file:///' + str(crx_dst).replace('\\', '/')
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, _REG_KEY,
                            access=winreg.KEY_ALL_ACCESS) as k:
        winreg.SetValueEx(k, '1', 0, winreg.REG_SZ, f'{ext_id};{crx_uri}')

    exe_dst = INSTALL_DIR / 'ClaudeMonitor.exe'
    exe_src = Path(sys.executable)
    if exe_src.resolve() != exe_dst.resolve():
        shutil.copy2(exe_src, exe_dst)

    subprocess.run([
        'schtasks', '/create',
        '/tn', 'ClaudeUsageMonitor',
        '/tr', f'"{exe_dst}"',
        '/sc', 'ONLOGON',
        '/ru', os.environ['USERNAME'],
        '/rl', 'LIMITED', '/f',
    ], check=False, creationflags=0x08000000)

    MARKER.write_text(ext_id)

    subprocess.Popen([str(exe_dst)], creationflags=0x08000000)


if __name__ == '__main__':
    if '--install' in sys.argv:
        if _is_admin():
            _do_install()
        sys.exit(0)

    if getattr(sys, 'frozen', False) and not MARKER.exists():
        if _is_admin():
            _do_install()
            sys.exit(0)
        else:
            ctypes.windll.shell32.ShellExecuteW(
                None, 'runas', sys.executable, '--install', None, 1
            )
            sys.exit(0)

    _lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _lock.bind(('127.0.0.1', LOCK_PORT))
    except OSError:
        sys.exit(0)

    import server
    from tray import run_tray
    server.start()
    run_tray()
