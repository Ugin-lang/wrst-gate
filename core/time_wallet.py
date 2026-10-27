class TimeWallet:
    def __init__(self, db): self.db=db
    @property
    def milliseconds(self):
        with self.db.lock: return self.db.conn.execute('SELECT ms FROM wallet WHERE id=1').fetchone()[0]
    def reward(self,task,round_id,minutes):
        if not 1 <= minutes <= 240: raise ValueError('Недопустимая награда')
        with self.db.transaction() as c:
            inserted=c.execute('INSERT OR IGNORE INTO solved(round,task) VALUES(?,?)',(round_id,task)).rowcount
            if not inserted: return False
            amount=minutes*60000
            c.execute('UPDATE wallet SET ms=ms+? WHERE id=1',(amount,))
            c.execute('INSERT INTO ledger(delta_ms,reason) VALUES(?,?)',(amount,f'Задача {task}, круг {round_id}'))
        return True
    def spend(self,ms):
        if ms<0: raise ValueError('Отрицательное списание')
        with self.db.transaction() as c:
            amount=min(int(ms),c.execute('SELECT ms FROM wallet WHERE id=1').fetchone()[0])
            if amount:
                c.execute('UPDATE wallet SET ms=ms-? WHERE id=1',(amount,))
                c.execute('INSERT INTO ledger(delta_ms,reason) VALUES(?,?)',(-amount,'Игровая сессия'))
        return amount
