from ..mapeamentos import (
    COLUNAS_ITENS,
    PRIORIDADE_EQUIPE_TRIAGEM,
    REF_COLETA,
    REF_NEGOCIACAO,
    REF_PEDIDO,
    REF_TRIAGEM,
    STATUS_COLETA,
    STATUS_NEGOCIACAO,
    STATUS_TRIAGEM,
    STATUS_VENDA,
    TABELA_ITENS,
    TIPOS_COLETA,
)
from ..utils import agrupar, cortar, indexar, moeda, ordem_data, para_datahora, uid
from .referencias import status_id


def _responsavel(ctx, coleta):
    return ctx.mapa("funcionario").get(coleta.get("id_cooperado_responsavel")) or ctx.mapa("gestor").get(coleta["id_cooperativa"])


def carregar_coletas(ctx):
    materiais = agrupar(ctx.origem("coleta_material"), "id_coleta")
    for coleta in ctx.origem("coleta"):
        origem_id = coleta["id_coleta"]
        peso = coleta["peso_total_kg"] or sum((m["quantidade_kg"] or 0) for m in materiais.get(origem_id, []))
        if not peso or peso <= 0:
            ctx.relatorio.ignorar("coletas", f"Coleta {origem_id} ({coleta['status']}) sem peso: coletas.quantidade_kg exige valor maior que zero")
            continue
        cooperado = _responsavel(ctx, coleta)
        if not cooperado:
            ctx.relatorio.ignorar("coletas", f"Coleta {origem_id} sem cooperado responsável migrado")
            continue
        tipo = TIPOS_COLETA.get(coleta["tipo"])
        data = para_datahora(coleta.get("data_fim") or coleta.get("data_inicio") or coleta.get("data_agendada"))
        linha = {
            "evento_id": uid("coleta", origem_id),
            "status_id": status_id(ctx, REF_COLETA, STATUS_COLETA.get(coleta["status"])),
            "cooperado_id": cooperado,
            "rota_id": ctx.mapa("rota").get(coleta.get("id_rota")) if tipo == "EXTERNA" else None,
            "tipo_coleta": tipo,
            "quantidade_kg": peso,
        }
        if data:
            linha["data_evento"] = data
        evento_id = ctx.carga.upsert("coletas", linha, "evento_id", "evento_id")
        if evento_id:
            ctx.mapa("coleta")[origem_id] = {
                "id": evento_id,
                "cooperativa": coleta["id_cooperativa"],
                "data": data,
                "status": coleta["status"],
            }


