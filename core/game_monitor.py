import logging
import os
import sys
import time
from pathlib import Path
import psutil

log=logging.getLogger(__name__)
def canonical(path): return os.path.normcase(os.path.realpath(path))
def validate_game(path):
    p=canonical(path)
    if not Path(p).is_file() or Path(p).suffix.lower()!='.exe':
        raise ValueError('Выберите существующий .exe файл игры')
    protected=[sys.executable]
    if getattr(sys,'frozen',False): protected.append(sys.executable)
    if p in {canonical(x) for x in protected}: raise ValueError('Нельзя контролировать само приложение или Python')
    win=os.environ.get('SystemRoot')
    if win and Path(canonical(win)) in Path(p).parents: raise ValueError('Системные программы нельзя добавлять')
    return p

class GameMonitor:
    def __init__(self,db,wallet,clock=time.monotonic,processes=None):
        self.db,self.wallet,self.clock=db,wallet,clock
        self.processes=processes or psutil.process_iter
        self.last=clock(); self.previous_active=False; self.session_ms=0; self.carry=0.0
    def tick(self):
        now=self.clock(); elapsed=max(0,now-self.last); self.last=now
        enabled=self.db.setting('enabled',True)
        before=self.wallet.milliseconds
        if enabled and self.previous_active:
            raw=elapsed*1000+self.carry; ms=int(raw); self.carry=raw-ms
            self.session_ms+=self.wallet.spend(ms)
        after=self.wallet.milliseconds
        notices=[f'Осталось {n} мин.' for n in (10,5,1) if before>n*60000>=after]
        paths=set(self.db.games()) if enabled else set()
        active=[]; denied=0
        for proc in self.processes():
            try:
                if proc.pid==os.getpid(): continue
                path=canonical(proc.exe())
                if path not in paths: continue
                # Повторная проверка перед terminate; psutil защищает от повторного использования PID.
                if after==0:
                    if canonical(proc.exe())==path: proc.terminate()
                else: active.append(Path(path).name)
            except psutil.AccessDenied:
                denied+=1
                log.debug('Нет доступа к PID %s',proc.pid)
            except (psutil.NoSuchProcess,psutil.ZombieProcess): pass
            except OSError: log.exception('Ошибка чтения процесса')
        self.previous_active=bool(active) and enabled
        return {'balance':after,'active':active,'session':self.session_ms,'notices':notices,'denied':denied}
