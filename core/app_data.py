import os
from pathlib import Path
import sqlite3

def data_dir():
    if os.name=='nt':
        return Path(os.environ.get('USERPROFILE',str(Path.home())))/'Documents'/'WRST Gate'
    return Path.home()/'.local'/'share'/'WRST Gate'

def migrate_data(destination=None, sources=None):
    folder=Path(destination) if destination is not None else data_dir()
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/'gate.sqlite3'
    if target.exists(): return
    if sources is None:
        local=Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local'/'share'))
        sources=[local/'WRST Gate'/'gate.sqlite3']
        if os.name=='nt':
            sources.extend((Path.home()/'AppData/Local/Packages').glob('OpenAI.Codex_*/LocalCache/Local/WRST Gate/gate.sqlite3'))
    backups=[]
    for index,path in enumerate(sources):
        path=Path(path)
        if not path.is_file(): continue
        source=sqlite3.connect(path)
        backup_path=folder/f'legacy-backup-{index}.sqlite3'
        backup=sqlite3.connect(backup_path)
        try:
            source.backup(backup)
            score=backup.execute('SELECT count(*),coalesce(max(created),\'\') FROM ledger').fetchone()
            backups.append((score,backup_path))
        finally: backup.close(); source.close()
    if not backups: return
    _,best=max(backups)
    temporary=folder/'migration.sqlite3'
    source=sqlite3.connect(best); output=sqlite3.connect(temporary)
    try:
        source.backup(output)
        for _,path in backups:
            other=sqlite3.connect(path)
            try: output.executemany('INSERT OR IGNORE INTO games VALUES(?)',other.execute('SELECT path FROM games').fetchall())
            finally: other.close()
        output.commit()
    finally: source.close(); output.close()
    temporary.replace(target)
