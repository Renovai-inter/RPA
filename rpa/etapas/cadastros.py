from ..mapeamentos import (
    ATIVIDADES,
    CONTATOS_PREFERENCIAIS,
    EQUIPE_GERAL,
    SEGMENTOS,
    STATUS_FUNCIONARIO,
    TIPO_ENDERECO_COLETA,
    TIPO_ENDERECO_PERFIL,
)
from ..utils import (
    agrupar,
    cortar,
    cpf_provisorio,
    para_datahora,
    resumir_horarios,
    separar_endereco,
    separar_telefone,
    uid,
)


def _endereco(ctx, chave, cep, texto, tipo, cidade=None):
    partes = separar_endereco(texto)
    return ctx.carga.upsert(
        "enderecos",
        {
            "endereco_id": uid("endereco", *chave),
            "cep": cortar(cep, 9),
            "logradouro": cortar(partes["logradouro"], 255),
            "numero": cortar(partes["numero"], 20),
            "complemento": cortar(partes["complemento"], 255),
            "bairro": None,
            "cidade": cortar(cidade or partes["cidade"], 100),
            "tipo": tipo,
        },
        "endereco_id",
        "endereco_id",
    )


def _perfil_existente(ctx, cnpj, email):
    colunas = ["perfil_id", "empresa_id", "cooperativa_id"]
    for coluna, valor in (("cnpj", cnpj), ("email", email)):
        if valor:
            linha = ctx.carga.buscar_linha("perfis", colunas, {coluna: valor})
            if linha:
                return linha
    return None


def _descricao_cooperativa(cooperativa, areas):
    partes = [cooperativa.get("descricao_institucional")]
    if cooperativa.get("nome_publico") and cooperativa["nome_publico"] != cooperativa["nome"]:
        partes.append(f"Nome público: {cooperativa['nome_publico']}")
    if areas:
        partes.append("Áreas de atuação: " + ", ".join(area["municipio_regiao"] for area in areas))
    if cooperativa.get("estado"):
        partes.append(f"UF: {cooperativa['estado']}")
    if cooperativa.get("link_whatsapp"):
        partes.append(f"WhatsApp: {cooperativa['link_whatsapp']}")
    return "\n".join(parte for parte in partes if parte) or None


def carregar_cooperativas(ctx):
    horarios = agrupar(ctx.origem("horario_funcionamento"), "id_cooperativa")
    areas = agrupar(ctx.origem("area_atuacao"), "id_cooperativa")
    for cooperativa in ctx.origem("cooperativa"):
        origem_id = cooperativa["id_cooperativa"]
        perfil_id = uid("perfil", "cooperativa", origem_id)
        existente = _perfil_existente(ctx, cooperativa["cnpj"], cooperativa["email_institucional"])
        if existente and existente["perfil_id"] != perfil_id:
            if existente["cooperativa_id"]:
                ctx.mapa("cooperativa")[origem_id] = existente["cooperativa_id"]
                ctx.mapa("perfil_cooperativa")[origem_id] = existente["perfil_id"]
                ctx.relatorio.avisar("cooperativas", f"Cooperativa {origem_id} já existia no destino (CNPJ/e-mail) e foi reutilizada sem alteração")
            else:
                ctx.relatorio.ignorar("cooperativas", f"Cooperativa {origem_id}: CNPJ/e-mail já pertence a uma empresa no destino")
            continue
        contato = cooperativa.get("canal_contato_preferencial")
        cooperativa_id = ctx.carga.upsert(
            "cooperativas",
            {
                "cooperativa_id": uid("cooperativa", origem_id),
                "nome": cortar(cooperativa["nome"], 255),
                "imagem_url": cooperativa.get("logo_url"),
                "descricao": _descricao_cooperativa(cooperativa, areas.get(origem_id, [])),
                "contato_preferencial": contato if contato in CONTATOS_PREFERENCIAIS else None,
                "horario_funcionamento": resumir_horarios(horarios.get(origem_id, [])),
            },
            "cooperativa_id",
            "cooperativa_id",
        )
        if not cooperativa_id:
            continue
        ctx.mapa("cooperativa")[origem_id] = cooperativa_id
        if not cooperativa["cnpj"]:
            ctx.relatorio.ignorar("perfis", f"Cooperativa {origem_id} sem CNPJ na origem: perfil não criado (cnpj é obrigatório)")
            continue
        endereco_id = _endereco(
            ctx, ("cooperativa", origem_id), cooperativa["cep"], cooperativa["endereco"],
            TIPO_ENDERECO_PERFIL, cooperativa["cidade"],
        )
        perfil = ctx.carga.upsert(
            "perfis",
            {
                "perfil_id": perfil_id,
                "empresa_id": None,
                "cooperativa_id": cooperativa_id,
                "endereco_id": endereco_id,
                "email": cortar(cooperativa["email_institucional"], 255),
                "cnpj": cortar(cooperativa["cnpj"], 18),
                "data_criacao": para_datahora(cooperativa.get("data_fundacao") or cooperativa.get("data_cadastro")),
                "esta_ativo": cooperativa.get("status", "ATIVA") == "ATIVA",
            },
            "perfil_id",
            "perfil_id",
        )
        if perfil:
            ctx.mapa("perfil_cooperativa")[origem_id] = perfil


