import logging
import math
import sys
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QTimer, Qt
from PySide6.QtGui import QIcon, QPainter, QColor, QPixmap
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
 QStackedWidget,QLineEdit,QListWidget,QFileDialog,QMessageBox,QSpinBox,QCheckBox,
 QSystemTrayIcon,QMenu)
from core.game_monitor import GameMonitor,validate_game
from core.autostart import set_autostart

def duration(ms):
    seconds=math.ceil(ms/1000)
    h,rest=divmod(seconds,3600); m,s=divmod(rest,60)
    return f'{h:02}:{m:02}:{s:02}'

def icon():
    pix=QPixmap(64,64); pix.fill(QColor('#171c2d'))
    painter=QPainter(pix); painter.setPen(QColor('#80ebc1'))
    font=painter.font(); font.setPixelSize(36); font.setBold(True); painter.setFont(font)
    painter.drawText(pix.rect(),Qt.AlignmentFlag.AlignCenter,'W'); painter.end()
    return QIcon(pix)

class MonitorThread(QThread):
    updated=Signal(dict)
    failed=Signal(str)
    def __init__(self,monitor): super().__init__(); self.monitor=monitor
    def run(self):
        try:
            while not self.isInterruptionRequested():
                self.updated.emit(self.monitor.tick())
                self.msleep(250)
        except Exception:
            logging.exception('Монитор остановлен')
            self.failed.emit('Контроль остановлен из-за ошибки. Перезапустите приложение. Подробности в журнале.')

