import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from core.app_data import data_dir, migrate_data

def main():
    parser=argparse.ArgumentParser(description='WRST Gate')
    parser.add_argument('--disable-control',action='store_true',help='Отключить контроль и выйти (восстановление доступа)')
    parser.add_argument('--minimized',action='store_true')
    args=parser.parse_args()
    folder=data_dir()
    folder.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,handlers=[RotatingFileHandler(folder/'errors.log',maxBytes=2000000,backupCount=3,encoding='utf-8')],format='%(asctime)s %(levelname)s %(name)s %(message)s')
    from storage.database import Database
    if args.disable_control:
        migrate_data()
        db=Database(folder/'gate.sqlite3'); db.set_setting('enabled',False); db.close(); print('Контроль отключён.'); return 0
    from PySide6.QtWidgets import QApplication,QSystemTrayIcon
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('WRST.Gate')
    app=QApplication(sys.argv); app.setApplicationName('WRST Gate'); app.setQuitOnLastWindowClosed(False)
    from core.single_instance import SingleInstance
    instance=SingleInstance(Path.home())
    if not instance.start():
        instance.close(); return 0
    migrate_data()
    db=Database(folder/'gate.sqlite3')
    from core.time_wallet import TimeWallet
    from core.task_engine import TaskEngine
    from ui.window import Window
    window=None
    try:
        wallet=TimeWallet(db)
        window=Window(db,wallet,TaskEngine(db,wallet,Path(__file__).parent/'assets'/'tasks.json'))
        instance.callback=window.show_window
        app.aboutToQuit.connect(window.shutdown)
        if not args.minimized or not QSystemTrayIcon.isSystemTrayAvailable(): window.show()
        return app.exec()
    finally:
        if window is not None: window.shutdown()
        db.close(); instance.close()

if __name__=='__main__':
    try: sys.exit(main())
    except Exception:
        logging.exception('Ошибка запуска WRST Gate')
        raise
