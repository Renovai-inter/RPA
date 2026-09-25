import re
import unicodedata
import uuid
from datetime import date, datetime, time

from .mapeamentos import ABREVIACOES_DIAS, DIAS_SEMANA

NAMESPACE = uuid.UUID("0b6f5a3e-2c1d-4e8f-9a7b-5c3d2e1f0a9b")


def uid(*partes):
    return str(uuid.uuid5(NAMESPACE, "|".join(str(parte) for parte in partes)))


def cortar(valor, limite):
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto[:limite] if texto else None


def normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().split())


def moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def indexar(linhas, chave):
    return {linha[chave]: linha for linha in linhas}


def agrupar(linhas, chave):
    grupos = {}
    for linha in linhas:
        grupos.setdefault(linha[chave], []).append(linha)
    return grupos


def para_datahora(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, date):
        return datetime.combine(valor, time.min)
    return datetime.fromisoformat(str(valor))


def inicio_mes(valor):
    data = para_datahora(valor)
    return date(data.year, data.month, 1) if data else None


def ordem_data(valor):
    return para_datahora(valor) or datetime.min


def separar_telefone(valor):
    numeros = digitos(valor)
    if len(numeros) > 11 and numeros.startswith("55"):
        numeros = numeros[2:]
    if not numeros:
        return None
    ddd = None
    if len(numeros) in (10, 11):
        ddd, numeros = numeros[:2], numeros[2:]
    if len(numeros) >= 8:
        numeros = f"{numeros[:-4]}-{numeros[-4:]}"
    return ddd, numeros[:20]


def separar_endereco(texto):
    partes = [parte.strip() for parte in str(texto or "").split(",") if parte.strip()]
    resultado = {"logradouro": None, "numero": None, "complemento": None, "cidade": None}
    if not partes:
        return resultado
    resultado["logradouro"] = partes.pop(0)
    if partes and re.fullmatch(r"\d+[A-Za-z]?|s/?n", partes[0], re.IGNORECASE):
        resultado["numero"] = partes.pop(0)
    if partes:
        cidade_uf = re.fullmatch(r"(.+?)\s*[-/]\s*[A-Za-z]{2}", partes[-1])
        if cidade_uf:
            resultado["cidade"] = cidade_uf.group(1)
            partes.pop()
    resultado["complemento"] = ", ".join(partes) or None
    return resultado


def formatar_hora(valor):
    if valor is None:
        return ""
    if isinstance(valor, time):
        return valor.strftime("%H:%M")
    return str(valor)[:5]


def resumir_horarios(linhas):
    por_dia = {linha["dia_semana"]: linha for linha in linhas}
    blocos = []
    for indice, dia in enumerate(DIAS_SEMANA):
        linha = por_dia.get(dia)
        if not linha:
            continue
        if linha["fechado"]:
            faixa = "Fechado"
        else:
            faixa = f"{formatar_hora(linha['horario_abertura'])}-{formatar_hora(linha['horario_encerramento'])}"
        if blocos and blocos[-1]["faixa"] == faixa and blocos[-1]["fim"] == indice - 1:
            blocos[-1]["fim"] = indice
        else:
            blocos.append({"inicio": indice, "fim": indice, "faixa": faixa})
    textos = []
    for bloco in blocos:
        inicio = ABREVIACOES_DIAS[DIAS_SEMANA[bloco["inicio"]]]
        fim = ABREVIACOES_DIAS[DIAS_SEMANA[bloco["fim"]]]
        dias = inicio if bloco["inicio"] == bloco["fim"] else f"{inicio}-{fim}"
        textos.append(f"{dias} {bloco['faixa']}")
    return cortar("; ".join(textos), 100)


def cpf_provisorio(id_origem):
    numeros = digitos(id_origem)
    if numeros:
        return f"MIG{int(numeros) % 10 ** 11:011d}"
    return "MIG" + uuid.uuid5(NAMESPACE, str(id_origem)).hex[:11].upper()
