from psycopg2 import sql

TABELAS_ORIGEM = (
    "usuario",
    "cooperativa",
    "cooperado",
    "cooperado_atividade",
    "horario_funcionamento",
    "area_atuacao",
    "empresa_recicladora",
    "empresa_material_interesse",
    "alerta_interesse",
    "favorito",
    "assinatura",
    "material",
    "material_disponivel",
    "rota",
    "endereco_rota",
    "coleta",
    "coleta_material",
    "negociacao",
    "proposta",
    "comprador",
    "venda",
    "periodo_financeiro",
    "despesa",
    "configuracao_rateio",
    "rateio_distribuicao",
)


def extrair(conexao, logger):
    dados = {}
    with conexao.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
        )
        existentes = {linha["table_name"] for linha in cursor.fetchall()}
        for tabela in TABELAS_ORIGEM:
            if tabela not in existentes:
                logger.warning("Tabela %s não encontrada na origem, seguirá vazia", tabela)
                dados[tabela] = []
                continue
            cursor.execute(sql.SQL("SELECT * FROM {} ORDER BY 1").format(sql.Identifier(tabela)))
            dados[tabela] = [dict(linha) for linha in cursor.fetchall()]
            logger.info("Extraídos %s registros de %s", len(dados[tabela]), tabela)
    conexao.rollback()
    return dados
