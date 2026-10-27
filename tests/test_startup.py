import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from core.app_data import migrate_data
from storage.database import Database
from core.time_wallet import TimeWallet
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

class StartupTests(unittest.TestCase):
    def test_migration_merges_games_preserves_one_wallet_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); sources=[root/'old1.db',root/'old2.db']
            for i,path in enumerate(sources):
                db=Database(path)
                db.add_game(f'C:/Games/game{i}.exe')
                wallet=TimeWallet(db); wallet.reward('task',1,10)
                if i: wallet.spend(1234)
                db.close()
            target=root/'new'; migrate_data(target,sources)
            db=Database(target/'gate.sqlite3')
            try:
                self.assertEqual(len(db.games()),2)
                self.assertEqual(TimeWallet(db).milliseconds,598766)
                self.assertEqual(db.count(),1)
                self.assertEqual(len(list(target.glob('legacy-backup-*.sqlite3'))),2)
            finally: db.close()
            migrate_data(target,[])
            db=Database(target/'gate.sqlite3')
            self.assertEqual(TimeWallet(db).milliseconds,598766); db.close()
    def test_repeat_launch_activates_hidden_window_and_exits(self):
        from PySide6.QtWidgets import QApplication,QWidget
        from core.single_instance import SingleInstance
        app=QApplication.instance() or QApplication([])
        instance=SingleInstance(str(uuid.uuid4()))
        window=QWidget(); window.hide()
        try:
            self.assertTrue(instance.start())
            instance.callback=window.show
            code=('from PySide6.QtCore import QCoreApplication; '
                  'from core.single_instance import SingleInstance; '
                  'app=QCoreApplication([]); '
                  f'instance=SingleInstance({str(uuid.uuid4())!r})')
            # Pass the exact server name to exercise the second process path.
            code+='; instance.name='+repr(instance.name)+'; raise SystemExit(1 if instance.start() else 0)'
            child=subprocess.run([sys.executable,'-c',code],timeout=10,capture_output=True)
            self.assertEqual(child.returncode,0,child.stderr.decode(errors='replace'))
            for _ in range(10): app.processEvents()
            self.assertTrue(window.isVisible())
        finally: window.hide(); instance.close()
