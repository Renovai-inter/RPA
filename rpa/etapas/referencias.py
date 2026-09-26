from ..mapeamentos import (
    CARGOS,
    CATEGORIAS_MACRO,
    REF_COLETA,
    REF_NEGOCIACAO,
    REF_PEDIDO,
    REF_TRIAGEM,
    STATUS_COLETA,
    STATUS_NEGOCIACAO,
    STATUS_TRIAGEM,
    STATUS_VENDA,
    TIPOS_RATEIO,
)
from ..utils import cortar, normalizar, ordem_data, uid


def procurar(linhas, coluna, nome, **filtro):
    alvo = normalizar(nome)
    for linha in linhas:
        if normalizar(linha[coluna]) == alvo and all(linha.get(k) == v for k, v in filtro.items()):
            return linha
    return None


def status_id(ctx, referencia, nome):
    return ctx.mapa("status").get((referencia, nome))


def _status_necessarios():
    pares = {(REF_COLETA, nome) for nome in STATUS_COLETA.values()}
    pares.add((REF_TRIAGEM, STATUS_TRIAGEM))
    pares |= {(REF_PEDIDO, nome) for nome in STATUS_NEGOCIACAO.values()}
    pares |= {(REF_PEDIDO, nome) for nome in STATUS_VENDA.values()}
    pares |= {(REF_NEGOCIACAO, nome) for nome in STATUS_NEGOCIACAO.values()}
    return sorted(pares)


def carregar_status(ctx):
    existentes = ctx.carga.listar("status", ["status_id", "referencia", "status_atual"])
    for referencia, nome in _status_necessarios():
        linha = (
            procurar(existentes, "status_atual", nome, referencia=referencia)
            or procurar(existentes, "status_atual", nome, referencia=None)
            or procurar(existentes, "status_atual", nome)
        )
        if linha:
            ctx.relatorio.contar("status", "inalterados")
            ctx.mapa("status")[(referencia, nome)] = linha["status_id"]
            continue
        novo = ctx.carga.upsert(
            "status",
            {"status_id": uid("status", referencia, nome), "referencia": referencia, "status_atual": nome},
            "status_id",
            "status_id",
            atualizar=False,
        )
        if novo:
            ctx.relatorio.avisar("status", f"Status '{nome}' (referência {referencia}) não existia no destino e foi criado")
            existentes.append({"status_id": novo, "referencia": referencia, "status_atual": nome})
            ctx.mapa("status")[(referencia, nome)] = novo


def _obter_por_nome(ctx, tabela, chave, coluna, existentes, nome, extras=None):
    linha = procurar(existentes, coluna, nome)
    if linha:
        ctx.relatorio.contar(tabela, "inalterados")
        return linha[chave]
    novo = ctx.carga.upsert(
        tabela, {chave: uid(tabela, nome), coluna: nome, **(extras or {})}, chave, chave, atualizar=False
    )
    if novo:
        existentes.append({chave: novo, coluna: nome})
    return novo


def carregar_cargos(ctx):
    existentes = ctx.carga.listar("cargos", ["cargo_id", "cargo"])
    for codigo, nome in CARGOS.items():
        cargo_id = _obter_por_nome(ctx, "cargos", "cargo_id", "cargo", existentes, nome)
        if cargo_id:
            ctx.mapa("cargo")[codigo] = cargo_id


def carregar_tipos_rateio(ctx):
    existentes = ctx.carga.listar("tipos_rateios", ["tipo_rateio_id", "tipo_rateio"])
    for tipo, descricao in TIPOS_RATEIO.items():
        tipo_id = _obter_por_nome(
            ctx, "tipos_rateios", "tipo_rateio_id", "tipo_rateio", existentes, tipo, {"descricao": descricao}
        )
        if tipo_id:
            ctx.mapa("tipo_rateio")[tipo] = tipo_id


def _precos_por_material(ctx):
    precos = {}
    for negociacao in sorted(ctx.origem("negociacao"), key=lambda n: ordem_data(n["data_criacao"])):
        if negociacao["valor_kg_atual"]:
            precos[negociacao["id_material"]] = negociacao["valor_kg_atual"]
    vendas = [v for v in ctx.origem("venda") if v["status"] == "CONCLUIDA"]
    for venda in sorted(vendas, key=lambda v: ordem_data(v["data_venda"])):
        if venda["valor_kg"]:
            precos[venda["id_material"]] = venda["valor_kg"]
    return precos


def _categoria(ctx, existentes, nome, pai_id, id_novo):
    linha = procurar(existentes, "nome_categoria", nome, categoria_pai_id=pai_id)
    if linha:
        ctx.relatorio.contar("categorias_materiais", "inalterados")
        return linha["categoria_id"]
    novo = ctx.carga.upsert(
        "categorias_materiais",
        {"categoria_id": id_novo, "nome_categoria": nome, "categoria_pai_id": pai_id},
        "categoria_id",
        "categoria_id",
        atualizar=False,
    )
    if novo:
        existentes.append({"categoria_id": novo, "nome_categoria": nome, "categoria_pai_id": pai_id})
    return novo


def carregar_categorias_e_materiais(ctx):
    existentes = ctx.carga.listar("categorias_materiais", ["categoria_id", "categoria_pai_id", "nome_categoria"])
    materiais = ctx.origem("material")
    for codigo in sorted({material["categoria"] for material in materiais}):
        nome = CATEGORIAS_MACRO.get(codigo, str(codigo).title())
        macro_id = _categoria(ctx, existentes, nome, None, uid("categoria", nome))
        if not macro_id:
            continue
        ctx.mapa("categoria_macro")[codigo] = macro_id
        material_macro = ctx.carga.obter_ou_criar(
            "materiais",
            "material_id",
            {"categoria_id": macro_id, "cooperativa_id": None},
            {"material_id": uid("material_macro", codigo), "esta_disponivel": True},
        )
        if material_macro:
            ctx.mapa("material_macro")[codigo] = material_macro

    precos = _precos_por_material(ctx)
    disponiveis = {d["id_material"] for d in ctx.origem("material_disponivel") if (d["quantidade_kg"] or 0) > 0}
    for material in materiais:
        origem_id = material["id_material"]
        macro_id = ctx.mapa("categoria_macro").get(material["categoria"])
        if not macro_id:
            ctx.relatorio.ignorar("materiais", f"Material {origem_id} sem categoria macro correspondente")
            continue
        subcategoria_id = _categoria(ctx, existentes, cortar(material["nome"], 100), macro_id, uid("subcategoria", origem_id))
        if not subcategoria_id:
            continue
        ctx.mapa("subcategoria")[origem_id] = subcategoria_id
        material_id = ctx.carga.upsert(
            "materiais",
            {
                "material_id": uid("material", origem_id),
                "categoria_id": subcategoria_id,
                "cooperativa_id": None,
                "preco_sugerido": precos.get(origem_id),
                "esta_disponivel": origem_id in disponiveis,
            },
            "material_id",
            "material_id",
        )
        if material_id:
            ctx.mapa("material")[origem_id] = material_id
            ctx.mapa("material_categoria")[origem_id] = material["categoria"]
