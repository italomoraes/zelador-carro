# SPDX-License-Identifier: MIT
"""Abre as capturas do DLT que o zelador manda (coleta/dlt-*.txt: o DLT em
gzip, em base64, com linhas "#") e grava o DLT cru ao lado, em <nome>.dlt,
para o DLT Viewer ou outro decodificador.

    python3 -I receptor/abre_dlt.py ~/zelador-carro/recebidos/coleta/dlt-*.txt

Uma captura cortada (a central desligou no meio) abre até onde chegou.
"""
import base64
import binascii
import re
import sys
import zlib

FIM = re.compile(rb'^# fim \S+: (\d+) bytes do DLT')


def abre(caminho):
    """(o DLT cru, os bytes que o rodapé diz ou None, as linhas "#")."""
    comprimido = bytearray()
    esperado, notas = None, []
    with open(caminho, 'rb') as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            if linha.startswith(b'#'):
                notas.append(linha.decode(errors='replace'))
                m = FIM.match(linha)
                if m:
                    esperado = int(m.group(1))
                continue
            try:
                comprimido += base64.b64decode(linha, validate=True)
            except (binascii.Error, ValueError):
                break  # a última linha de uma captura cortada
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    partes = []
    for i in range(0, len(comprimido), 1 << 16):  # em pedaços: um erro no meio guarda o que veio antes
        try:
            partes.append(d.decompress(bytes(comprimido[i:i + (1 << 16)])))
        except zlib.error:
            break
    return b''.join(partes), esperado, notas


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    erros = 0
    for caminho in argv[1:]:
        dlt, esperado, _ = abre(caminho)
        destino = re.sub(r'\.txt$', '', caminho) + '.dlt'
        with open(destino, 'wb') as f:
            f.write(dlt)
        if esperado is None:
            situacao = 'cortada, sem rodapé'
        elif esperado == len(dlt):
            situacao = 'completa'
        else:
            situacao = 'o rodapé diz %d bytes' % esperado
            erros += 1
        print('%s: %d bytes do DLT (%s) -> %s' % (caminho, len(dlt), situacao, destino))
    return 1 if erros else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
