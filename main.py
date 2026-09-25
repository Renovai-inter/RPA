import argparse
import sys

from rpa.config import carregar_config
from rpa.pipeline import executar


def main():
    parser = argparse.ArgumentParser(description="RPA de migração InterV1 (Aiven) -> pg_dbRenovai (Neon)")
    parser.add_argument("--dry-run", action="store_true", help="Executa toda a carga e desfaz no final, sem gravar no destino")
    argumentos = parser.parse_args()
    try:
        config = carregar_config(argumentos.dry_run)
    except RuntimeError as erro:
        print(f"Configuração inválida: {erro}")
        return 1
    try:
        relatorio = executar(config)
    except Exception:
        return 1
    return 2 if relatorio.tem_erros() else 0


if __name__ == "__main__":
    sys.exit(main())
