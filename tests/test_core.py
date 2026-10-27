import concurrent.futures
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock
import psutil
from storage.database import Database
from core.time_wallet import TimeWallet
from core.game_monitor import GameMonitor,canonical,validate_game
from core.task_engine import TaskEngine

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'test.db'
        self.db=Database(self.path); self.wallet=TimeWallet(self.db)
    def tearDown(self): self.db.close(); self.tmp.cleanup()
    def test_credit(self):
        self.assertTrue(self.wallet.reward('a',1,20)); self.assertEqual(self.wallet.milliseconds,1200000)
    def test_debit_clamps(self):
        self.wallet.reward('a',1,1); self.assertEqual(self.wallet.spend(70000),60000); self.assertEqual(self.wallet.milliseconds,0)
        with self.assertRaises(ValueError): self.wallet.spend(-1)
    def test_restart_persistence_and_no_offline_charge(self):
        self.wallet.reward('a',1,20); self.wallet.spend(1234); self.db.add_game('/game.exe'); self.db.set_setting('minutes',30)
        self.db.close(); self.db=Database(self.path); self.wallet=TimeWallet(self.db)
        monitor=GameMonitor(self.db,self.wallet,clock=lambda:99999,processes=lambda:[]); monitor.tick()
        self.assertEqual(self.wallet.milliseconds,1198766); self.assertEqual(self.db.games(),['/game.exe']); self.assertEqual(self.db.setting('minutes'),30)
    def test_duplicate_concurrent(self):
        with concurrent.futures.ThreadPoolExecutor(8) as executor:
            outcomes=list(executor.map(lambda _:self.wallet.reward('a',1,20),range(20)))
        self.assertEqual(sum(outcomes),1); self.assertEqual(self.wallet.milliseconds,1200000)
    def test_duplicate_across_connections(self):
        other=Database(self.path)
        try:
            self.wallet.reward('a',1,20); self.assertFalse(TimeWallet(other).reward('a',1,20))
        finally: other.close()
    def process(self,path,pid):
        p=Mock(); p.pid=pid; p.exe.return_value=path; return p
    def test_multiple_games_one_debit_and_stop(self):
        self.wallet.reward('a',1,20); self.db.add_game(canonical('/games/a.exe'))
        now=[0]; processes=[self.process('/games/a.exe',123),self.process('/games/a.exe',124)]
        monitor=GameMonitor(self.db,self.wallet,clock=lambda:now[0],processes=lambda:processes)
        monitor.tick(); now[0]=2; monitor.tick(); self.assertEqual(self.wallet.milliseconds,1198000)
        processes.clear(); now[0]=3; monitor.tick(); before=self.wallet.milliseconds
        now[0]=10; monitor.tick(); self.assertEqual(self.wallet.milliseconds,before)
    def test_zero_and_repeat_block_only_exact_path(self):
        self.db.add_game(canonical('/games/a.exe'))
        game=self.process('/games/a.exe',123); unrelated=self.process('/other/a.exe',124)
        monitor=GameMonitor(self.db,self.wallet,processes=lambda:[game,unrelated]); monitor.tick(); monitor.tick()
        self.assertEqual(game.terminate.call_count,2); unrelated.terminate.assert_not_called()
        self.wallet.reward('a',1,1); monitor.tick(); self.assertEqual(game.terminate.call_count,2)
    def test_disable_and_access_denied(self):
        game=self.process('/games/a.exe',123); game.exe.side_effect=psutil.AccessDenied(123)
        self.db.add_game(canonical('/games/a.exe')); monitor=GameMonitor(self.db,self.wallet,processes=lambda:[game])
        self.assertEqual(monitor.tick()['denied'],1)
        self.db.set_setting('enabled',False); monitor.tick(); game.terminate.assert_not_called()
    def test_warning_thresholds(self):
        self.wallet.reward('a',1,11); self.db.add_game(canonical('/games/a.exe')); now=[0]
        monitor=GameMonitor(self.db,self.wallet,clock=lambda:now[0],processes=lambda:[self.process('/games/a.exe',123)])
        monitor.tick(); now[0]=61; self.assertEqual(monitor.tick()['notices'],['Осталось 10 мин.'])
        now[0]=62; self.assertEqual(monitor.tick()['notices'],[])
    def test_task_bank_and_rounds(self):
        engine=TaskEngine(self.db,self.wallet,Path(__file__).parents[1]/'assets/tasks.json')
        self.assertEqual(len(engine.tasks),35); self.assertFalse(engine.new_round())
        for task in engine.tasks:
            self.assertEqual(engine.submit(task['id'],task['answer']),'correct')
            self.assertEqual(engine.submit(task['id'],task['answer']),'duplicate')
        self.assertIsNone(engine.current()); self.assertTrue(engine.new_round()); self.assertIsNotNone(engine.current())
    def test_answer_parser(self):
        self.assertTrue(TaskEngine.matches(' 0,2500001 ','0.25'))
        for value in ['nan','Infinity','__import__("os")','1/4','']:
            self.assertFalse(TaskEngine.matches(value,'0.25'))
    @unittest.skipUnless(os.name=='posix' and Path('/bin/sleep').exists(),'POSIX safe process integration')
    def test_real_safe_process_block(self):
        executable=Path(self.tmp.name)/'safe-game.exe'; shutil.copy2('/bin/sleep',executable)
        self.db.add_game(validate_game(str(executable)))
        child=subprocess.Popen([str(executable),'30'])
        try:
            # A unique copied executable ensures no other sleep process is targeted.
            monitor=GameMonitor(self.db,self.wallet,processes=lambda:[psutil.Process(child.pid)])
            monitor.tick(); child.wait(timeout=5); self.assertIsNotNone(child.returncode)
        finally:
            if child.poll() is None: child.kill(); child.wait()

if __name__=='__main__': unittest.main()
