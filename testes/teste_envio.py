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


def gira(caminho, geracoes):
    """Como o diário do waze-on-cluster: .N-1 -> .N, ..., .1 -> .2, atual -> .1."""
    for i in range(geracoes - 1, 0, -1):
        if os.path.exists('%s.%d' % (caminho, i)):
            os.replace('%s.%d' % (caminho, i), '%s.%d' % (caminho, i + 1))
    os.replace(caminho, caminho + '.1')


def testa_girados(zelador, tmp):
    jr = os.path.join(tmp, 'jr', 'journal.log')
    escreve(jr + '.2', b'a\n')
    escreve(jr + '.1', b'b\n')
    escreve(jr, b'c\n')
    novo, est = zelador.le_novo(jr, {})
    ok('girados: a primeira vez lê todos, do mais antigo', novo == b'a\nb\nc\n')
    with open(jr, 'ab') as f:
        f.write(b'd\n')
    novo, est = zelador.le_novo(jr, est)
    ok('girados: depois, só o que entrou no atual', novo == b'd\n')
    novo, est = zelador.le_novo(jr, est)
    ok('girados: nada novo, nada lido', novo == b'')
    with open(jr, 'ab') as f:
        f.write(b'e\n')
    gira(jr, 10)
    escreve(jr, b'f\n')
    novo, est = zelador.le_novo(jr, est)
    ok('girou: o resto do antigo e o novo, sem repetir', novo == b'e\nf\n')
    with open(jr, 'ab') as f:
        f.write(b'g\n')
    gira(jr, 10)
    escreve(jr, b'h\n')
    with open(jr, 'ab') as f:
        f.write(b'i\n')
    gira(jr, 10)
    escreve(jr, b'j\n')
    novo, est = zelador.le_novo(jr, est)
    ok('girou duas vezes entre leituras: nada perdido', novo == b'g\nh\ni\nj\n')
    for n in os.listdir(os.path.dirname(jr)):
        os.unlink(os.path.join(os.path.dirname(jr), n))
    escreve(jr + '.1', b'x\n')
    escreve(jr, b'y\n')
    novo, est = zelador.le_novo(jr, est)
    ok('o de antes sumiu: lê todos de novo', novo == b'x\ny\n')
    with open(jr, 'wb') as f:
        f.write(b'z')
    novo, est = zelador.le_novo(jr, est)
    ok('truncado: lido do começo', novo == b'z')
    with open(jr, 'ab') as f:
        f.write(b'123456\n')
    novo, est = zelador.le_novo(jr, est, limite=3)
    novo2, est = zelador.le_novo(jr, est, limite=100)
    ok('com limite: o resto fica para a próxima', novo == b'123' and novo2 == b'456\n')
    sumido = os.path.join(tmp, 'jr', 'nao-existe.log')
    ok('sem o arquivo: nada, e o estado fica', zelador.le_novo(sumido, {'ino': 7, 'pos': 3}) == (b'', {'ino': 7, 'pos': 3}))

    carro = os.path.join(tmp, 'carro-girados')
    conf = {'receptor': '127.0.0.1', 'porta': 1, 'uid': os.getuid(), 'pasta': carro, 'intervalo_s': 1,
            'limite_mb': 10, 'coleta': {'diario': jr}}
    p = zelador.pastas(conf)
    os.makedirs(p['estado'])
    with open(os.path.join(p['estado'], 'coleta.json'), 'w') as f:
        json.dump({'render-log-anterior': {'ino': 1, 'pos': 2}, 'diario': est}, f)
    with open(jr, 'ab') as f:
        f.write(b'pela coleta\n')
    zelador.coleta(conf)
    diarios = [n for n in os.listdir(p['coleta']) if n.startswith('diario-')]
    with open(os.path.join(p['estado'], 'coleta.json')) as f:
        estado = json.load(f)
    ok('coleta: o diário girado vira diario-*.txt',
       len(diarios) == 1 and ler(os.path.join(p['coleta'], diarios[0])) == b'pela coleta\n')
    ok('coleta: o estado de um arquivo que saiu da configuração sai também',
       'render-log-anterior' not in estado and 'diario' in estado)


FALSO_JOURNALCTL = r'''
import json, sys
entradas, args = sys.argv[1], sys.argv[2:]
with open(entradas + '.chamadas', 'a') as f:
    f.write(' '.join(args) + '\n')
linhas = [l for l in open(entradas).read().splitlines() if l]
cursor = [a.split('=', 1)[1] for a in args if a.startswith('--after-cursor=')]
if cursor:
    nomes = [json.loads(l)['__CURSOR'] for l in linhas]
    if cursor[0] not in nomes:
        sys.stderr.write('Failed to seek to cursor\n')
        sys.exit(1)
    linhas = linhas[nomes.index(cursor[0]) + 1:]
for l in linhas:
    print(l)
'''


