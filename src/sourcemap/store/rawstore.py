"""Content-addressed, write-once store for raw fetches (docs/containers.md, R10).

The same bytes stored twice are one file. A file is never rewritten or deleted by the product.
"""

import hashlib
import os
import tempfile
from pathlib import Path


class RawStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def path_of(self, sha256: str) -> Path:
        return self.root / sha256[:2] / sha256[2:4] / sha256

    def put(self, data: bytes) -> str:
        """Store bytes; return their SHA-256. Existing content is left untouched."""
        h = hashlib.sha256(data).hexdigest()
        path = self.path_of(h)
        if path.exists():
            return h
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.chmod(tmp, 0o444)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
        return h

    def get(self, sha256: str) -> bytes:
        return self.path_of(sha256).read_bytes()
