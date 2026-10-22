# -*- coding: utf-8 -*-
"""
Módulo centralizado de CEPs para coleta multi-região.

Este módulo define a lista canônica de CEPs usados para simulação de preços
por região (VTEX simulation API). A lista em recoletar_por_ean.py era um
fallback sequencial (tenta CEPs até um funcionar); este módulo é para o
novo caso de uso multi-CEP onde armazenamos preços por CEP.
"""

CEPS = [
    {"cep": "11060-002", "cidade": "Santos", "estado": "SP"},
    {"cep": "01310-100", "cidade": "São Paulo", "estado": "SP"},
    {"cep": "13010-000", "cidade": "Campinas", "estado": "SP"},
    {"cep": "14010-000", "cidade": "Ribeirão Preto", "estado": "SP"},
    {"cep": "07011-000", "cidade": "Guarulhos", "estado": "SP"},
    {"cep": "18010-000", "cidade": "Sorocaba", "estado": "SP"},
]

CEPA_PADRAO = CEPS[0]  # Santos — fallback default


def ceps_strings() -> list[str]:
    """Retorna lista de strings de CEP (compatibilidade com código legado)."""
    return [c["cep"] for c in CEPS]