CATEGORIAS_MACRO = {
    "PAPEIS": "Papel",
    "PLASTICOS": "Plástico",
    "METAIS": "Metal",
    "VIDROS": "Vidro",
    "OUTROS": "Outros",
}

CARGOS = {
    "GESTOR": "Gestor",
    "TESOUREIRO": "Tesoureiro",
    "MOTORISTA": "Motorista",
    None: "Cooperado",
}

STATUS_COLETA = {
    "AGENDADA": "Pendente",
    "EM_ANDAMENTO": "Aberto",
    "CONCLUIDA": "Coletado",
    "CANCELADA": "Cancelado",
}

STATUS_TRIAGEM = "Concluído"

REF_COLETA = "COLETA"
REF_TRIAGEM = "TRIAGEM"
REF_PEDIDO = "PEDIDO"
REF_NEGOCIACAO = "NEGOCIACAO"

STATUS_NEGOCIACAO = {
    "AGUARDANDO_RESPOSTA": "Aberto",
    "EM_NEGOCIACAO": "Pendente",
    "ACEITA": "Aceito",
    "RECUSADA": "Recusado",
    "CANCELADA": "Cancelado",
    "CONCLUIDA": "Finalizado",
}

STATUS_VENDA = {
    "CONCLUIDA": "Finalizado",
    "CANCELADA": "Cancelado",
}

TIPOS_RATEIO = {
    "AUTOMATICO": "Rateio calculado automaticamente pelo sistema, dividindo o valor líquido (vendas - despesas) entre os cooperados ativos.",
    "MANUAL": "Rateio com valores definidos manualmente pelo gestor, fora do cálculo automático.",
}

CONFIG_RATEIO = {
    "IGUALITARIO": "AUTOMATICO",
    "COM_EXCECOES": "MANUAL",
}

DESPESAS_FIXAS = {"ALUGUEL", "ENERGIA_ELETRICA", "AGUA", "ADMINISTRATIVO"}

CATEGORIAS_DESPESA = {
    "ALUGUEL": "Aluguel",
    "ENERGIA_ELETRICA": "Energia elétrica",
    "AGUA": "Água",
    "COMBUSTIVEL": "Combustível",
    "MANUTENCAO_VEICULOS": "Manutenção de veículos",
    "EQUIPAMENTOS": "Equipamentos",
    "MATERIAIS_CONSUMO": "Materiais de consumo",
    "ADMINISTRATIVO": "Administrativo",
    "OUTROS": "Outros",
}

EQUIPE_GERAL = "GERAL"

ATIVIDADES = {
    "GERAL": "Equipe Geral",
    "COLETA_EXTERNA": "Coleta Externa",
    "SEPARACAO_MATERIAIS": "Separação de Materiais",
    "ORGANIZACAO_GALPAO": "Organização do Galpão",
    "PRENSAGEM": "Prensagem",
    "PESAGEM": "Pesagem",
    "NEGOCIACOES": "Negociações",
    "ADMINISTRATIVO": "Administrativo",
}

PRIORIDADE_EQUIPE_TRIAGEM = (
    "SEPARACAO_MATERIAIS",
    "PESAGEM",
    "PRENSAGEM",
    "ORGANIZACAO_GALPAO",
    "GERAL",
)

SEGMENTOS = {
    "RECICLADORA": "Recicladora",
    "INDUSTRIA_RECICLADORA": "Indústria recicladora",
    "INDUSTRIA_TRANSFORMACAO": "Indústria de transformação",
    "SUCATEIRA": "Sucateira",
    "COMERCIO_RECICLAVEIS": "Comércio de recicláveis",
    "FABRICANTE_EMBALAGENS": "Fabricante de embalagens",
    "GESTAO_RESIDUOS": "Gestão de resíduos",
    "OUTRO": "Outro",
}

DIAS_SEMANA = ("SEGUNDA", "TERCA", "QUARTA", "QUINTA", "SEXTA", "SABADO", "DOMINGO")

ABREVIACOES_DIAS = {
    "SEGUNDA": "Seg",
    "TERCA": "Ter",
    "QUARTA": "Qua",
    "QUINTA": "Qui",
    "SEXTA": "Sex",
    "SABADO": "Sáb",
    "DOMINGO": "Dom",
}

TABELA_ITENS = "pedido_itens"

COLUNAS_ITENS = {
    "id": "item_id",
    "pedido": "pedido_id",
    "material": "material_id",
    "quantidade": "quantidade_kg",
    "preco": "preco_unitario",
}

TIPOS_COLETA = {
    "COLETA_EXTERNA": "EXTERNA",
    "ENTREGA_COOPERATIVA": "ENTREGA",
}

CONTATOS_PREFERENCIAIS = {"WHATSAPP", "TELEFONE", "EMAIL"}

STATUS_FUNCIONARIO = {"ATIVO", "AFASTADO", "INATIVO"}

TIPO_ENDERECO_PERFIL = "Comercial"
TIPO_ENDERECO_COLETA = "Coleta"

TABELAS_DESTINO = (
    "enderecos",
    "categorias_materiais",
    "materiais",
    "cooperativas",
    "empresas",
    "perfis",
    "usuarios",
    "cargos",
    "status",
    "funcionarios",
    "telefones",
    "equipes",
    "equipes_cooperados",
    "pedidos",
    TABELA_ITENS,
    "pedidos_cooperativas",
    "coletas",
    "triagens",
    "estoques",
    "movimentacoes_estoques",
    "tipos_rateios",
    "rateios",
    "rateios_funcionarios",
    "despesas",
    "lancamentos_despesas",
    "rotas",
    "rotas_enderecos",
    "rota_execucoes",
    "rota_execucoes_paradas",
    "negociacoes",
    "negociacao_itens",
    "negociacao_mensagens",
    "empresa_materiais_interesses",
    "empresa_cooperativas_favoritas",
)
