import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    origem_dsn: str
    destino_dsn: str
    dry_run: bool
    pasta_logs: Path
    pasta_relatorios: Path


def carregar_config(dry_run=False):
    load_dotenv(RAIZ / ".env")
    origem = os.getenv("ORIGEM_DSN", "").strip()
    destino = os.getenv("DESTINO_DSN", "").strip()
    if not origem or not destino:
        raise RuntimeError("Defina ORIGEM_DSN e DESTINO_DSN no arquivo .env")
    if origem == destino:
        raise RuntimeError("ORIGEM_DSN e DESTINO_DSN não podem apontar para o mesmo banco")
    simular = dry_run or os.getenv("DRY_RUN", "false").strip().lower() == "true"
    return Config(origem, destino, simular, RAIZ / "logs", RAIZ / "relatorios")
