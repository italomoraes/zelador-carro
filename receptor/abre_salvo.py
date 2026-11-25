# SPDX-License-Identifier: MIT
"""Abre os arquivos do "Salvar logs" do Mapas no painel que o zelador manda
(coleta/salvo-*.txt: o .tar.gz em base64, com linhas "#") e grava o .tar.gz
ao lado, conferindo o tamanho e o sha256 do rodapé.

    python3 -I receptor/abre_salvo.py ~/zelador-carro/recebidos/coleta/salvo-*.txt
"""
import base64
import binascii
import hashlib
import re
import sys

FIM = re.compile(rb'^# fim: (\d+) bytes, sha256 ([0-9a-f]{64})$')


def abre(caminho):
    """(o .tar.gz, (bytes, sha256) do rodapé ou None)."""
    dados = bytearray()
    fim = None
    with open(caminho, 'rb') as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            if linha.startswith(b'#'):
                m = FIM.match(linha)
                if m:
                    fim = (int(m.group(1)), m.group(2).decode())
                continue
            try:
                dados += base64.b64decode(linha, validate=True)
            except (binascii.Error, ValueError):
                break
    return bytes(dados), fim


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    erros = 0
    for caminho in argv[1:]:
        dados, fim = abre(caminho)
        if fim is None:
            print('%s: sem rodapé, não gravei' % caminho)
            erros += 1
            continue
        if fim != (len(dados), hashlib.sha256(dados).hexdigest()):
            print('%s: não confere com o rodapé (%d bytes), não gravei' % (caminho, len(dados)))
            erros += 1
            continue
        destino = re.sub(r'\.txt$', '', caminho) + '.tar.gz'
        with open(destino, 'wb') as f:
            f.write(dados)
        print('%s: %d bytes, sha256 confere -> %s' % (caminho, len(dados), destino))
    return 1 if erros else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