def _descricao_empresa(empresa):
    segmento = SEGMENTOS.get(empresa["segmento_atuacao"], empresa["segmento_atuacao"])
    if empresa.get("segmento_outro"):
        segmento = f"{segmento}: {empresa['segmento_outro']}"
    partes = [f"Segmento de atuação: {segmento}"]
    if empresa.get("estado"):
        partes.append(f"UF: {empresa['estado']}")
    return "\n".join(partes)


def carregar_empresas(ctx):
    assinaturas = agrupar(ctx.origem("assinatura"), "id_empresa")
    for empresa in ctx.origem("empresa_recicladora"):
        origem_id = empresa["id_empresa"]
        perfil_id = uid("perfil", "empresa", origem_id)
        existente = _perfil_existente(ctx, empresa["cnpj"], empresa["email_institucional"])
        if existente and existente["perfil_id"] != perfil_id:
            if existente["empresa_id"]:
                ctx.mapa("empresa")[origem_id] = existente["empresa_id"]
                ctx.mapa("perfil_empresa")[origem_id] = existente["perfil_id"]
                ctx.relatorio.avisar("empresas", f"Empresa {origem_id} já existia no destino (CNPJ/e-mail) e foi reutilizada sem alteração")
            else:
                ctx.relatorio.ignorar("empresas", f"Empresa {origem_id}: CNPJ/e-mail já pertence a uma cooperativa no destino")
            continue
        empresa_id = ctx.carga.upsert(
            "empresas",
            {
                "empresa_id": uid("empresa", origem_id),
                "nome": cortar(empresa["nome"], 255),
                "descricao": _descricao_empresa(empresa),
            },
            "empresa_id",
            "empresa_id",
        )
        if not empresa_id:
            continue
        ctx.mapa("empresa")[origem_id] = empresa_id
        endereco_id = _endereco(
            ctx, ("empresa", origem_id), empresa["cep"], empresa["endereco"], TIPO_ENDERECO_PERFIL, empresa["cidade"]
        )
        lista_assinaturas = assinaturas.get(origem_id, [])
        ativa = not lista_assinaturas or any(a["status"] == "ATIVO" for a in lista_assinaturas)
        perfil = ctx.carga.upsert(
            "perfis",
            {
                "perfil_id": perfil_id,
                "empresa_id": empresa_id,
                "cooperativa_id": None,
                "endereco_id": endereco_id,
                "email": cortar(empresa["email_institucional"], 255),
                "cnpj": cortar(empresa["cnpj"], 18),
                "data_criacao": para_datahora(empresa.get("data_cadastro")),
                "esta_ativo": ativa,
            },
            "perfil_id",
            "perfil_id",
        )
        if perfil:
            ctx.mapa("perfil_empresa")[origem_id] = perfil


