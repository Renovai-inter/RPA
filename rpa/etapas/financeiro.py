from ..mapeamentos import CATEGORIAS_DESPESA, CONFIG_RATEIO, DESPESAS_FIXAS
from ..utils import agrupar, cortar, indexar, inicio_mes, para_datahora, uid


def carregar_despesas(ctx):
    periodos = indexar(ctx.origem("periodo_financeiro"), "id_periodo")
    lancamentos = {}
    for despesa in ctx.origem("despesa"):
        periodo = periodos.get(despesa["id_periodo"])
        cooperativa_id = ctx.mapa("cooperativa").get(periodo["id_cooperativa"]) if periodo else None
        if not cooperativa_id:
            ctx.relatorio.ignorar("despesas", f"Despesa {despesa['id_despesa']} sem período/cooperativa migrados")
            continue
        categoria = despesa["categoria"]
        nome = cortar(f"{CATEGORIAS_DESPESA.get(categoria, categoria)}: {despesa['descricao']}", 255)
        despesa_id = ctx.carga.upsert(
            "despesas",
            {
                "despesa_id": uid("despesa", cooperativa_id, categoria, nome.lower()),
                "cooperativa_id": cooperativa_id,
                "nome": nome,
                "tipo_despesa": "FIXA" if categoria in DESPESAS_FIXAS else "VARIAVEL",
                "esta_ativa": True,
            },
            "despesa_id",
            "despesa_id",
        )
        if not despesa_id:
            continue
        data = para_datahora(despesa["data"])
        grupo = lancamentos.setdefault((despesa_id, inicio_mes(data)), {"valor": 0, "data": data})
        grupo["valor"] += despesa["valor"]
        grupo["data"] = max(grupo["data"], data)

    for (despesa_id, mes), grupo in sorted(lancamentos.items(), key=lambda item: str(item[0])):
        ctx.carga.upsert(
            "lancamentos_despesas",
            {
                "lancamento_id": uid("lancamento", despesa_id, mes),
                "despesa_id": despesa_id,
                "valor": grupo["valor"],
                "mes_referencia": mes,
                "data_lancamento": grupo["data"],
            },
            ("despesa_id", "mes_referencia"),
            "lancamento_id",
        )


def carregar_rateios(ctx):
    distribuicoes = agrupar(ctx.origem("rateio_distribuicao"), "id_periodo")
    configuracoes = indexar(ctx.origem("configuracao_rateio"), "id_cooperativa")
    for periodo in ctx.origem("periodo_financeiro"):
        origem_id = periodo["id_periodo"]
        itens = distribuicoes.get(origem_id, [])
        if periodo["status"] != "FECHADO" and not itens:
            ctx.relatorio.ignorar("rateios", f"Período {origem_id} está ABERTO e sem distribuição: não há rateio para migrar")
            continue
        cooperativa_id = ctx.mapa("cooperativa").get(periodo["id_cooperativa"])
        gestor_id = ctx.mapa("gestor").get(periodo["id_cooperativa"])
        if not cooperativa_id or not gestor_id:
            ctx.relatorio.ignorar("rateios", f"Período {origem_id} sem cooperativa ou gestor migrados")
            continue
        configuracao = configuracoes.get(periodo["id_cooperativa"])
        tipo = CONFIG_RATEIO.get(configuracao["tipo"] if configuracao else None, "AUTOMATICO")
        mes = inicio_mes(periodo["data_inicio"])
        rateio_id = ctx.carga.upsert(
            "rateios",
            {
                "rateio_id": uid("rateio", cooperativa_id, mes),
                "cooperativa_id": cooperativa_id,
                "gestor_id": gestor_id,
                "tipo_rateio_id": ctx.mapa("tipo_rateio").get(tipo),
                "mes_referencia": mes,
                "data_rateio": para_datahora(periodo.get("data_fechamento") or periodo["data_fim"]),
            },
            ("cooperativa_id", "mes_referencia"),
            "rateio_id",
        )
        if not rateio_id:
            continue
        for item in itens:
            funcionario_id = ctx.mapa("funcionario").get(item["id_cooperado"])
            if not funcionario_id or not item["valor_recebido"] or item["valor_recebido"] <= 0:
                ctx.relatorio.ignorar("rateios_funcionarios", f"Período {origem_id} / cooperado {item['id_cooperado']}: cooperado não migrado ou valor zerado")
                continue
            ctx.carga.upsert(
                "rateios_funcionarios",
                {
                    "rateio_funcionario_id": uid("rateio_funcionario", rateio_id, funcionario_id),
                    "rateio_id": rateio_id,
                    "cooperado_id": funcionario_id,
                    "valor_rateio": item["valor_recebido"],
                },
                ("rateio_id", "cooperado_id"),
                "rateio_funcionario_id",
            )
