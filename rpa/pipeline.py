from .carregador import Carregador
from .conexao import conectar_destino, conectar_origem
from .contexto import Contexto
from .etapas import cadastros, financeiro, operacoes, referencias
from .extrator import extrair
from .logger import criar_logger
from .relatorio import Relatorio
from .validador import contar_destino, verificar_integridade, verificar_schema

ETAPAS = (
    ("Status", referencias.carregar_status),
    ("Cargos", referencias.carregar_cargos),
    ("Tipos de rateio", referencias.carregar_tipos_rateio),
    ("Categorias e materiais", referencias.carregar_categorias_e_materiais),
    ("Cooperativas, endereços e perfis", cadastros.carregar_cooperativas),
    ("Empresas, endereços e perfis", cadastros.carregar_empresas),
    ("Compradores", cadastros.carregar_compradores),
    ("Interesses e favoritos", cadastros.carregar_interesses_e_favoritos),
    ("Telefones", cadastros.carregar_telefones),
    ("Usuários", cadastros.carregar_usuarios),
    ("Funcionários", cadastros.carregar_funcionarios),
    ("Equipes", cadastros.carregar_equipes),
    ("Rotas e endereços de rota", cadastros.carregar_rotas),
    ("Coletas", operacoes.carregar_coletas),
    ("Execuções de rota", operacoes.carregar_execucoes_rota),
    ("Triagens", operacoes.carregar_triagens),
    ("Estoques", operacoes.carregar_estoques),
    ("Pedidos, itens e negociações", operacoes.carregar_pedidos),
    ("Mensagens de negociação", operacoes.carregar_mensagens),
    ("Movimentações de estoque", operacoes.carregar_movimentacoes),
    ("Reconciliação de estoques", operacoes.reconciliar_estoques),
    ("Despesas e lançamentos", financeiro.carregar_despesas),
    ("Rateios", financeiro.carregar_rateios),
)


def executar(config):
    logger = criar_logger(config.pasta_logs)
    relatorio = Relatorio(logger)
    logger.info("Iniciando RPA Renovaí | sentido único: InterV1 (Aiven) -> pg_dbRenovai (Neon) | dry_run=%s", config.dry_run)
    destino = None
    try:
        origem = conectar_origem(config.origem_dsn)
        try:
            dados = extrair(origem, logger)
        finally:
            origem.close()
        relatorio.origem = {tabela: len(linhas) for tabela, linhas in dados.items()}

        destino = conectar_destino(config.destino_dsn)
        carga = Carregador(destino, relatorio)
        verificar_schema(carga)
        contexto = Contexto(dados, carga, relatorio, logger)
        for nome, etapa in ETAPAS:
            logger.info("Etapa: %s", nome)
            etapa(contexto)
        relatorio.destino = contar_destino(carga)
        verificar_integridade(contexto)

        if config.dry_run:
            destino.rollback()
            relatorio.status = "SIMULADO_SEM_GRAVACAO"
            logger.info("Dry-run concluído: todas as alterações foram desfeitas")
        else:
            destino.commit()
            relatorio.status = "CONCLUIDO_COM_ERROS" if relatorio.tem_erros() else "CONCLUIDO"
            logger.info("Carga confirmada no destino")
    except Exception as erro:
        if destino is not None and not destino.closed:
            destino.rollback()
        relatorio.status = "FALHOU"
        relatorio.falha = str(erro)
        logger.exception("Falha na execução: nenhuma alteração foi gravada no destino")
        raise
    finally:
        if destino is not None and not destino.closed:
            destino.close()
        caminho = relatorio.salvar(config.pasta_relatorios)
        logger.info(relatorio.resumo())
        logger.info("Relatório salvo em %s", caminho)
    return relatorio