def carregar_compradores(ctx):
    nomes_cooperativa = {c["id_cooperativa"]: c["nome"] for c in ctx.origem("cooperativa")}
    for comprador in ctx.origem("comprador"):
        origem_id = comprador["id_comprador"]
        if comprador["id_empresa_recicladora"]:
            empresa_id = ctx.mapa("empresa").get(comprador["id_empresa_recicladora"])
            if empresa_id:
                ctx.mapa("empresa_comprador")[origem_id] = empresa_id
            else:
                ctx.relatorio.ignorar("empresas", f"Comprador {origem_id} aponta para empresa não migrada")
            continue
        partes = [f"Comprador externo cadastrado pela cooperativa {nomes_cooperativa.get(comprador['id_cooperativa'], comprador['id_cooperativa'])}"]
        rotulos = (
            ("nome_responsavel", "Responsável"),
            ("email", "E-mail"),
            ("whatsapp", "WhatsApp"),
            ("telefone", "Telefone"),
            ("cidade", "Cidade"),
            ("observacoes", "Observações"),
        )
        partes += [f"{rotulo}: {comprador[campo]}" for campo, rotulo in rotulos if comprador.get(campo)]
        chave = " ".join(str(comprador["nome_empresa"]).lower().split())
        empresa_id = ctx.carga.upsert(
            "empresas",
            {
                "empresa_id": uid("empresa", "comprador", chave),
                "nome": cortar(comprador["nome_empresa"], 255),
                "descricao": "\n".join(partes),
            },
            "empresa_id",
            "empresa_id",
        )
        if empresa_id:
            ctx.mapa("empresa_comprador")[origem_id] = empresa_id


def carregar_interesses_e_favoritos(ctx):
    pares = {(i["id_empresa"], i["id_material"]) for i in ctx.origem("empresa_material_interesse")}
    pares |= {(a["id_empresa"], a["id_material"]) for a in ctx.origem("alerta_interesse")}
    for id_empresa, id_material in sorted(pares, key=str):
        empresa_id = ctx.mapa("empresa").get(id_empresa)
        categoria_id = ctx.mapa("subcategoria").get(id_material)
        if not empresa_id or not categoria_id:
            ctx.relatorio.ignorar("empresa_materiais_interesses", f"Empresa {id_empresa} / material {id_material} não migrados")
            continue
        ctx.carga.upsert(
            "empresa_materiais_interesses",
            {
                "empresa_material_id": uid("interesse", empresa_id, categoria_id),
                "empresa_id": empresa_id,
                "categoria_id": categoria_id,
            },
            ("empresa_id", "categoria_id"),
            "empresa_material_id",
            atualizar=False,
        )

    for favorito in ctx.origem("favorito"):
        empresa_id = ctx.mapa("empresa").get(favorito["id_empresa"])
        cooperativa_id = ctx.mapa("cooperativa").get(favorito["id_cooperativa"])
        if not empresa_id or not cooperativa_id:
            ctx.relatorio.ignorar("empresa_cooperativas_favoritas", f"Favorito empresa {favorito['id_empresa']} / cooperativa {favorito['id_cooperativa']} não migrados")
            continue
        linha = {
            "favorito_id": uid("favorito", empresa_id, cooperativa_id),
            "empresa_id": empresa_id,
            "cooperativa_id": cooperativa_id,
        }
        if favorito.get("data_adicao"):
            linha["data_criacao"] = para_datahora(favorito["data_adicao"])
        ctx.carga.upsert("empresa_cooperativas_favoritas", linha, ("empresa_id", "cooperativa_id"), "favorito_id")


def carregar_telefones(ctx):
    fontes = []
    for cooperativa in ctx.origem("cooperativa"):
        fontes.append((ctx.mapa("perfil_cooperativa").get(cooperativa["id_cooperativa"]), cooperativa["telefone_whatsapp"]))
    for empresa in ctx.origem("empresa_recicladora"):
        fontes.append((ctx.mapa("perfil_empresa").get(empresa["id_empresa"]), empresa["telefone_whatsapp"]))
    for comprador in ctx.origem("comprador"):
        if comprador["id_empresa_recicladora"]:
            perfil = ctx.mapa("perfil_empresa").get(comprador["id_empresa_recicladora"])
            fontes += [(perfil, comprador.get("whatsapp")), (perfil, comprador.get("telefone"))]
    vistos = set()
    for perfil_id, numero in fontes:
        if not perfil_id or not numero:
            continue
        partes = separar_telefone(numero)
        if not partes:
            ctx.relatorio.ignorar("telefones", f"Telefone inválido: {numero}")
            continue
        ddd, telefone = partes
        if (perfil_id, ddd, telefone) in vistos:
            continue
        vistos.add((perfil_id, ddd, telefone))
        ctx.carga.obter_ou_criar(
            "telefones",
            "telefone_id",
            {"perfil_id": perfil_id, "usuario_id": None, "ddd": ddd, "telefone": telefone},
            {"telefone_id": uid("telefone", perfil_id, ddd, telefone)},
        )


