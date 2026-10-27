import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')

@unittest.skipUnless(importlib.util.find_spec('PySide6'),'PySide6 not installed')
class UITests(unittest.TestCase):
    def test_window_navigation_answer_settings_and_shutdown(self):
        from PySide6.QtWidgets import QApplication
        from storage.database import Database
        from core.time_wallet import TimeWallet
        from core.task_engine import TaskEngine
        from ui.window import Window
        app=QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            db=Database(Path(folder)/'gate.db'); wallet=TimeWallet(db)
            engine=TaskEngine(db,wallet,Path(__file__).parents[1]/'assets/tasks.json')
            window=Window(db,wallet,engine)
            try:
                window.show(); app.processEvents()
                for i in range(3):
                    window.pages.setCurrentIndex(i); app.processEvents()
                    self.assertEqual(window.pages.currentIndex(),i)
                window.pages.setCurrentIndex(1); window.answer.setText('wrong'); window.submit(); self.assertEqual(wallet.milliseconds,0)
                window.answer.setText(window.task['answer']); window.submit(); self.assertEqual(wallet.milliseconds,1200000)
                window.enabled.setChecked(False); self.assertFalse(db.setting('enabled'))
                window.minutes.setValue(30); self.assertEqual(db.setting('minutes'),30)
                app.processEvents()
                if os.environ.get('WRST_SCREENSHOT'):
                    for i in range(3):
                        window.pages.setCurrentIndex(i); app.processEvents(); window.grab().save(os.environ['WRST_SCREENSHOT']+str(i)+'.png')
            finally:
                window.shutdown(); window.hide(); db.close()
