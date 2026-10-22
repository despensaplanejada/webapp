# -*- coding: utf-8 -*-
"""
Coletor de produtos do Soudaki para integração com o sistema Dispensa Planejada.

Este coletor é projetado para funcionar com lojas Webflow, extraindo dados de produtos
diretamente das páginas de categoria e produto.
"""

import json
import os
import random
import re
import time
from datetime import date
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Anti-block: User-Agent rotation + jitter
# ---------------------------------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def random_ua():
    return random.choice(USER_AGENTS)


def sleep_with_jitter(base_sleep: float, factor: float = 1.0):
    """Sleep com jitter randômico para evitar padrão detectável."""
    time.sleep(base_sleep * factor + random.uniform(0, base_sleep * 0.6))


def backoff_sleep(tentativa: int, base: float = 5.0, maximo: float = 60.0):
    """Backoff exponencial: 5s, 10s, 20s... com jitter."""
    espera = min(base * (2 ** tentativa), maximo)
    espera += random.uniform(0, espera * 0.3)
    print(f"    [backoff] aguardando {espera:.1f}s (tentativa {tentativa + 1})")
    time.sleep(espera)

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------
BASE_URL = "https://www.soudaki.com.br"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": random_ua(),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Arquivos de saída
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_PRODUTOS = os.path.join(RAIZ, "produtos_soudaki.json")
ARQUIVO_PRECOS = os.path.join(RAIZ, "precos_soudaki_ampliado.json")