def carregar_usuarios(ctx):
    provisorios = 0
    for usuario in ctx.origem("usuario"):
        origem_id = usuario["id_usuario"]
        usuario_id = uid("usuario", origem_id)
        existente = ctx.carga.buscar("usuarios", "usuario_id", {"email": usuario["email"]})
        if existente and existente != usuario_id:
            ctx.mapa("usuario")[origem_id] = existente
            ctx.relatorio.avisar("usuarios", f"Usuário {origem_id} ({usuario['email']}) já existia no destino e foi reutilizado sem alteração")
            continue
        linha = {
            "usuario_id": usuario_id,
            "nome": cortar(usuario["nome_completo"], 255),
            "email": cortar(usuario["email"], 255),
            "cpf": cpf_provisorio(origem_id),
            "senha_hash": cortar(usuario["senha_hash"], 255),
            "esta_ativo": True,
        }
        if usuario.get("data_criacao"):
            linha["data_criacao"] = para_datahora(usuario["data_criacao"])
        resultado = ctx.carga.upsert("usuarios", linha, "usuario_id", "usuario_id")
        if resultado:
            ctx.mapa("usuario")[origem_id] = resultado
            provisorios += 1
    if provisorios:
        ctx.relatorio.avisar("usuarios", f"{provisorios} usuário(s) receberam CPF provisório no formato MIGxxxxxxxxxxx porque a origem não possui CPF")


def carregar_funcionarios(ctx):
    cooperados = ctx.origem("cooperado")
    for cooperado in cooperados:
        origem_id = cooperado["id_cooperado"]
        usuario_id = ctx.mapa("usuario").get(cooperado["id_usuario"])
        cooperativa_id = ctx.mapa("cooperativa").get(cooperado["id_cooperativa"])
        cargo_id = ctx.mapa("cargo").get(cooperado.get("cargo")) or ctx.mapa("cargo").get(None)
        if not usuario_id or not cooperativa_id or not cargo_id:
            ctx.relatorio.ignorar("funcionarios", f"Cooperado {origem_id} sem usuário, cooperativa ou cargo migrado")
            continue
        situacao = cooperado.get("status") or "ATIVO"
        linha = {
            "funcionario_id": uid("funcionario", origem_id),
            "usuario_id": usuario_id,
            "cooperativa_id": cooperativa_id,
            "cargo_id": cargo_id,
            "status_funcionario": situacao if situacao in STATUS_FUNCIONARIO else "ATIVO",
        }
        if cooperado.get("data_cadastro"):
            linha["data_admissao"] = para_datahora(cooperado["data_cadastro"])
        funcionario_id = ctx.carga.upsert("funcionarios", linha, "funcionario_id", "funcionario_id")
        if funcionario_id:
            ctx.mapa("funcionario")[origem_id] = funcionario_id

    for cooperativa_origem, lista in agrupar(cooperados, "id_cooperativa").items():
        ordenados = sorted(
            lista,
            key=lambda c: (c.get("cargo") != "GESTOR", (c.get("status") or "ATIVO") != "ATIVO", str(c["id_cooperado"])),
        )
        gestor = next((ctx.mapa("funcionario")[c["id_cooperado"]] for c in ordenados if c["id_cooperado"] in ctx.mapa("funcionario")), None)
        if gestor:
            ctx.mapa("gestor")[cooperativa_origem] = gestor

    vinculados = {c["id_usuario"] for c in cooperados}
    for usuario in ctx.origem("usuario"):
        if usuario["tipo_usuario"] == "GESTOR_COOPERATIVA" and usuario["id_usuario"] not in vinculados:
            ctx.relatorio.avisar("funcionarios", f"Usuário {usuario['id_usuario']} é GESTOR_COOPERATIVA mas não possui vínculo em cooperado na origem: migrado apenas para usuarios")


