import os

from dados_prototipo.config import DB_ACESSO_PATH, DB_DADOS_PATH
from dados_prototipo.funcoes.gerar_banco import gerar_banco
from dados_prototipo.funcoes.gerar_acesso import gerar_acesso
from dados_prototipo.funcoes.verificar_consistencia import verificar_consistencia

if __name__ == "__main__":
    gerar_banco()    # dados.db   (predição)
    gerar_acesso()   # acesso.db  (login e permissões)

    if os.path.exists(DB_DADOS_PATH) and os.path.exists(DB_ACESSO_PATH):
        problemas = verificar_consistencia()
        if problemas:
            print("\nINCONSISTÊNCIAS entre dados.db e acesso.db:")
            for p in problemas:
                print("  -", p)
        else:
            print("\nConferência dados.db x acesso.db: tudo consistente.")
