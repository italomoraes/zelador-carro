# SPDX-License-Identifier: MIT
"""Testes do envio, da coleta (ferramenta/zelador.py) e do receptor
(receptor/receptor.py), de ponta a ponta em 127.0.0.1, sem root.

    python3 -I testes/teste_envio.py

Precisa do `openssl` (os certificados de teste)."""
import http.client
import importlib.util
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
falhas = []


def ok(o_que, deu):
    print('%s %s' % ('ok  ' if deu else 'FALHA', o_que), flush=True)
    if not deu:
        falhas.append(o_que)


def modulo(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def certificado(pasta, ip):
    os.makedirs(pasta, exist_ok=True)
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '30',
                    '-subj', '/CN=teste', '-addext', 'subjectAltName=IP:' + ip,
                    '-keyout', os.path.join(pasta, 'receptor.key'), '-out', os.path.join(pasta, 'receptor.pem')],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def sobe(receptor, pasta):
    srv = receptor.servidor(pasta, 0, '127.0.0.1')
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def escreve(caminho, conteudo, idade=0):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, 'wb') as f:
        f.write(conteudo)
    if idade:
        t = time.time() - idade
        os.utime(caminho, (t, t))


def ler(caminho):
    with open(caminho, 'rb') as f:
        return f.read()


