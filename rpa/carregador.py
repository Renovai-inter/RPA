import psycopg2
from psycopg2 import sql


def _lista(nomes):
    return sql.SQL(", ").join(sql.Identifier(nome) for nome in nomes)


def _filtro(filtro):
    condicoes = []
    parametros = []
    for coluna, valor in filtro.items():
        if valor is None:
            condicoes.append(sql.SQL("{} IS NULL").format(sql.Identifier(coluna)))
        else:
            condicoes.append(sql.SQL("{} = %s").format(sql.Identifier(coluna)))
            parametros.append(valor)
    return sql.SQL(" AND ").join(condicoes), parametros


class Carregador:
    def __init__(self, conexao, relatorio):
        self.conexao = conexao
        self.relatorio = relatorio
        self.savepoints = 0

    def consultar(self, consulta, parametros=None):
        with self.conexao.cursor() as cursor:
            cursor.execute(consulta, parametros)
            return [dict(linha) for linha in cursor.fetchall()]

    def executar(self, comando, parametros=None):
        with self.conexao.cursor() as cursor:
            cursor.execute(comando, parametros)
            return cursor.rowcount

    def protegido(self, tabela, funcao):
        self.savepoints += 1
        nome = sql.Identifier(f"sp_rpa_{self.savepoints}")
        self.executar(sql.SQL("SAVEPOINT {}").format(nome))
        try:
            resultado = funcao()
        except psycopg2.Error as erro:
            self.executar(sql.SQL("ROLLBACK TO SAVEPOINT {}").format(nome))
            mensagem = (erro.pgerror or str(erro)).strip().splitlines()
            self.relatorio.erro(tabela, mensagem[0] if mensagem else repr(erro))
            return None
        self.executar(sql.SQL("RELEASE SAVEPOINT {}").format(nome))
        return resultado

    def tabelas_existentes(self):
        linhas = self.consultar(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
        )
        return {linha["table_name"] for linha in linhas}

    def listar(self, tabela, colunas):
        consulta = sql.SQL("SELECT {} FROM {} ORDER BY 1").format(_lista(colunas), sql.Identifier(tabela))
        linhas = self.protegido(tabela, lambda: self.consultar(consulta)) or []
        return [
            {chave: (str(valor) if valor is not None and chave.endswith("_id") else valor) for chave, valor in linha.items()}
            for linha in linhas
        ]

    def buscar_linha(self, tabela, colunas, filtro):
        condicao, parametros = _filtro(filtro)
        consulta = sql.SQL("SELECT {} FROM {} WHERE {} ORDER BY 1 LIMIT 1").format(
            _lista(colunas), sql.Identifier(tabela), condicao
        )
        linhas = self.consultar(consulta, parametros)
        if not linhas:
            return None
        return {chave: (str(valor) if valor is not None and chave.endswith("_id") else valor) for chave, valor in linhas[0].items()}

    def buscar(self, tabela, retorno, filtro):
        linha = self.buscar_linha(tabela, [retorno], filtro)
        return linha[retorno] if linha else None

    def contar_registros(self, tabela):
        linhas = self.consultar(sql.SQL("SELECT COUNT(*) AS total FROM {}").format(sql.Identifier(tabela)))
        return linhas[0]["total"]

    def upsert(self, tabela, linha, conflito, retorno, atualizar=True):
        conflito = (conflito,) if isinstance(conflito, str) else tuple(conflito)
        colunas = list(linha)
        editaveis = [coluna for coluna in colunas if coluna not in conflito and coluna != retorno] if atualizar else []
        if editaveis:
            acao = sql.SQL("DO UPDATE SET {} WHERE ({}) IS DISTINCT FROM ({})").format(
                sql.SQL(", ").join(sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(c)) for c in editaveis),
                sql.SQL(", ").join(sql.SQL("{}.{}").format(sql.Identifier(tabela), sql.Identifier(c)) for c in editaveis),
                sql.SQL(", ").join(sql.SQL("EXCLUDED.{}").format(sql.Identifier(c)) for c in editaveis),
            )
        else:
            acao = sql.SQL("DO NOTHING")
        comando = sql.SQL(
            "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) {} RETURNING {} AS retorno, (xmax = 0) AS inserido"
        ).format(
            sql.Identifier(tabela),
            _lista(colunas),
            sql.SQL(", ").join(sql.Placeholder() * len(colunas)),
            _lista(conflito),
            acao,
            sql.Identifier(retorno),
        )

        def gravar():
            with self.conexao.cursor() as cursor:
                cursor.execute(comando, [linha[coluna] for coluna in colunas])
                resultado = cursor.fetchone()
            if resultado:
                self.relatorio.contar(tabela, "inseridos" if resultado["inserido"] else "atualizados")
                return str(resultado["retorno"])
            self.relatorio.contar(tabela, "inalterados")
            return self.buscar(tabela, retorno, {coluna: linha[coluna] for coluna in conflito})

        return self.protegido(tabela, gravar)

    def obter_ou_criar(self, tabela, chave, filtro, linha):
        existente = self.protegido(tabela, lambda: self.buscar(tabela, chave, filtro))
        if existente:
            self.relatorio.contar(tabela, "inalterados")
            return existente
        return self.upsert(tabela, {**linha, **filtro}, chave, chave, atualizar=False)

    def atualizar(self, tabela, valores, filtro):
        condicao, parametros = _filtro(filtro)
        comando = sql.SQL("UPDATE {} SET {} WHERE {} AND ({}) IS DISTINCT FROM ({})").format(
            sql.Identifier(tabela),
            sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(c)) for c in valores),
            condicao,
            _lista(valores),
            sql.SQL(", ").join(sql.Placeholder() * len(valores)),
        )
        argumentos = list(valores.values()) + parametros + list(valores.values())
        return self.protegido(tabela, lambda: self.executar(comando, argumentos)) or 0