def testa_uplink(zelador, tmp, conf):
    pasta = os.path.join(tmp, 'uplink')
    os.makedirs(pasta)
    falso = os.path.join(pasta, 'journalctl.py')
    with open(falso, 'w') as f:
        f.write(FALSO_JOURNALCTL)
    entradas = os.path.join(pasta, 'entradas.json')
    boot = os.path.join(pasta, 'boot_id')
    status = os.path.join(pasta, 'status.json')
    antigos = (zelador.JOURNALCTL, zelador.BOOT_ID, zelador.STATUS_UPLINK)
    zelador.JOURNALCTL = [sys.executable, '-I', falso, entradas]
    zelador.BOOT_ID = boot
    zelador.STATUS_UPLINK = status

    def entrada(cursor, segundos, msg):
        return json.dumps({'__CURSOR': cursor, '__REALTIME_TIMESTAMP': str(segundos * 1000000),
                           'SYSLOG_IDENTIFIER': 'mgu-uplink', '_PID': '812', 'MESSAGE': msg})

    def poe(*linhas):
        with open(entradas, 'w') as f:
            f.write('\n'.join(linhas) + '\n')

    def wifi(link):
        with open(status, 'w') as f:
            json.dump({'state': 'searching', 'device': None, 'wifi': {
                'enabled': True, 'link': link, 'backend': 'car-supplicant', 'paused': None, 'freq': 2437,
                'ssid': 'RedeSecreta', 'ip': '192.168.0.9', 'saved': ['RedeSecreta'],
                'networks': [{'ssid': 'RedeSecreta', 'signal': -50}],
                'error': 'could not join "RedeSecreta" (wrong password, or out of range)'}}, f)

    carro = os.path.join(tmp, 'carro-uplink')
    c = dict(conf, pasta=carro, coleta={})
    p = zelador.pastas(c)
    vistos = set()

    def novo_uplink():
        nomes = sorted(n for n in os.listdir(p['coleta']) if n.startswith('uplink-') and n not in vistos)
        vistos.update(nomes)
        return b''.join(ler(os.path.join(p['coleta'], n)) for n in nomes).decode()

    try:
        escreve(boot, b'boot-1\n')
        bytes_msg = list('wifi: found "Casa": joining'.encode())
        poe(entrada('c1', 1, 'wifi: looking for the saved networks on wlan0 (every channel)'),
            entrada('c2', 2, bytes_msg))
        wifi('scanning')
        zelador.coleta(c)
        t = novo_uplink()
        linhas = t.splitlines()
        ok('uplink: as linhas do diário com a hora UTC e o processo',
           len(linhas) == 3 and linhas[0] == '1970-01-01T00:00:01.000000Z mgu-uplink[812]: wifi: looking for '
           'the saved networks on wlan0 (every channel)' and linhas[1].endswith('wifi: found "Casa": joining'))
        ok('uplink: o estado do Wi-Fi numa linha', ' wifi: {' in linhas[2] and '"link": "scanning"' in linhas[2]
           and '"backend": "car-supplicant"' in linhas[2] and '"freq": 2437' in linhas[2])
        ok('uplink: o estado sem nome de rede nem endereço',
           'RedeSecreta' not in linhas[2] and '192.168' not in linhas[2] and 'could not join' in linhas[2])

        poe(entrada('c1', 1, 'um'), entrada('c2', 2, 'dois'), entrada('c3', 3, 'wifi: saved networks paused'))
        zelador.coleta(c)
        t = novo_uplink()
        ok('uplink: depois, só o que veio depois do cursor, e o estado igual não se repete',
           t.splitlines() == ['1970-01-01T00:00:03.000000Z mgu-uplink[812]: wifi: saved networks paused'])
        ok('uplink: pediu pelo cursor', '--after-cursor=c2' in open(entradas + '.chamadas').read().splitlines()[-1])

        poe(entrada('c2', 2, 'dois'), entrada('c9', 4, 'wifi: automatic scans on wlan0 on every channel'))
        wifi('idle')
        zelador.coleta(c)
        t = novo_uplink().splitlines()
        ok('uplink: cursor recusado: lê o boot e deixa de fora o que já foi',
           len(t) == 2 and t[0].endswith('wifi: automatic scans on wlan0 on every channel') and '"link": "idle"' in t[1])

        escreve(boot, b'boot-2\n')
        poe(entrada('d1', 5, 'wifi: using the car\'s wpa_supplicant on wlan0'))
        zelador.coleta(c)
        t = novo_uplink().splitlines()
        ultima = open(entradas + '.chamadas').read().splitlines()[-1]
        ok('uplink: outro boot: do começo, sem cursor',
           len(t) == 1 and t[0].endswith("using the car's wpa_supplicant on wlan0") and '--after-cursor' not in ultima)

        zelador.coleta(c)
        ok('uplink: nada novo, nenhum arquivo', novo_uplink() == '')
        zelador.JOURNALCTL = [os.path.join(pasta, 'nao-existe')]
        os.unlink(status)
        zelador.coleta(c)
        ok('uplink: sem journalctl e sem o status, a coleta segue', novo_uplink() == '')
    finally:
        zelador.JOURNALCTL, zelador.BOOT_ID, zelador.STATUS_UPLINK = antigos


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

        testa_girados(zelador, tmp)
        testa_uplink(zelador, tmp, conf)

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