def main():
    tmp = tempfile.mkdtemp(prefix='zelador-teste-')
    try:
        receptor = modulo('receptor', os.path.join(RAIZ, 'receptor', 'receptor.py'))
        zelador = modulo('zelador', os.path.join(RAIZ, 'ferramenta', 'zelador.py'))
        casa = os.path.join(tmp, 'casa')
        certificado(casa, '127.0.0.1')
        srv = sobe(receptor, casa)
        porta = srv.server_address[1]
        carro = os.path.join(tmp, 'carro')
        conf = {'receptor': '127.0.0.1', 'porta': porta, 'uid': os.getuid(), 'pasta': carro, 'intervalo_s': 1,
                'limite_mb': 10, 'coleta': {'mapas-log': os.path.join(tmp, 'woc.log')}}
        p = zelador.pastas(conf)
        for d in p.values():
            os.makedirs(d, exist_ok=True)

        cid = zelador.carro_id(p['estado'])
        ok('o id do carro é sorteado e guardado 0600',
           len(cid) == 64 and os.stat(os.path.join(p['estado'], 'carro.id')).st_mode & 0o777 == 0o600)
        ok('e é o mesmo da próxima vez', zelador.carro_id(p['estado']) == cid)

        escreve(os.path.join(p['escuta'], 'escuta-b.txt'), b'segundo\n', idade=10)
        escreve(os.path.join(p['escuta'], 'escuta-a.txt'), b'primeiro\n', idade=20)
        escreve(os.path.join(p['escuta'], 'escuta-c.part'), b'ainda gravando\n')
        escreve(os.path.join(p['coleta'], 'resumo-x.txt.tmp'), b'pela metade\n')
        lista = zelador.prontos(conf)
        ok('prontos: só .txt, do mais antigo', [n for _, n, _ in lista] == ['escuta-a.txt', 'escuta-b.txt'])

        ctx = zelador.contexto(os.path.join(casa, 'receptor.pem'))
        sub, nome, caminho = lista[0]
        ok('manda: o receptor confirma', zelador.manda(conf, ctx, cid, sub, nome, caminho))
        recebido = os.path.join(casa, 'recebidos', 'escuta', 'escuta-a.txt')
        ok('o conteúdo chega igual', os.path.exists(recebido) and ler(recebido) == b'primeiro\n')
        ok('e o do carro é apagado', not os.path.exists(caminho))
        ok('o receptor guarda o id do primeiro carro', ler(os.path.join(casa, 'carro.id')).strip() == cid.encode())

        escreve(caminho, b'primeiro\n')
        ok('o mesmo arquivo de novo: confirmado sem duplicar',
           zelador.manda(conf, ctx, cid, sub, nome, caminho) and not os.path.exists(caminho) and
           sorted(os.listdir(os.path.dirname(recebido))) == ['escuta-a.txt'])
        escreve(caminho, b'outro conteudo\n')
        zelador.manda(conf, ctx, cid, sub, nome, caminho)
        nomes = sorted(os.listdir(os.path.dirname(recebido)))
        ok('mesmo nome, outro conteúdo: guardado ao lado', len(nomes) == 2 and ler(recebido) == b'primeiro\n')

        outro = 'f' * 64
        b = os.path.join(p['escuta'], 'escuta-b.txt')
        ok('outro carro: recusado, e o arquivo fica', not zelador.manda(conf, ctx, outro, 'escuta', 'escuta-b.txt', b)
           and os.path.exists(b))

        con = http.client.HTTPSConnection('127.0.0.1', porta, context=ctx, timeout=10)
        con.request('POST', '/arquivo', body=b'x', headers={'X-Zelador-Carro': cid, 'X-Zelador-Nome': '../fora.txt',
                                                           'X-Zelador-Sha256': 'a' * 64})
        r = con.getresponse()
        r.read()
        con.close()
        ok('um nome com caminho: 400', r.status == 400 and not os.path.exists(os.path.join(casa, 'fora.txt')))
        con = http.client.HTTPSConnection('127.0.0.1', porta, context=ctx, timeout=10)
        con.request('POST', '/arquivo', body=b'abc', headers={'X-Zelador-Carro': cid,
                                                             'X-Zelador-Nome': 'escuta/escuta-z.txt',
                                                             'X-Zelador-Sha256': 'a' * 64})
        r = con.getresponse()
        r.read()
        con.close()
        ok('sha256 que não confere: 400, nada gravado',
           r.status == 400 and not os.path.exists(os.path.join(casa, 'recebidos', 'escuta', 'escuta-z.txt')))

        falso = os.path.join(tmp, 'falso')
        certificado(falso, '127.0.0.1')
        shutil.copy(os.path.join(casa, 'carro.id'), falso)
        srv2 = sobe(receptor, falso)
        conf2 = dict(conf, porta=srv2.server_address[1])
        try:
            zelador.manda(conf2, ctx, cid, 'escuta', 'escuta-b.txt', b)
            deu = False
        except ssl.SSLCertVerificationError:
            deu = True
        ok('um receptor com outro certificado: o envio recusa', deu and os.path.exists(b))
        ip2 = os.path.join(tmp, 'ip2')
        certificado(ip2, '127.0.0.2')
        srv3 = sobe(receptor, ip2)
        conf3 = dict(conf, porta=srv3.server_address[1])
        try:
            zelador.manda(conf3, zelador.contexto(os.path.join(ip2, 'receptor.pem')), cid, 'escuta',
                          'escuta-b.txt', b)
            deu = False
        except ssl.SSLCertVerificationError:
            deu = True
        ok('o certificado de outro IP: o envio recusa', deu)

        # coleta
        woc = conf['coleta']['mapas-log']
        escreve(woc, b'linha 1\n')
        zelador.coleta(conf)
        col = sorted(os.listdir(p['coleta']))
        logs = [n for n in col if n.startswith('mapas-log-') and n.endswith('.txt')]
        resumos = [n for n in col if n.startswith('resumo-') and n.endswith('.txt')]
        ok('coleta: o log e um resumo', len(logs) == 1 and len(resumos) == 1 and
           ler(os.path.join(p['coleta'], logs[0])) == b'linha 1\n')
        ok('o resumo diz as pastas', b'escuta: ' in ler(os.path.join(p['coleta'], resumos[0])))
        with open(woc, 'ab') as f:
            f.write(b'linha 2\n')
        time.sleep(1.1)
        zelador.coleta(conf)
        col = sorted(os.listdir(p['coleta']))
        logs = sorted(n for n in col if n.startswith('mapas-log-') and n.endswith('.txt'))
        ok('depois, só o que entrou de novo', len(logs) == 2 and ler(os.path.join(p['coleta'], logs[1])) == b'linha 2\n')
        ok('o resumo sem mudança não se repete',
           len([n for n in col if n.startswith('resumo-') and n.endswith('.txt')]) == 1)
        os.unlink(woc)
        escreve(woc, b'girou\n')
        time.sleep(1.1)
        zelador.coleta(conf)
        logs = sorted(n for n in os.listdir(p['coleta']) if n.startswith('mapas-log-') and n.endswith('.txt'))
        ok('o log girou: lido do começo', len(logs) == 3 and ler(os.path.join(p['coleta'], logs[2])) == b'girou\n')

        # o envio de verdade, como processo
        atual = os.path.join(tmp, 'current')
        os.makedirs(atual)
        shutil.copy(os.path.join(RAIZ, 'ferramenta', 'zelador.py'), atual)
        shutil.copy(os.path.join(casa, 'receptor.pem'), atual)
        arq_conf = os.path.join(atual, 'zelador.conf')
        with open(arq_conf, 'w') as f:
            json.dump(conf, f)
        escreve(os.path.join(p['escuta'], 'escuta-d.txt'), b'pelo processo\n')
        proc = subprocess.Popen([sys.executable, '-I', os.path.join(atual, 'zelador.py'), 'envio', '--conf', arq_conf],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        limite = time.time() + 15
        while time.time() < limite and zelador.prontos(conf):
            time.sleep(0.2)
        restantes = zelador.prontos(conf)
        proc.terminate()
        saida = proc.communicate(timeout=10)[0]
        ok('o processo de envio manda tudo o que está pronto', not restantes and
           ler(os.path.join(casa, 'recebidos', 'escuta', 'escuta-d.txt')) == b'pelo processo\n')
        ok('e diz que alcançou o receptor', 'receptor alcançado' in saida and 'mandou' in saida)
        srv.shutdown()
        srv.server_close()
        escreve(os.path.join(p['escuta'], 'escuta-e.txt'), b'sem receptor\n')
        proc = subprocess.Popen([sys.executable, '-I', os.path.join(atual, 'zelador.py'), 'envio', '--conf', arq_conf],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        time.sleep(3)
        proc.terminate()
        saida = proc.communicate(timeout=10)[0]
        ok('sem receptor: avisa uma vez e guarda o arquivo',
           saida.count('fora do alcance') == 1 and os.path.exists(os.path.join(p['escuta'], 'escuta-e.txt')))

        conf_errada = dict(conf, uid=os.getuid() + 1)
        try:
            zelador.envio(conf_errada)
            deu = False
        except SystemExit as e:
            deu = 'uid' in str(e)
        ok('o envio não roda com outro uid sem ser root', deu)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('FALHOU: %d' % len(falhas) if falhas else 'tudo ok')
    return 1 if falhas else 0


if __name__ == '__main__':
    sys.exit(main())
