import logging
from datetime import datetime


def criar_logger(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("rpa_renovai")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formato = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
    arquivo = logging.FileHandler(pasta / f"rpa_{datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8")
    console = logging.StreamHandler()
    for handler in (arquivo, console):
        handler.setFormatter(formato)
        logger.addHandler(handler)
    return logger