def carregar_equipes(ctx):
    atividades = agrupar(ctx.origem("cooperado_atividade"), "id_cooperado")
    nomes_cooperativa = {c["id_cooperativa"]: c["nome"] for c in ctx.origem("cooperativa")}
    membros = {}
    for cooperado in ctx.origem("cooperado"):
        funcionario_id = ctx.mapa("funcionario").get(cooperado["id_cooperado"])
        if not funcionario_id:
            continue
        cooperativa = cooperado["id_cooperativa"]
        membros.setdefault((cooperativa, EQUIPE_GERAL), []).append(funcionario_id)
        for atividade in atividades.get(cooperado["id_cooperado"], []):
            membros.setdefault((cooperativa, atividade["atividade"]), []).append(funcionario_id)

    for (cooperativa, atividade), lista in sorted(membros.items(), key=lambda item: str(item[0])):
        gestor = ctx.mapa("gestor").get(cooperativa)
        if not gestor:
            ctx.relatorio.ignorar("equipes", f"Cooperativa {cooperativa} sem gestor para a equipe {atividade}")
            continue
        rotulo = ATIVIDADES.get(atividade, atividade)
        if atividade == EQUIPE_GERAL:
            descricao = "Todos os cooperados da cooperativa"
        else:
            descricao = f"Cooperados com a atividade {rotulo} no InterV1"
        equipe_id = ctx.carga.upsert(
            "equipes",
            {
                "equipe_id": uid("equipe", cooperativa, atividade),
                "gestor_id": gestor,
                "nome": cortar(f"{rotulo} - {nomes_cooperativa.get(cooperativa, cooperativa)}", 255),
                "descricao": descricao,
                "esta_ativa": True,
            },
            "equipe_id",
            "equipe_id",
        )
        if not equipe_id:
            continue
        ctx.mapa("equipe")[(cooperativa, atividade)] = equipe_id
        for funcionario_id in dict.fromkeys(lista):
            ctx.carga.upsert(
                "equipes_cooperados",
                {
                    "equipe_cooperado_id": uid("equipe_cooperado", equipe_id, funcionario_id),
                    "equipe_id": equipe_id,
                    "cooperado_id": funcionario_id,
                },
                ("equipe_id", "cooperado_id"),
                "equipe_cooperado_id",
                atualizar=False,
            )


def carregar_rotas(ctx):
    for rota in ctx.origem("rota"):
        cooperativa_id = ctx.mapa("cooperativa").get(rota["id_cooperativa"])
        if not cooperativa_id:
            ctx.relatorio.ignorar("rotas", f"Rota {rota['id_rota']} sem cooperativa migrada")
            continue
        rota_id = ctx.carga.upsert(
            "rotas",
            {
                "rota_id": uid("rota", rota["id_rota"]),
                "cooperativa_id": cooperativa_id,
                "nome": cortar(rota["nome_rota"], 255),
                "esta_ativa": True,
            },
            "rota_id",
            "rota_id",
        )
        if rota_id:
            ctx.mapa("rota")[rota["id_rota"]] = rota_id

    for endereco in ctx.origem("endereco_rota"):
        rota_id = ctx.mapa("rota").get(endereco["id_rota"])
        if not rota_id:
            ctx.relatorio.ignorar("rotas_enderecos", f"Endereço de rota {endereco['id_endereco']} sem rota migrada")
            continue
        endereco_id = _endereco(
            ctx, ("endereco_rota", endereco["id_endereco"]), None, endereco["endereco_completo"], TIPO_ENDERECO_COLETA
        )
        if not endereco_id:
            continue
        ctx.carga.upsert(
            "rotas_enderecos",
            {
                "rota_endereco_id": uid("rota_endereco", endereco["id_endereco"]),
                "rota_id": rota_id,
                "endereco_id": endereco_id,
                "nome_local": cortar(endereco["nome_local"], 255),
                "tipo_local": cortar(endereco["tipo_local"], 50),
                "ordem": endereco["ordem"] or 1,
            },
            "rota_endereco_id",
            "rota_endereco_id",
        )
