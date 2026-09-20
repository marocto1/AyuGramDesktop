from pathlib import Path

def read_text(path, encoding="utf-8"): return Path(path).read_text(encoding=encoding)
def write_text(path, text, encoding="utf-8"):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding=encoding); return str(p)
def read_bytes(path): return Path(path).read_bytes()
def write_bytes(path, data):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data); return str(p)
def exists(path): return Path(path).exists()
def mkdir(path, parents=True, exist_ok=True):
    Path(path).mkdir(parents=parents, exist_ok=exist_ok); return str(path)