# Regex para extrair apresentação: ex. "500g", "1kg", "200 ml", "200ml", "1 L", "12 un", "12un"
RE_APRESENTACAO = re.compile(
    r"""
    (\d+(?:[.,]\d+)?)\s*       # quantidade (número com opcional decimal)
    (g|kg|ml|l|un|unid|unidade)  # unidade (case-insensitive)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Seletores comuns para lojas Webflow (ajustar conforme necessário)
PRODUCT_SELECTORS = [
    ".product-item",           # Seletor genérico
    ".product-card",           # Outro comum
    "[data-w-id]",            # Atributo Webflow
    ".collection-item",        # Coleções Webflow
    ".store-product",          # Nome genérico de loja
]

PRICE_SELECTORS = [
    ".price",                  # Classe genérica
    ".product-price",          # Preço do produto
    ".sale-price",             # Preço promocional
    ".regular-price",          # Preço regular
    "[data-price]",            # Atributo de preço
    ".price-tag",              # Tag de preço
]

EAN_SELECTORS = [
    "[data-ean]",              # Atributo direto
    ".ean",                    # Classe EAN
    ".gtin",                   # Classe GTIN
    ".barcode",                # Classe de código de barras
    "span:contains('Código de Barras')", # Texto seguido do valor
    "span:contains('GTIN')",   # Texto seguido do valor
    "span:contains('EAN')",    # Texto seguido do valor
]

# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def normalizar_unidade(un: str) -> str:
    un = un.lower().strip()
    if un in ("unid", "unidade"):
        return "un"
    return un


def extrair_apresentacao(nome: str) -> dict | None:
    """Extrai quantidade e unidade do nome do produto via regex."""
    match = RE_APRESENTACAO.search(nome)
    if not match:
        return None
    qtd_str = match.group(1).replace(",", ".")
    unidade = normalizar_unidade(match.group(2))
    try:
        qtd = float(qtd_str)
        if qtd.is_integer():
            qtd = int(qtd)
    except ValueError:
        return None
    return {"quantidade": qtd, "unidade_medida": unidade}


def ean_valido(ean) -> bool:
    if not ean:
        return False
    ean = str(ean).strip()
    return ean.isdigit() and len(ean) == 13


def limpar_texto(texto: str) -> str:
    """Remove espaços extras e quebras de linha."""
    if not texto:
        return ""
    return re.sub(r'\s+', ' ', texto.strip())


def extrair_preco_de_texto(texto: str) -> Optional[float]:
    """Extrai valor monetário de uma string."""
    if not texto:
        return None
    # Remove símbolos de moeda e espaços
    texto_limpo = re.sub(r'[R$\s\.]', '', texto)
    # Substitui vírgula por ponto para decimal
    texto_limpo = texto_limpo.replace(',', '.')
    try:
        return float(texto_limpo)
    except ValueError:
        return None


def descobrir_categorias_soudaki() -> List[Dict[str, str]]:
    """
    Descobre as categorias (seções) disponíveis no Soudaki analisando a página inicial.
    """
    try:
        print("Descobrindo categorias do Soudaki...")
        headers_dyn = {
            "User-Agent": random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
        resp = requests.get(BASE_URL, headers=headers_dyn, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')

        categorias = []
        # Procurar por links que provavelmente levam a categorias
        links = soup.find_all('a', href=True)

        for link in links:
            href = link['href']
            texto = limpar_texto(link.get_text())

            # Filtrar links que parecem ser de categorias
            if (href and
                ('/shop/' in href or '/colecao/' in href or '/categoria/' in href) and
                texto and len(texto) > 2 and
                not any(x in href.lower() for x in ['login', 'carrinho', 'conta', 'blog', 'contato'])):

                # Construir URL absoluta
                url_completa = urljoin(BASE_URL, href)
                slug = href.strip('/').split('/')[-1] if '/' in href else href.strip('/')

                categorias.append({
                    "slug": slug,
                    "nome": texto,
                    "url": url_completa
                })

        # Remover duplicatas baseado no slug
        categorias_unicas = []
        slugs_vistos = set()
        for cat in categorias:
            if cat["slug"] not in slugs_vistos and cat["slug"]:
                slugs_vistos.add(cat["slug"])
                categorias_unicas.append(cat)

        print(f"Encontradas {len(categorias_unicas)} categorias")
        return categorias_unicas[:10]  # Limitar para evitar muitas requisições

    except Exception as e:
        print(f"Erro ao descobrir categorias: {e}")
        # Fallback para categorias conhecidas
        return [
            {"slug": "bebidas", "nome": "Bebidas", "url": f"{BASE_URL}/shop/bebidas/"},
            {"slug": "mercearia", "nome": "Mercearia", "url": f"{BASE_URL}/shop/mercearia/"},
            {"slug": "higiene", "nome": "Higiene e Beleza", "url": f"{BASE_URL}/shop/higiene/"},
            {"slug": "limpeza", "nome": "Limpeza", "url": f"{BASE_URL}/shop/limpeza/"},
            {"slug": "congelados", "nome": "Congelados", "url": f"{BASE_URL}/shop/congelados/"},
        ]


def coletar_produtos_da_pagina(url: str, secao_nome: str) -> List[Dict[str, Any]]:
    """
    Coleta produtos de uma página específica do Soudaki.
    """
    try:
        print(f"Coletando produtos de: {url}")
        headers_dyn = {
            "User-Agent": random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
        for tentativa in range(3):
            resp = requests.get(url, headers=headers_dyn, timeout=20)
            if resp.status_code in (429, 500, 502, 503, 504):
                if tentativa < 2:
                    backoff_sleep(tentativa)
                    continue
                resp.raise_for_status()
            break
        else:
            resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')

        produtos = []

        # Tentar diferentes seletores para encontrar produtos
        produto_elements = []
        for selector in PRODUCT_SELECTORS:
            elementos = soup.select(selector)
            if elementos:
                produto_elements = elementos
                print(f"  Encontrados {len(elementos)} produtos com seletor '{selector}'")
                break

        # Se nenhum seletor funcionar, tentar encontrar por estrutura comum
        if not produto_elements:
            # Procurar por elementos que contenham preço e nome
            todos_elementos = soup.find_all(['div', 'article', 'li'])
            for elem in todos_elementos:
                texto = limpar_texto(elem.get_text())
                if ('R$' in texto or '$' in texto) and len(texto) > 20:
                    produto_elements.append(elem)
            produto_elements = produto_elements[:20]  # Limitar

        for i, produto_elem in enumerate(produto_elements):
            try:
                produto_data = extrair_dados_do_produto(produto_elem, secao_nome)
                if produto_data and produto_data.get("ean"):
                    produtos.append(produto_data)

                if (i + 1) % 10 == 0:
                    print(f"  Processados {i + 1} elementos...")

            except Exception as e:
                print(f"  Erro ao processar produto {i}: {e}")
                continue

        print(f"  Total de produtos válidos extraídos: {len(produtos)}")
        return produtos

    except Exception as e:
        print(f"Erro ao coletar produtos de {url}: {e}")
        return []


def extrair_dados_do_produto(elemento: BeautifulSoup, secao_padrao: str) -> Optional[Dict[str, Any]]:
    """
    Extrai dados completos de um produto a partir de um elemento HTML.
    """
    try:
        # Extrair nome/título do produto
        nome = ""
        titulo_selectors = [".product-title", ".product-name", "h1", "h2", "h3", ".title", "[title]"]
        for selector in titulo_selectors:
            elem_nome = elemento.select_one(selector)
            if elem_nome:
                nome = limpar_texto(elem_nome.get_text()) or limpar_texto(elem_nome.get("title", ""))
                if nome:
                    break

        if not nome:
            # Tentar obter do texto geral
            texto_geral = limpar_texto(elemento.get_text())
            if texto_geral and len(texto_geral) > 10:
                # Primeira linha razoavelmente longa pode ser o nome
                linhas = [l.strip() for l in texto_geral.split('\n') if l.strip()]
                if linhas:
                    nome = linhas[0][:100]  # Limitar tamanho

        if not nome or len(nome) < 3:
            return None

        # Extrair EAN
        ean = extrair_ean_do_elemento(elemento)
        if not ean:
            return None

        # Extrair marca
        marca = extrair_marca_do_elemento(elemento, nome)

        # Extrair preços
        precos = extrair_precos_do_elemento(elemento)
        if not precos:
            return None  # Pular produtos sem preço válido

        # Extrair disponibilidade em estoque
        em_estoque = verificar_estoque(elemento)

        # Extrair apresentação do nome
        apresentacao = extrair_apresentacao(nome) or {"quantidade": 1, "unidade_medida": "un"}

        # Extrair URL da imagem
        imagem_url = extrair_imagem_do_elemento(elemento)

        return {
            "nome": nome,
            "ean": ean,
            "marca": marca,
            "apresentacao": apresentacao,
            "preco_regular": precos["regular"],
            "preco_promocional": precos["promocional"],
            "em_estoque": em_estoque,
            "imagem_url": imagem_url,
            "secao": secao_padrao,
            "subsecao": ""  # Pode ser aprimorado posteriormente
        }

    except Exception as e:
        print(f"Erro ao extrair dados do produto: {e}")
        return None


def extrair_ean_do_elemento(elemento: BeautifulSoup) -> Optional[str]:
    """Extrai EAN/GTIN de um elemento produto."""
    # Tentar seletores específicos
    for selector in EAN_SELECTORS:
        try:
            if selector.startswith("span:contains("):
                # Seletor especial para texto contido
                texto_procurado = selector[13:-2]  # Extrair o texto entre aspas
                elem_texto = elemento.find(string=re.compile(texto_procurado, re.I))
                if elem_texto:
                    # Procurar o próximo elemento ou texto que contém o valor
                    proximo = elem_texto.find_next()
                    if proximo and proximo.get_text():
                        texto_valor = limpar_texto(proximo.get_text())
                        ean_limpo = re.sub(r'[^\d]', '', texto_valor)
                        if ean_valido(ean_limpo):
                            return ean_limpo
            else:
                elem_ean = elemento.select_one(selector)
                if elem_ean:
                    # Tentar atributo primeiro
                    ean_attr = elem_ean.get("data-ean") or elem_ean.get("ean") or elem_ean.get("gtin")
                    if ean_attr and ean_valido(ean_attr):
                        return ean_attr

                    # Senão, tentar o texto
                    texto_ean = limpar_texto(elem_ean.get_text())
                    ean_limpo = re.sub(r'[^\d]', '', texto_ean)
                    if ean_valido(ean_limpo):
                        return ean_limpo
        except Exception:
            continue

    # Se ainda não encontrou, procurar por padrões de EAN no texto inteiro
    texto_completo = limpar_texto(elemento.get_text())
    # Procurar por sequências de 13 dígitos
    matches = re.findall(r'\b\d{13}\b', texto_completo)
    for match in matches:
        if ean_valido(match):
            return match

    return None


def extrair_marca_do_elemento(elemento: BeautifulSoup, nome_produto: str) -> str:
    """Extrai a marca do produto."""
    # Tentar seletores específicos de marca
    marca_selectors = [".brand", ".product-brand", ".marca", "[data-brand]"]
    for selector in marca_selectors:
        elem_marca = elemento.select_one(selector)
        if elem_marca:
            marca = limpar_texto(elem_marca.get_text()) or elem_marca.get("data-brand", "")
            if marca and len(marca) > 1:
                return marca

    # Tentar extrair do nome (primeira palavra muitas vezes é a marca)
    if nome_produto:
        primeira_palavra = nome_produto.split()[0] if nome_produto.split() else ""
        if len(primeira_palavra) > 1 and primeira_palavra.isalpha():
            # Verificar se não é uma palavra comum de produto
            palavras_comuns = {"refrigerante", "suco", "água", "cerveja", "vinho", "leite", "iogurte",
                             "pão", "bolo", "biscoito", "chocolate", "café", "açúcar", "sal", "óleo"}
            if primeira_palavra.lower() not in palavras_comuns:
                return primeira_palavra

    return "Não Informada"


def extrair_precos_do_elemento(elemento: BeautifulSoup) -> Optional[Dict[str, float]]:
    """Extrai preços regular e promocional de um elemento produto."""
    try:
        preco_regular = None
        preco_promocional = None

        # Procurar por elementos de preço
        for selector in PRICE_SELECTORS:
            elementos_preco = elemento.select(selector)
            for elem_preco in elementos_preco:
                texto_preco = limpar_texto(elem_preco.get_text())
                valor = extrair_preco_de_texto(texto_preco)
                if valor is not None:
                    # Determinar se é regular ou promocional baseado no contexto
                    classe = " ".join(elem_preco.get("class", []))
                    if any(x in classe.lower() for x in ["sale", "promo", "desconto", "oferta"]):
                        if preco_promocional is None or valor < preco_promocional:
                            preco_promocional = valor
                    else:
                        if preco_regular is None or valor > preco_regular:
                            preco_regular = valor

        # Se encontramos apenas um preço, assume-se que é o regular
        if preco_regular is not None and preco_promocional is None:
            preco_promocional = preco_regular
        elif preco_promocional is not None and preco_regular is None:
            preco_regular = preco_promocional

        # Validar que temos preços razoáveis
        if preco_regular is not None and preco_regular > 0:
            return {
                "regular": round(preco_regular, 2),
                "promocional": round(preco_promocional or preco_regular, 2)
            }

        return None

    except Exception:
        return None


def verificar_estoque(elemento: BeautifulSoup) -> bool:
    """Verifica se o produto está em estoque."""
    try:
        texto_completo = limpar_texto(elemento.get_text()).lower()

        # Indicadores de esgotado
        indicadores_esgotado = [
            "esgotado", "fora de estoque", "indisponível", "out of stock",
            "sem estoque", "acabou", "temporariamente indisponível"
        ]

        for indicador in indicadores_esgotado:
            if indicador in texto_completo:
                return False

        # Indicadores de disponível (se nenhum indicador de esgotado foi encontrado)
        indicadores_disponivel = [
            "em estoque", "disponível", "available", "in stock",
            "comprar", "adicionar ao carrinho"
        ]

        for indicador in indicadores_disponivel:
            if indicador in texto_completo:
                return True

        # Padrão: assumir disponível se não houver indicação clara de esgotado
        return True

    except Exception:
        return True  # Em caso de dúvida, assumir disponível


def extrair_imagem_do_elemento(elemento: BeautifulSoup) -> Optional[str]:
    """Extrai URL da imagem do produto."""
    try:
        # Procurar por imagens
        img_elem = elemento.select_one("img")
        if img_elem:
            # Tentar vários atributos de imagem
            for attr in ["src", "data-src", "data-lazy", "data-original"]:
                img_url = img_elem.get(attr)
                if img_url and isinstance(img_url, str):
                    # Fazer URL absoluta se necessário
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    elif img_url.startswith("/"):
                        img_url = urljoin(BASE_URL, img_url)
                    elif not img_url.startswith("http"):
                        img_url = urljoin(BASE_URL, "/" + img_url)

                    # Verificar se é uma URL válida de imagem
                    if any(ext in img_url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
                        return img_url

        return None
    except Exception:
        return None


def processar_categorias() -> None:
    """
    Função principal que processa todas as categorias do Soudaki.
    """
    hoje = date.today().isoformat()
    print(f"=== Coletor Soudaki (Webflow) ===")
    print(f"Data da coleta: {hoje}")
    print("-" * 50)

    # Carrega estado existente (para preservar dados de outras lojas e permitir retomada)
    produtos_existentes = {}
    precos_existentes = {}

    if os.path.exists(ARQUIVO_PRODUTOS):
        try:
            with open(ARQUIVO_PRODUTOS, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if isinstance(dados, list):
                    produtos_existentes = {p.get("gtin_ean"): p for p in dados if p.get("gtin_ean")}
        except Exception as e:
            print(f"Erro ao carregar produtos existentes: {e}")

    if os.path.exists(ARQUIVO_PRECOS):
        try:
            with open(ARQUIVO_PRECOS, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if isinstance(dados, list):
                    precos_existentes = {p.get("gtin_ean"): p for p in dados if p.get("gtin_ean")}
        except Exception as e:
            print(f"Erro ao carregar preços existentes: {e}")

    # Estruturas para acumular resultados desta execução
    produtos_nesta_execucao: Dict[str, dict] = {}
    precos_nesta_execucao: Dict[str, dict] = {}
    vistos_execucao: set = set()

    # Estatísticas
    stats = {
        "categorias_processadas": 0,
        "produtos_validos": 0,
        "novos_produtos": 0,
        "novos_precos": 0,
        "ignorados_sem_ean": 0,
        "ignorados_duplicados": 0,
        "ignorados_sem_preco": 0,
        "paginas_processadas": 0
    }

    # Obtém lista de categorias para processar
    categorias = descobrir_categorias_soudaki()
    print(f"Processando {len(categorias)} categorias...")

    for categoria in categorias:
        slug = categoria["slug"]
        secao_nome = categoria["nome"]
        url = categoria["url"]

        print(f"\nProcessando categoria: {secao_nome} ({slug})")
        stats["categorias_processadas"] += 1
        stats["paginas_processadas"] += 1

        # Coleta produtos desta categoria
        produtos_brutos = coletar_produtos_da_pagina(url, secao_nome)

        for produto_data in produtos_brutos:
            ean = produto_data["ean"]

            # Verifica duplicação nesta execução
            if ean in vistos_execucao:
                stats["ignorados_duplicados"] += 1
                continue
            vistos_execucao.add(ean)

            # Preparar dados do produto no formato padrão
            produto_padrao = {
                "gtin_ean": ean,
                "secao": produto_data["secao"],
                "subsecao": produto_data.get("subsecao", ""),
                "nome_completo": produto_data["nome"],
                "marca": produto_data["marca"],
                "apresentacao": produto_data["apresentacao"],
                "imagem_url": produto_data["imagem_url"],
                "data_cadastro": hoje,
            }

            # Preparar dados de preço no formato padrão
            preco_padrao = {
                "gtin_ean": ean,
                "supermercado": "Soudaki",
                "preco_regular": produto_data["preco_regular"],
                "preco_promocional": produto_data["preco_promocional"],
                "em_estoque": produto_data["em_estoque"],
                "data_coleta": hoje,
            }

            # Cadastra produto (se novo)
            if ean not in produtos_existentes:
                produtos_nesta_execucao[ean] = produto_padrao
                stats["novos_produtos"] += 1
            stats["produtos_validos"] += 1

            # Sempre atualiza/registra o preço
            if ean not in precos_existentes:
                precos_nesta_execucao[ean] = preco_padrao
                stats["novos_precos"] += 1

        # Respeitar limite de taxa entre requisições
        sleep_with_jitter(1.5)

    # Merge resultados com existentes
    produtos_finais = {**produtos_existentes, **produtos_nesta_execucao}
    precos_finais = {**precos_existentes, **precos_nesta_execucao}

    # Salva resultados finais
    print("\nSalvando resultados...")
    try:
        with open(ARQUIVO_PRODUTOS, "w", encoding="utf-8") as f:
            json.dump(list(produtos_finais.values()), f, indent=2, ensure_ascii=False)
        print(f"  Produtos salvos: {len(produtos_finais)}")
    except Exception as e:
        print(f"Erro ao salvar produtos: {e}")

    try:
        with open(ARQUIVO_PRECOS, "w", encoding="utf-8") as f:
            json.dump(list(precos_finais.values()), f, indent=2, ensure_ascii=False)
        print(f"  Preços salvos: {len(precos_finais)}")
    except Exception as e:
        print(f"Erro ao salvar preços: {e}")

    # Relatório final
    print("\n" + "=" * 50)
    print("RESULTADOS DA COLETA:")
    print(f"  Categorias processadas: {stats['categorias_processadas']}")
    print(f"  Páginas processadas: {stats['paginas_processadas']}")
    print(f"  Produtos válidos com EAN: {stats['produtos_validos']}")
    print(f"  Novos produtos cadastrados: {stats['novos_produtos']}")
    print(f"  Novos preços coletados: {stats['novos_precos']}")
    print(f"  Ignorados (sem EAN): {stats['ignorados_sem_ean']}")
    print(f"  Ignorados (duplicados nesta execução): {stats['ignorados_duplicados']}")
    print(f"  Ignorados (sem preço): {stats['ignorados_sem_preco']}")
    print(f"  Total de produtos no catálogo: {len(produtos_finais)}")
    print(f"  Total de preços no Soudaki: {len(precos_finais)}")
    print("\nArquivos gerados:")
    print(f"  {ARQUIVO_PRODUTOS}")
    print(f"  {ARQUIVO_PRECOS}")
    print("=" * 50)


if __name__ == "__main__":
    processar_categorias()