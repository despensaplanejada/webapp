"""
Script simples para testar a conexao com o banco de dados Turso LibSQL.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Carrega variaveis do .env local se existir
load_dotenv()

try:
    import libsql_client
except ImportError:
    print("ERRO: Pacote 'libsql-client' nao encontrado. Instale com: pip install libsql-client")
    sys.exit(1)

url = os.environ.get("TURSO_DATABASE_URL")
token = os.environ.get("TURSO_AUTH_TOKEN")

if not url or not token:
    print("ERRO: Variaveis TURSO_DATABASE_URL ou TURSO_AUTH_TOKEN nao configuradas!")
    print("Defina-as no arquivo .env ou no seu ambiente.")
    sys.exit(1)

# Normaliza URL
url = url.strip().strip("'\"")
token = token.strip().strip("'\"")
if url.startswith("libsql://"):
    url = "https://" + url[len("libsql://"):]

print(f"Tentando conectar ao Turso: {url[:30]}...")

try:
    client = libsql_client.create_client_sync(url=url, auth_token=token)
    
    # 1. Testar consulta simples
    rs_lojas = client.execute("SELECT id, chave, nome FROM lojas;")
    print("\n[OK] Conexao estabelecida com sucesso!")
    print("\nLojas ativas no banco:")
    for row in rs_lojas.rows:
        print(f"  - [{row[0]}] {row[1]}: {row[2]}")

    # 2. Total de produtos e precos
    rs_prod = client.execute("SELECT COUNT(*) FROM produtos;")
    rs_prec = client.execute("SELECT COUNT(*) FROM precos WHERE preco_promocional IS NOT NULL;")
    print(f"\nEstatisticas do Banco Turso:")
    print(f"  - Total de Produtos: {rs_prod.rows[0][0]:,}")
    print(f"  - Total de Precos Ativos: {rs_prec.rows[0][0]:,}")

    client.close()
    print("\n[STATUS] Turso esta 100% OPERACIONAL e pronto para producao!")

except Exception as err:
    print(f"\n[FALHA] Nao foi possivel consultar o Turso: {err}")
