import subprocess
import sys
from pathlib import Path

KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'
def set_autostart(enabled):
    if sys.platform!='win32': raise OSError('Автозапуск доступен только в Windows')
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,KEY) as key:
        if enabled:
            args=[sys.executable]
            if not getattr(sys,'frozen',False): args.append(str(Path(__file__).resolve().parents[1]/'main.py'))
            args.append('--minimized')
            winreg.SetValueEx(key,'WRST Gate',0,winreg.REG_SZ,subprocess.list2cmdline(args))
        else:
            try: winreg.DeleteValue(key,'WRST Gate')
            except FileNotFoundError: pass
