"""
Protecao simples para evitar multiplas instancias com o mesmo token.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import fcntl


def acquire_process_lock(lock_key: str):
    """
    Tenta adquirir lock exclusivo por chave.
    Retorna um file descriptor aberto quando consegue.
    Retorna None quando outro processo ja possui o lock.
    """
    key_hash = hashlib.sha1(lock_key.encode("utf-8")).hexdigest()[:16]
    lock_path = Path("/tmp") / f"morfel_bot_{key_hash}.lock"

    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        os.close(fd)
        return None
