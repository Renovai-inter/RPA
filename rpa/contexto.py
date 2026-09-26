from dataclasses import dataclass, field


@dataclass
class Contexto:
    dados: dict
    carga: object
    relatorio: object
    logger: object
    ids: dict = field(default_factory=dict)

    def mapa(self, nome):
        return self.ids.setdefault(nome, {})

    def origem(self, tabela):
        return self.dados.get(tabela, [])
