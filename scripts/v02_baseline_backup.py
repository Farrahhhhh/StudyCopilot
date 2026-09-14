from datetime import datetime
from pathlib import Path
import hashlib
import json
import sqlite3
import zipfile

root = Path(__file__).resolve().parents[1]
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
out = root / "test-results"
out.mkdir(exist_ok=True)
source = sqlite3.connect(f"file:{(root / 'data/study.db').as_posix()}?mode=ro", uri=True)
backup_dir = root / "data" / "backups"
backup_dir.mkdir(exist_ok=True)
backup = backup_dir / f"study-before-v02-{stamp}.db"
with sqlite3.connect(backup) as destination:
    source.backup(destination)
source.close()
with zipfile.ZipFile(out / f"v01-source-{stamp}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    # Git index is the exact staged V0.1 baseline; new V0.2 files are not included.
    import subprocess
    names = subprocess.check_output(["git", "-c", f"safe.directory={root.as_posix()}", "ls-files"], cwd=root).decode().splitlines()
    for name in names:
        content = subprocess.check_output(["git", "-c", f"safe.directory={root.as_posix()}", "show", f":{name}"], cwd=root)
        archive.writestr(name, content)
print(f"V0.1 SQLite backup: {backup}")
