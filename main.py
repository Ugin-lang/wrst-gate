import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

def data_dir():
    base=Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local'/'share'))
    return base/'WRST Gate'

def main():
    parser=argparse.ArgumentParser(description='WRST Gate')
    parser.add_argument('--disable-control',action='store_true',help='Отключить контроль и выйти (восстановление доступа)')
    parser.add_argument('--minimized',action='store_true')
    args=parser.parse_args()
    folder=data_dir(); folder.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,handlers=[RotatingFileHandler(folder/'errors.log',maxBytes=2000000,backupCount=3,encoding='utf-8')],format='%(asctime)s %(levelname)s %(name)s %(message)s')
    from storage.database import Database
    if args.disable_control:
        db=Database(folder/'gate.sqlite3'); db.set_setting('enabled',False); db.close(); print('Контроль отключён.'); return 0
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication,QMessageBox,QSystemTrayIcon
    app=QApplication(sys.argv); app.setApplicationName('WRST Gate'); app.setQuitOnLastWindowClosed(False)
    lock=QLockFile(str(folder/'app.lock'))
    if not lock.tryLock(100):
        QMessageBox.information(None,'WRST Gate','Приложение уже запущено. Откройте его через трей.'); return 0
    db=Database(folder/'gate.sqlite3')
    from core.time_wallet import TimeWallet
    from core.task_engine import TaskEngine
    from ui.window import Window
    window=None
    try:
        wallet=TimeWallet(db)
        window=Window(db,wallet,TaskEngine(db,wallet,Path(__file__).parent/'assets'/'tasks.json'))
        app.aboutToQuit.connect(window.shutdown)
        if not args.minimized or not QSystemTrayIcon.isSystemTrayAvailable(): window.show()
        return app.exec()
    finally:
        if window is not None: window.shutdown()
        db.close(); lock.unlock()

if __name__=='__main__':
    try: sys.exit(main())
    except Exception:
        logging.exception('Ошибка запуска WRST Gate')
        raise
