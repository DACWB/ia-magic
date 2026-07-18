"""Extrai objetos JSON de dentro de texto que não é JSON.

Precisamos disso em dois lugares bem diferentes do sistema:

1. **Log do Arena** — blocos JSON no meio de mensagens da Unity
2. **Respostas da IA** — o modelo às vezes escreve "Aqui está a análise:"
   antes do JSON, ou embrulha em ```json ... ```

Nos dois casos o problema é o mesmo: achar JSON válido no meio de texto solto.
Por isso mora em `utils` e não em nenhum dos dois serviços.

O cuidado essencial é ignorar chaves que estejam DENTRO de strings. Em Magic
isso não é caso raro: custo de mana se escreve `{2}{R}{R}`, e um contador de
chaves ingênuo se perde na primeira carta que aparecer.
"""

import json
from collections.abc import Iterator
from typing import Any


def extrair_objetos_json(texto: str) -> Iterator[dict[str, Any]]:
    """Extrai todo objeto JSON de nível superior encontrado no texto.

    Varre o texto contando chaves `{` e `}` até fechar cada bloco, pulando
    o que estiver dentro de aspas.

    Args:
        texto: Qualquer texto que possa conter JSON no meio.

    Yields:
        Cada objeto JSON válido encontrado, já convertido em dicionário.
        Blocos malformados ou truncados são simplesmente ignorados.
    """
    posicao = 0
    tamanho = len(texto)

    while posicao < tamanho:
        if texto[posicao] != "{":
            posicao += 1
            continue

        profundidade = 0
        dentro_de_string = False
        escapado = False
        fim_encontrado = False

        for indice in range(posicao, tamanho):
            caractere = texto[indice]

            # Uma barra invertida faz o próximo caractere perder o sentido
            # especial — inclusive uma aspa. Sem isso, `"texto \" aqui"`
            # bagunçaria a contagem.
            if escapado:
                escapado = False
                continue
            if caractere == "\\":
                escapado = True
                continue
            if caractere == '"':
                dentro_de_string = not dentro_de_string
                continue
            if dentro_de_string:
                continue

            if caractere == "{":
                profundidade += 1
            elif caractere == "}":
                profundidade -= 1
                if profundidade == 0:
                    try:
                        yield json.loads(texto[posicao : indice + 1])
                    except json.JSONDecodeError:
                        pass  # bloco inválido — segue procurando
                    posicao = indice + 1
                    fim_encontrado = True
                    break

        if not fim_encontrado:
            # Bloco aberto que nunca fecha: fim do texto no meio da escrita
            break


def maior_objeto_json(texto: str) -> dict[str, Any] | None:
    """Devolve o maior objeto JSON encontrado no texto.

    Usado pra ler respostas da IA. O critério "maior" resolve um caso chato:
    se o modelo escreve um exemplo pequeno antes da resposta de verdade, ou
    se a resposta contém objetos aninhados que também casam com o padrão,
    queremos o bloco completo — que é sempre o maior.

    Args:
        texto: Resposta da IA.

    Returns:
        O maior objeto JSON, ou None se não houver nenhum válido.
    """
    candidatos = list(extrair_objetos_json(texto))
    if not candidatos:
        return None
    return max(candidatos, key=lambda objeto: len(json.dumps(objeto)))
