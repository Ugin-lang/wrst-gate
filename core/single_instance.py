import hashlib
import os
from PySide6.QtCore import QThread
from PySide6.QtNetwork import QLocalServer, QLocalSocket

class SingleInstance:
    def __init__(self, user_key):
        self.name='WRSTGate-'+hashlib.sha256(str(user_key).lower().encode()).hexdigest()[:24]
        self.server=QLocalServer()
        self.callback=None
        self.mutex=None
        self.server.newConnection.connect(self.activate)
    def start(self):
        primary=True
        if os.name=='nt':
            import ctypes
            from ctypes import wintypes
            self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            self.kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
            self.kernel.CreateMutexW.restype=wintypes.HANDLE
            self.kernel.CloseHandle.argtypes=[wintypes.HANDLE]
            self.mutex=self.kernel.CreateMutexW(None,False,'Local\\'+self.name)
            if not self.mutex: raise ctypes.WinError(ctypes.get_last_error())
            primary=ctypes.get_last_error()!=183
        if primary and self.server.listen(self.name): return True
        socket=QLocalSocket()
        connected=False
        for _ in range(50):
            socket.abort(); socket.connectToServer(self.name)
            if socket.waitForConnected(100):
                connected=True; break
            QThread.msleep(100)
        if not connected:
            raise RuntimeError('Не удалось связаться с работающим WRST Gate. Повторите запуск.')
        socket.disconnectFromServer()
        return False
    def activate(self):
        while self.server.hasPendingConnections():
            socket=self.server.nextPendingConnection()
            socket.disconnectFromServer(); socket.deleteLater()
            if self.callback: self.callback()
    def close(self):
        self.server.close()
        if self.mutex:
            self.kernel.CloseHandle(self.mutex); self.mutex=None
