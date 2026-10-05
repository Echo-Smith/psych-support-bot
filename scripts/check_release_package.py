"""Verify the generated release archive and startup from its extracted source."""

import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def main() -> None:
    archive_path = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="psy-release-check-") as directory:
        destination = Path(directory)
        with tarfile.open(archive_path) as archive:
            names = archive.getnames()
            roots = {name.split("/")[0] for name in names}
            assert len(roots) == 1
            for name in names:
                parts = Path(name).parts
                assert ".env" not in parts
                assert not name.endswith((".db", ".sqlite", ".sqlite3", ".pyc"))
                assert not any(part.startswith("._") or "mirror-memory" in part for part in parts)
            archive.extractall(destination, filter="data")
        root = destination / roots.pop()
        for name in (
            "Dockerfile",
            "Dockerfile.server",
            "docker-compose.yml",
            "docker-compose.server.yml",
            "alembic.ini",
            "pyproject.toml",
            "uv.lock",
            ".env.example",
            "src/psych_support_bot/infra/db/migration_runner.py",
            "src/psych_support_bot/infra/db/migrations/env.py",
        ):
            assert (root / name).is_file(), name
        assert (root / "Dockerfile").read_bytes() == (root / "Dockerfile.server").read_bytes()
        env = dict(os.environ)
        env.update(
            {
                "DATABASE_URL": f"sqlite:///{destination / 'smoke.db'}",
                "AUTH_ENABLED": "false",
                "OPENAI_API_KEY": "",
                "DASHSCOPE_API_KEY": "",
                "JUDGE_API_KEY": "",
                "LANGFUSE_PUBLIC_KEY": "",
                "LANGFUSE_SECRET_KEY": "",
                "VOICE_STT_API_KEY": "",
                "VOICE_TTS_API_KEY": "",
                "PROFILE_LLM_EXTRACTION_ENABLED": "false",
                "SPECULATIVE_REPLY_ENABLED": "false",
            }
        )
        code = """
import sys
sys.path.insert(0, sys.argv[1])
from fastapi.testclient import TestClient
from psych_support_bot.app import app
with TestClient(app) as client:
    assert client.get('/health').status_code == 200
    assert client.get('/').status_code == 200
    assert client.get('/static/js/voice/stt.js').status_code == 200
    assert client.get('/static/icons/icon-192.png').status_code == 200
"""
        subprocess.run([sys.executable, "-I", "-c", code, str(root / "src")], cwd=root, env=env, check=True, timeout=45)
        print("release archive: required files, data exclusions, migrations and extracted startup passed")


if __name__ == "__main__":
    main()
