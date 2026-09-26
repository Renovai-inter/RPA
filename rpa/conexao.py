import psycopg2
from psycopg2.extras import RealDictCursor


def conectar_origem(dsn):
    conexao = psycopg2.connect(
        dsn,
        cursor_factory=RealDictCursor,
        connect_timeout=20,
        application_name="rpa_renovai_leitura",
    )
    conexao.set_session(readonly=True, autocommit=False)
    return conexao


def conectar_destino(dsn):
    conexao = psycopg2.connect(
        dsn,
        cursor_factory=RealDictCursor,
        connect_timeout=20,
        application_name="rpa_renovai_carga",
    )
    conexao.autocommit = False
    return conexao
