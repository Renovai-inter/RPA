from .mapeamentos import COLUNAS_ITENS, TABELA_ITENS, TABELAS_DESTINO


def verificar_schema(carga):
    faltantes = [tabela for tabela in TABELAS_DESTINO if tabela not in carga.tabelas_existentes()]
    if faltantes:
        raise RuntimeError(
            "Tabelas ausentes no banco de destino: " + ", ".join(faltantes)
            + ". Execute o init.sql do pg_dbRenovai antes de rodar o RPA."
        )


def contar_destino(carga):
    return {tabela: carga.contar_registros(tabela) for tabela in TABELAS_DESTINO}


VERIFICACOES = {
    "estoques_negativos": "SELECT COUNT(*) AS total FROM estoques WHERE quantidade_kg < 0",
    "coletas_sem_triagem": """
        SELECT COUNT(*) AS total FROM coletas c
         WHERE NOT EXISTS (SELECT 1 FROM triagens t WHERE t.coleta_id = c.evento_id)
    """,
    "pedidos_sem_itens": f"""
        SELECT COUNT(*) AS total FROM pedidos p
         WHERE NOT EXISTS (SELECT 1 FROM {TABELA_ITENS} i WHERE i.{COLUNAS_ITENS["pedido"]} = p.pedido_id)
    """,
    "pedidos_sem_cooperativa": """
        SELECT COUNT(*) AS total FROM pedidos p
         WHERE NOT EXISTS (SELECT 1 FROM pedidos_cooperativas pc WHERE pc.pedido_id = p.pedido_id)
    """,
    "negociacoes_sem_itens": """
        SELECT COUNT(*) AS total FROM negociacoes n
         WHERE NOT EXISTS (SELECT 1 FROM negociacao_itens ni WHERE ni.negociacao_id = n.negociacao_id)
    """,
    "usuarios_com_cpf_provisorio": "SELECT COUNT(*) AS total FROM usuarios WHERE cpf LIKE 'MIG%'",
}


def verificar_integridade(ctx):
    resultados = {}
    for nome, consulta in VERIFICACOES.items():
        linhas = ctx.carga.protegido("verificacoes", lambda c=consulta: ctx.carga.consultar(c))
        resultados[nome] = linhas[0]["total"] if linhas else None
    for chave, esperado in ctx.ids.get("estoque_alvo", {}).items():
        estoque_id = ctx.mapa("estoque").get(chave)
        atual = ctx.carga.buscar("estoques", "quantidade_kg", {"estoque_id": estoque_id}) if estoque_id else None
        if atual is None or atual != esperado:
            ctx.relatorio.avisar("estoques", f"Estoque {estoque_id} com saldo {atual} diferente do esperado {esperado}")
    ctx.relatorio.verificacoes = resultados
    for nome, total in resultados.items():
        ctx.logger.info("Verificação %s: %s", nome, total)
    return resultados