class Window(QMainWindow):
    def __init__(self,db,wallet,engine):
        super().__init__(); self.db,self.wallet,self.engine=db,wallet,engine
        self.setWindowTitle('WRST Gate'); self.setWindowIcon(icon()); self.resize(840,650)
        self.setStyleSheet('''
        QWidget { background: #101522; color: #e8eef8; font: 16px "Segoe UI"; }
        QLabel { padding: 6px; } QPushButton { background: #26344a; border: 0; border-radius: 9px; padding: 12px 22px; }
        QPushButton:hover { background: #35516a; } QLineEdit, QListWidget, QSpinBox { background: #1a2435; border: 1px solid #364962; border-radius: 8px; padding: 12px; }
        QCheckBox { padding: 10px; }''')
        outer=QWidget(); layout=QVBoxLayout(outer); layout.setContentsMargins(28,24,28,24)
        header=QLabel('WRST  /  GATE'); header.setStyleSheet('color:#80ebc1; font-size:24px; font-weight:700;'); layout.addWidget(header)
        nav=QHBoxLayout(); layout.addLayout(nav)
        self.pages=QStackedWidget(); layout.addWidget(self.pages)
        for name in ('Главная','Решать задачи','Мои игры / Настройки'):
            i=nav.count(); b=QPushButton(name); b.clicked.connect(lambda checked=False,index=i:self.pages.setCurrentIndex(index)); nav.addWidget(b)
        home,hl=self.page(); self.balance=QLabel(); self.balance.setStyleSheet('font-size:64px; font-weight:700; color:#80ebc1;'); hl.addWidget(self.balance)
        self.status=QLabel(); hl.addWidget(self.status); self.stats=QLabel(); hl.addWidget(self.stats)
        self.session=QLabel('Сессия: 00:00:00'); hl.addWidget(self.session)
        self.warning=QLabel(); self.warning.setWordWrap(True); hl.addWidget(self.warning)
        hl.addStretch(); solve=QPushButton('Решать задачи  →'); solve.clicked.connect(lambda:self.pages.setCurrentIndex(1)); hl.addWidget(solve)
        task,tl=self.page(); self.topic=QLabel(); tl.addWidget(self.topic)
        self.statement=QLabel(); self.statement.setTextFormat(Qt.TextFormat.PlainText); self.statement.setWordWrap(True); self.statement.setStyleSheet('font-size:26px; padding:20px;'); tl.addWidget(self.statement)
        self.answer=QLineEdit(); self.answer.setPlaceholderText('Числовой ответ, например 0,25'); self.answer.setMaxLength(100); tl.addWidget(self.answer)
        self.check=QPushButton('Проверить'); self.check.clicked.connect(self.submit); self.answer.returnPressed.connect(self.submit); tl.addWidget(self.check)
        self.result=QLabel(); self.result.setWordWrap(True); tl.addWidget(self.result)
        self.restart=QPushButton('Начать новое прохождение'); self.restart.clicked.connect(self.new_round); tl.addWidget(self.restart); tl.addStretch()
        settings,sl=self.page(); sl.addWidget(QLabel('Контролируемые .exe — по полному пути'))
        self.games=QListWidget(); sl.addWidget(self.games)
        row=QHBoxLayout(); sl.addLayout(row)
        add=QPushButton('Добавить игру'); add.clicked.connect(self.add_game); row.addWidget(add)
        remove=QPushButton('Удалить выбранную'); remove.clicked.connect(self.remove_game); row.addWidget(remove)
        self.enabled=QCheckBox('Контроль игр включён'); self.enabled.setChecked(db.setting('enabled',True)); self.enabled.toggled.connect(lambda v:db.set_setting('enabled',v)); sl.addWidget(self.enabled)
        sl.addWidget(QLabel('Минут за правильный ответ (1–240)'))
        self.minutes=QSpinBox(); self.minutes.setRange(1,240); self.minutes.setValue(db.setting('minutes',20)); self.minutes.valueChanged.connect(lambda v:db.set_setting('minutes',v)); sl.addWidget(self.minutes)
        self.auto=QCheckBox('Запускать вместе с Windows'); self.auto.setChecked(db.setting('autostart',False)); self.auto.setEnabled(sys.platform=='win32'); self.auto.toggled.connect(self.autostart); sl.addWidget(self.auto)
        sl.addWidget(QLabel('Контроль можно отключить в любой момент. Выход доступен в трее.'))
        self.setCentralWidget(outer)
        self.tray=QSystemTrayIcon(icon(),self); self.tray.setToolTip('WRST Gate')
        menu=QMenu(self); menu.addAction('Открыть',self.show_window); menu.addAction('Отключить контроль',lambda:self.enabled.setChecked(False)); menu.addAction('Выход',self.exit_app)
        self.tray.setContextMenu(menu); self.tray.activated.connect(lambda reason:self.show_window() if reason==QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show(); self.refresh_games(); self.load_task()
        self.worker=MonitorThread(GameMonitor(db,wallet)); self.worker.updated.connect(self.update_status); self.worker.failed.connect(self.monitor_failed); self.worker.start()
        self.refresh=QTimer(self); self.refresh.timeout.connect(self.refresh_balance); self.refresh.start(500); self.refresh_balance()
    def page(self):
        w=QWidget(); l=QVBoxLayout(w); self.pages.addWidget(w); return w,l
    def refresh_balance(self):
        self.balance.setText(duration(self.wallet.milliseconds)); self.stats.setText(f'Решено задач: {self.db.count()}  ·  Прохождение {self.engine.round}')
        self.status.setText('Контроль отключён' if not self.db.setting('enabled',True) else ('Игры разрешены' if self.wallet.milliseconds else 'Нет игрового времени'))
    def update_status(self,state):
        self.session.setText(f"Сессия: {duration(state['session'])}  ·  Активно игр: {len(state['active'])}")
        self.warning.setText(f"Недоступно процессов: {state['denied']}. Контроль программ с повышенными правами может быть недоступен." if state['denied'] else '')
        for message in state['notices']: self.tray.showMessage('WRST Gate',message)
    def monitor_failed(self,message):
        self.enabled.setChecked(False); self.warning.setText(message); QMessageBox.warning(self,'Ошибка контроля',message)
    def load_task(self):
        self.task=self.engine.current(); done=self.task is None
        self.restart.setVisible(done); self.check.setEnabled(not done); self.answer.setEnabled(not done)
        self.topic.setText(f"{self.task['topic']}  ·  +{self.db.setting('minutes',20)} минут" if self.task else 'Прохождение завершено')
        self.statement.setText(self.task['text'] if self.task else 'Все 35 задач решены. Можно начать новое прохождение.'); self.answer.clear()
    def submit(self):
        if not self.task: return
        result=self.engine.submit(self.task['id'],self.answer.text())
        if result=='correct':
            self.result.setText(f"Верно! Начислено {self.db.setting('minutes',20)} минут."); self.load_task(); self.refresh_balance()
        elif result=='wrong': self.result.setText('Неверно. Попробуйте ещё раз — штрафа нет.')
        else: self.result.setText('Эта задача уже зачтена.'); self.load_task()
    def new_round(self): self.engine.new_round(); self.result.clear(); self.load_task()
    def refresh_games(self): self.games.clear(); self.games.addItems(self.db.games())
    def add_game(self):
        path,_=QFileDialog.getOpenFileName(self,'Выберите исполняемый файл игры','','Приложения (*.exe)')
        if path:
            try: self.db.add_game(validate_game(path)); self.refresh_games()
            except ValueError as e: QMessageBox.warning(self,'Не удалось добавить',str(e))
    def remove_game(self):
        item=self.games.currentItem()
        if item: self.db.remove_game(item.text()); self.refresh_games()
    def autostart(self,value):
        try: set_autostart(value); self.db.set_setting('autostart',value)
        except OSError as e:
            self.auto.blockSignals(True); self.auto.setChecked(not value); self.auto.blockSignals(False); QMessageBox.warning(self,'Автозапуск',str(e))
    def show_window(self): self.showNormal(); self.raise_(); self.activateWindow()
    def closeEvent(self,event):
        if QSystemTrayIcon.isSystemTrayAvailable(): self.hide(); event.ignore()
        else: self.exit_app(); event.accept()
    def exit_app(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()
    def shutdown(self):
        self.worker.requestInterruption(); self.worker.wait(); self.tray.hide()
