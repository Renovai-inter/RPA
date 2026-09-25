import json
from collections import defaultdict
from datetime import datetime

CAMPOS = ("inseridos", "atualizados", "inalterados", "ignorados", "erros")


class Relatorio:
    def __init__(self, logger):
        self.logger = logger
        self.inicio = datetime.now()
        self.tabelas = defaultdict(lambda: dict.fromkeys(CAMPOS, 0))
        self.avisos = []
        self.origem = {}
        self.destino = {}
        self.verificacoes = {}
        self.status = "EM_EXECUCAO"
        self.falha = None

    def contar(self, tabela, campo, quantidade=1):
        self.tabelas[tabela][campo] = self.tabelas[tabela].get(campo, 0) + quantidade

    def avisar(self, tabela, mensagem):
        self.avisos.append({"tipo": "AVISO", "tabela": tabela, "mensagem": mensagem})
        self.logger.warning("%s | %s", tabela, mensagem)

    def ignorar(self, tabela, mensagem):
        self.contar(tabela, "ignorados")
        self.avisos.append({"tipo": "IGNORADO", "tabela": tabela, "mensagem": mensagem})
        self.logger.warning("%s | ignorado | %s", tabela, mensagem)

    def erro(self, tabela, mensagem):
        self.contar(tabela, "erros")
        self.avisos.append({"tipo": "ERRO", "tabela": tabela, "mensagem": mensagem})
        self.logger.error("%s | %s", tabela, mensagem)

    def tem_erros(self):
        return any(valores.get("erros") for valores in self.tabelas.values())

    def resumo(self):
        linhas = ["Resumo da carga:"]
        for tabela in sorted(self.tabelas):
            valores = self.tabelas[tabela]
            linhas.append(f"  {tabela:<24} " + " ".join(f"{campo}={valores.get(campo, 0)}" for campo in valores))
        linhas.append(f"  status={self.status} avisos={len(self.avisos)}")
        return "\n".join(linhas)

    def salvar(self, pasta):
        pasta.mkdir(parents=True, exist_ok=True)
        fim = datetime.now()
        caminho = pasta / f"relatorio_{fim:%Y%m%d_%H%M%S}.json"
        conteudo = {
            "status": self.status,
            "falha": self.falha,
            "inicio": self.inicio,
            "fim": fim,
            "duracao_segundos": round((fim - self.inicio).total_seconds(), 2),
            "registros_origem": self.origem,
            "registros_destino": self.destino,
            "movimento_por_tabela": dict(self.tabelas),
            "verificacoes": self.verificacoes,
            "avisos": self.avisos,
        }
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(conteudo, arquivo, ensure_ascii=False, indent=2, default=str)
        return caminho
