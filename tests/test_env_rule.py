"""Only the CLI reads the environment or .env (CLAUDE.md code principles; docs/components/README.md rule 5).

import-linter can't express this (everything imports `os`), so the source is searched instead.
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "sourcemap"
ENV_READ = re.compile(r"os\.environ|os\.getenv|getenv\(|\.env\b|load_dotenv")


def test_only_cli_reads_the_environment():
    offenders = [
        f"{p.relative_to(SRC)}:{i}"
        for p in SRC.rglob("*.py") if p.name != "cli.py"
        for i, line in enumerate(p.read_text().splitlines(), 1)
        if ENV_READ.search(line)
    ]
    assert offenders == []
