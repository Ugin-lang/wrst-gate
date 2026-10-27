import json
from decimal import Decimal, DecimalException
from pathlib import Path

REWARD_MINUTES = 10

class TaskEngine:
    def __init__(self,db,wallet,bank):
        self.db,self.wallet=db,wallet
        self.tasks=json.loads(Path(bank).read_text(encoding='utf-8'))
        if len({t['id'] for t in self.tasks})!=len(self.tasks): raise ValueError('Повтор ID')
    @property
    def round(self): return self.db.setting('round',1)
    def current(self):
        solved=self.db.solved(self.round)
        return next((t for t in self.tasks if t['id'] not in solved),None)
    def new_round(self):
        if self.current() is not None: return False
        self.db.set_setting('round',self.round+1)
        return True
    @staticmethod
    def matches(answer, expected):
        # Только числа: никаких eval/sympify пользовательского ввода.
        if len(answer)>100: return False
        try:
            value=Decimal(answer.strip().replace(',','.'))
            target=Decimal(str(expected))
            return value.is_finite() and abs(value-target)<=Decimal('0.000001')
        except DecimalException: return False
    def submit(self,task_id,answer):
        task=next((t for t in self.tasks if t['id']==task_id),None)
        if task is None or not self.matches(answer,task['answer']): return 'wrong'
        return 'correct' if self.wallet.reward(task_id,self.round,REWARD_MINUTES) else 'duplicate'