def carregar_execucoes_rota(ctx):
    enderecos = indexar(ctx.origem("endereco_rota"), "id_endereco")
    materiais = agrupar(ctx.origem("coleta_material"), "id_coleta")
    nomes_material = {m["id_material"]: m["nome"] for m in ctx.origem("material")}
    for coleta in ctx.origem("coleta"):
        if coleta["tipo"] != "COLETA_EXTERNA" or not coleta.get("id_rota"):
            continue
        origem_id = coleta["id_coleta"]
        rota_id = ctx.mapa("rota").get(coleta["id_rota"])
        motorista = _responsavel(ctx, coleta)
        if not rota_id or not motorista:
            ctx.relatorio.ignorar("rota_execucoes", f"Coleta {origem_id} sem rota ou motorista migrados")
            continue
        inicio = para_datahora(coleta.get("data_inicio"))
        fim = para_datahora(coleta.get("data_fim"))
        endereco = enderecos.get(coleta.get("id_endereco_rota"))
        concluida = coleta["status"] == "CONCLUIDA"
        execucao_id = ctx.carga.upsert(
            "rota_execucoes",
            {
                "execucao_id": uid("rota_execucao", origem_id),
                "rota_id": rota_id,
                "motorista_id": motorista,
                "status_final": coleta["status"],
                "total_paradas": 1 if endereco else 0,
                "paradas_concluidas": 1 if endereco and concluida else 0,
                "peso_estimado": None,
                "peso_coletado": coleta["peso_total_kg"],
                "tempo_total_minutos": int((fim - inicio).total_seconds() // 60) if inicio and fim else None,
                "data_inicio": inicio or para_datahora(coleta.get("data_agendada")),
                "data_finalizacao": fim,
            },
            "execucao_id",
            "execucao_id",
        )
        if not execucao_id or not endereco:
            continue
        observacoes = [endereco.get("observacoes"), coleta.get("observacoes")]
        if endereco.get("nome_responsavel"):
            observacoes.append(f"Responsável no local: {endereco['nome_responsavel']}")
        if endereco.get("telefone_contato"):
            observacoes.append(f"Contato: {endereco['telefone_contato']}")
        nomes = [nomes_material.get(m["id_material"], str(m["id_material"])) for m in materiais.get(origem_id, [])]
        ctx.carga.upsert(
            "rota_execucoes_paradas",
            {
                "parada_execucao_id": uid("rota_parada", origem_id, endereco["id_endereco"]),
                "execucao_id": execucao_id,
                "endereco": cortar(f"{endereco['nome_local']} - {endereco['endereco_completo']}", 255),
                "material": cortar(", ".join(nomes), 100),
                "peso_estimado": None,
                "peso_coletado": coleta["peso_total_kg"],
                "status": coleta["status"],
                "observacoes": " | ".join(o for o in observacoes if o) or None,
            },
            "parada_execucao_id",
            "parada_execucao_id",
        )


def _equipe_triagem(ctx, cooperativa):
    for atividade in PRIORIDADE_EQUIPE_TRIAGEM:
        equipe = ctx.mapa("equipe").get((cooperativa, atividade))
        if equipe:
            return equipe
    return None


def carregar_triagens(ctx):
    status_triagem = status_id(ctx, REF_TRIAGEM, STATUS_TRIAGEM)
    for item in ctx.origem("coleta_material"):
        coleta = ctx.mapa("coleta").get(item["id_coleta"])
        if not coleta:
            continue
        chave = f"coleta {item['id_coleta']} / material {item['id_material']}"
        if coleta["status"] != "CONCLUIDA":
            ctx.relatorio.ignorar("triagens", f"{chave}: coleta não concluída")
            continue
        if not item["quantidade_kg"] or item["quantidade_kg"] <= 0:
            ctx.relatorio.ignorar("triagens", f"{chave}: quantidade zerada")
            continue
        material_id = ctx.mapa("material").get(item["id_material"])
        equipe_id = _equipe_triagem(ctx, coleta["cooperativa"])
        if not material_id or not equipe_id:
            ctx.relatorio.ignorar("triagens", f"{chave}: material ou equipe não migrados")
            continue
        linha = {
            "evento_id": uid("triagem", item["id_coleta"], item["id_material"]),
            "status_id": status_triagem,
            "equipe_id": equipe_id,
            "coleta_id": coleta["id"],
            "material_id": material_id,
            "quantidade_kg": item["quantidade_kg"],
            "quantidade_rejeito_kg": 0,
        }
        if coleta["data"]:
            linha["data_evento"] = coleta["data"]
        triagem_id = ctx.carga.upsert("triagens", linha, "evento_id", "evento_id")
        if triagem_id:
            ctx.mapa("triagem")[(item["id_coleta"], item["id_material"])] = {
                "id": triagem_id,
                "cooperativa": coleta["cooperativa"],
                "material": item["id_material"],
                "quantidade": item["quantidade_kg"],
                "data": coleta["data"],
            }


def _chave_estoque(ctx, cooperativa_origem, material_origem):
    cooperativa_id = ctx.mapa("cooperativa").get(cooperativa_origem)
    categoria = ctx.mapa("material_categoria").get(material_origem)
    material_macro = ctx.mapa("material_macro").get(categoria)
    if not cooperativa_id or not material_macro:
        return None
    return cooperativa_id, material_macro


def _estoque(ctx, cooperativa_origem, material_origem):
    chave = _chave_estoque(ctx, cooperativa_origem, material_origem)
    return ctx.mapa("estoque").get(chave) if chave else None


def carregar_estoques(ctx):
    alvo = {}
    for disponivel in ctx.origem("material_disponivel"):
        chave = _chave_estoque(ctx, disponivel["id_cooperativa"], disponivel["id_material"])
        if not chave:
            ctx.relatorio.ignorar("estoques", f"Disponibilidade {disponivel['id_disponibilidade']} sem cooperativa ou material migrados")
            continue
        alvo[chave] = alvo.get(chave, 0) + (disponivel["quantidade_kg"] or 0)
    ctx.ids["estoque_alvo"] = alvo

    chaves = set(alvo)
    for triagem in ctx.mapa("triagem").values():
        chave = _chave_estoque(ctx, triagem["cooperativa"], triagem["material"])
        if chave:
            chaves.add(chave)
    for venda in ctx.origem("venda"):
        if venda["status"] == "CONCLUIDA":
            chave = _chave_estoque(ctx, venda["id_cooperativa"], venda["id_material"])
            if chave:
                chaves.add(chave)

    for chave in sorted(chaves):
        cooperativa_id, material_id = chave
        linha = {
            "estoque_id": uid("estoque", cooperativa_id, material_id),
            "cooperativa_id": cooperativa_id,
            "material_id": material_id,
        }
        if chave in alvo:
            linha["quantidade_kg"] = alvo[chave]
        estoque_id = ctx.carga.upsert(
            "estoques", linha, ("cooperativa_id", "material_id"), "estoque_id", atualizar=chave in alvo
        )
        if estoque_id:
            ctx.mapa("estoque")[chave] = estoque_id


def _gravar_pedido(ctx, pedido_id, empresa_id, data_pedido, data_conclusao, observacao):
    if data_pedido and data_conclusao and data_conclusao < data_pedido:
        data_conclusao = data_pedido
    linha = {
        "pedido_id": pedido_id,
        "empresa_id": empresa_id,
        "observacao": observacao,
        "data_conclusao": data_conclusao,
    }
    if data_pedido:
        linha["data_pedido"] = data_pedido
    return ctx.carga.upsert("pedidos", linha, "pedido_id", "pedido_id")


def _gravar_pedido_cooperativa(ctx, pedido_id, cooperativa_id, id_status):
    if not id_status:
        ctx.relatorio.ignorar("pedidos_cooperativas", f"Status não encontrado para o pedido {pedido_id}")
        return None
    return ctx.carga.upsert(
        "pedidos_cooperativas",
        {
            "pedido_cooperativa_id": uid("pedido_cooperativa", pedido_id, cooperativa_id),
            "pedido_id": pedido_id,
            "cooperativa_id": cooperativa_id,
            "status_id": id_status,
        },
        ("pedido_id", "cooperativa_id"),
        "pedido_cooperativa_id",
    )


def _gravar_item(ctx, item_id, pedido_id, material_id, quantidade, preco):
    colunas = COLUNAS_ITENS
    return ctx.carga.upsert(
        TABELA_ITENS,
        {
            colunas["id"]: item_id,
            colunas["pedido"]: pedido_id,
            colunas["material"]: material_id,
            colunas["quantidade"]: quantidade,
            colunas["preco"]: preco,
        },
        colunas["id"],
        colunas["id"],
    )


def _ultima_quantidade(propostas):
    ordenadas = sorted(propostas, key=lambda p: (ordem_data(p.get("data_proposta")), str(p["id_proposta"])))
    return next((p["quantidade_kg"] for p in reversed(ordenadas) if p["quantidade_kg"]), None)


def _texto(*partes):
    return " | ".join(str(parte) for parte in partes if parte) or None


def _gravar_negociacao(ctx, origem_id, negociacao, pedido_id, cooperativa_id, empresa_id, material_id, quantidade, conclusao):
    id_status = status_id(ctx, REF_NEGOCIACAO, STATUS_NEGOCIACAO.get(negociacao["status"]))
    if not id_status:
        ctx.relatorio.ignorar("negociacoes", f"Negociação {origem_id} sem status correspondente")
        return
    valor_total = negociacao.get("valor_total_atual")
    if valor_total is None and quantidade:
        valor_total = round(quantidade * negociacao["valor_kg_atual"], 2)
    linha = {
        "negociacao_id": uid("negociacao", origem_id),
        "pedido_id": pedido_id,
        "cooperativa_id": cooperativa_id,
        "empresa_id": empresa_id,
        "status_id": id_status,
        "valor_total": valor_total,
        "data_fechamento": conclusao,
    }
    if negociacao.get("data_criacao"):
        linha["data_inicio"] = para_datahora(negociacao["data_criacao"])
    negociacao_id = ctx.carga.upsert("negociacoes", linha, ("pedido_id", "cooperativa_id"), "negociacao_id")
    if not negociacao_id:
        return
    ctx.mapa("negociacao")[origem_id] = negociacao_id
    ctx.carga.upsert(
        "negociacao_itens",
        {
            "negociacao_item_id": uid("negociacao_item", negociacao_id, material_id),
            "negociacao_id": negociacao_id,
            "material_id": material_id,
            "quantidade_kg": quantidade,
            "preco_unitario": negociacao["valor_kg_atual"],
        },
        ("negociacao_id", "material_id"),
        "negociacao_item_id",
    )


def carregar_pedidos(ctx):
    vendas_por_negociacao = {
        v["id_negociacao"]: v for v in ctx.origem("venda") if v["id_negociacao"] and v["status"] == "CONCLUIDA"
    }
    propostas = agrupar(ctx.origem("proposta"), "id_negociacao")
    for negociacao in ctx.origem("negociacao"):
        origem_id = negociacao["id_negociacao"]
        empresa_id = ctx.mapa("empresa").get(negociacao["id_empresa"])
        cooperativa_id = ctx.mapa("cooperativa").get(negociacao["id_cooperativa"])
        material_id = ctx.mapa("material").get(negociacao["id_material"])
        if not empresa_id or not cooperativa_id or not material_id:
            ctx.relatorio.ignorar("pedidos", f"Negociação {origem_id} sem empresa, cooperativa ou material migrados")
            continue
        venda = vendas_por_negociacao.get(origem_id)
        conclusao = para_datahora(negociacao.get("data_conclusao") or (venda["data_venda"] if venda else None))
        observacao = _texto(
            f"Negociação InterV1 #{origem_id}",
            venda and venda.get("numero_documento") and f"Documento {venda['numero_documento']}",
            venda and venda.get("observacoes"),
        )
        pedido_id = _gravar_pedido(
            ctx, uid("pedido", "negociacao", origem_id), empresa_id,
            para_datahora(negociacao.get("data_criacao")), conclusao, observacao,
        )
        if not pedido_id:
            continue
        ctx.mapa("pedido_negociacao")[origem_id] = pedido_id
        nome_status = STATUS_NEGOCIACAO.get(negociacao["status"])
        _gravar_pedido_cooperativa(ctx, pedido_id, cooperativa_id, status_id(ctx, REF_PEDIDO, nome_status))
        quantidade = negociacao["quantidade_kg"] or _ultima_quantidade(propostas.get(origem_id, []))
        item_id = _gravar_item(
            ctx, uid("item", "negociacao", origem_id), pedido_id, material_id, quantidade, negociacao["valor_kg_atual"]
        )
        if item_id:
            ctx.mapa("item_negociacao")[origem_id] = item_id
        _gravar_negociacao(ctx, origem_id, negociacao, pedido_id, cooperativa_id, empresa_id, material_id, quantidade, conclusao)

    for venda in ctx.origem("venda"):
        origem_id = venda["id_venda"]
        negociacao = venda.get("id_negociacao")
        if negociacao and negociacao in ctx.mapa("item_negociacao"):
            ctx.mapa("item_venda")[origem_id] = ctx.mapa("item_negociacao")[negociacao]
            continue
        cooperativa_id = ctx.mapa("cooperativa").get(venda["id_cooperativa"])
        material_id = ctx.mapa("material").get(venda["id_material"])
        pedido_id = ctx.mapa("pedido_negociacao").get(negociacao)
        if not pedido_id:
            empresa_id = ctx.mapa("empresa_comprador").get(venda["id_comprador"])
            if not empresa_id or not cooperativa_id or not material_id:
                ctx.relatorio.ignorar("pedidos", f"Venda {origem_id} sem comprador/empresa, cooperativa ou material migrados")
                continue
            data = para_datahora(venda["data_venda"])
            observacao = _texto(
                f"Venda {(venda.get('origem') or 'MANUAL').lower()} InterV1 #{origem_id}",
                venda.get("numero_documento") and f"Documento {venda['numero_documento']}",
                venda.get("documento_url"),
                venda.get("observacoes"),
            )
            pedido_id = _gravar_pedido(
                ctx, uid("pedido", "venda", origem_id), empresa_id, data,
                data if venda["status"] == "CONCLUIDA" else None, observacao,
            )
            if not pedido_id:
                continue
            _gravar_pedido_cooperativa(ctx, pedido_id, cooperativa_id, status_id(ctx, REF_PEDIDO, STATUS_VENDA.get(venda["status"])))
        if not material_id:
            ctx.relatorio.ignorar(TABELA_ITENS, f"Venda {origem_id} sem material migrado")
            continue
        item_id = _gravar_item(ctx, uid("item", "venda", origem_id), pedido_id, material_id, venda["quantidade_kg"], venda["valor_kg"])
        if item_id:
            ctx.mapa("item_venda")[origem_id] = item_id


def carregar_mensagens(ctx):
    negociacoes = indexar(ctx.origem("negociacao"), "id_negociacao")
    propostas = sorted(
        ctx.origem("proposta"),
        key=lambda p: (str(p["id_negociacao"]), ordem_data(p.get("data_proposta")), str(p["id_proposta"])),
    )
    for proposta in propostas:
        negociacao = negociacoes.get(proposta["id_negociacao"])
        negociacao_id = ctx.mapa("negociacao").get(proposta["id_negociacao"])
        if not negociacao or not negociacao_id:
            ctx.relatorio.ignorar("negociacao_mensagens", f"Proposta {proposta['id_proposta']} sem negociação migrada")
            continue
        if proposta["autor"] == "COOPERATIVA":
            remetente = ctx.mapa("perfil_cooperativa").get(negociacao["id_cooperativa"])
        else:
            remetente = ctx.mapa("perfil_empresa").get(negociacao["id_empresa"])
        if not remetente:
            ctx.relatorio.ignorar("negociacao_mensagens", f"Proposta {proposta['id_proposta']} sem perfil do remetente ({proposta['autor']})")
            continue
        texto = f"Proposta: {moeda(proposta['valor_kg'])}/kg"
        if proposta.get("quantidade_kg"):
            texto += f" para {proposta['quantidade_kg']} kg"
        if proposta.get("observacoes"):
            texto += f". {proposta['observacoes']}"
        linha = {
            "mensagem_id": uid("mensagem", proposta["id_proposta"]),
            "negociacao_id": negociacao_id,
            "remetente_id": remetente,
            "mensagem": texto,
            "tipo_mensagem": "CONTRAPROPOSTA",
        }
        if proposta.get("data_proposta"):
            linha["data_envio"] = para_datahora(proposta["data_proposta"])
        ctx.carga.upsert("negociacao_mensagens", linha, "mensagem_id", "mensagem_id")


def _movimentar(ctx, movimentacao_id, estoque_id, quantidade, data, triagem_id=None, item_id=None):
    linha = {
        "movimentacao_id": movimentacao_id,
        "estoque_id": estoque_id,
        "triagem_id": triagem_id,
        "item_id": item_id,
        "quantidade_kg": quantidade,
    }
    if data:
        linha["data_movimentacao"] = data
    return ctx.carga.upsert("movimentacoes_estoques", linha, "movimentacao_id", "movimentacao_id", atualizar=False)


def carregar_movimentacoes(ctx):
    triagens = sorted(ctx.mapa("triagem").values(), key=lambda t: (ordem_data(t["data"]), t["id"]))
    for triagem in triagens:
        estoque_id = _estoque(ctx, triagem["cooperativa"], triagem["material"])
        if not estoque_id:
            ctx.relatorio.ignorar("movimentacoes_estoques", f"Triagem {triagem['id']} sem estoque correspondente")
            continue
        _movimentar(ctx, uid("movimentacao", "triagem", triagem["id"]), estoque_id, triagem["quantidade"], triagem["data"], triagem_id=triagem["id"])

    vendas = [v for v in ctx.origem("venda") if v["status"] == "CONCLUIDA"]
    for venda in sorted(vendas, key=lambda v: (ordem_data(v["data_venda"]), str(v["id_venda"]))):
        item_id = ctx.mapa("item_venda").get(venda["id_venda"])
        estoque_id = _estoque(ctx, venda["id_cooperativa"], venda["id_material"])
        if not item_id or not estoque_id:
            ctx.relatorio.ignorar("movimentacoes_estoques", f"Venda {venda['id_venda']} sem item ou estoque correspondente")
            continue
        movimentacao_id = uid("movimentacao", "venda", venda["id_venda"])
        if ctx.carga.buscar("movimentacoes_estoques", "movimentacao_id", {"movimentacao_id": movimentacao_id}):
            ctx.relatorio.contar("movimentacoes_estoques", "inalterados")
            continue
        saldo = ctx.carga.buscar("estoques", "quantidade_kg", {"estoque_id": estoque_id}) or 0
        if saldo < venda["quantidade_kg"]:
            ctx.relatorio.ignorar("movimentacoes_estoques", f"Venda {venda['id_venda']}: saldo {saldo} kg insuficiente para saída de {venda['quantidade_kg']} kg")
            continue
        _movimentar(ctx, movimentacao_id, estoque_id, -venda["quantidade_kg"], para_datahora(venda["data_venda"]), item_id=item_id)


def reconciliar_estoques(ctx):
    for chave, quantidade in ctx.ids.get("estoque_alvo", {}).items():
        estoque_id = ctx.mapa("estoque").get(chave)
        if not estoque_id:
            continue
        alterados = ctx.carga.atualizar("estoques", {"quantidade_kg": quantidade}, {"estoque_id": estoque_id})
        if alterados:
            ctx.relatorio.contar("estoques", "reconciliados", alterados)
