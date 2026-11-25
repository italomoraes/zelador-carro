# SPDX-License-Identifier: MIT
"""Testes do envio, da coleta, da gravação do DLT (ferramenta/zelador.py), do
receptor (receptor/receptor.py) e de receptor/abre_dlt.py e abre_salvo.py, de ponta a ponta em
127.0.0.1, sem root.

    python3 -I testes/teste_envio.py

Precisa do `openssl` (os certificados de teste)."""
import base64
import gzip
import http.client
import importlib.util
import json
import os
import random
import shutil
import socket
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


CABECALHO_TCP = ('  sl  local_address                         remote_address                        st tx_queue '
                 'rx_queue tr tm->when retrnsmt   uid  timeout inode\n')


def linha_tcp(porta, estado, v4=False):
    zero = '0' * (8 if v4 else 32)
    return ('   0: %s:%04X %s:0000 %s 00000000:00000000 00:00000000 00000000     0        0 12345 1 '
            '0000000000000000 100 0 0 10 0\n' % (zero, porta, zero, estado))


def tabela(caminho, *linhas):
    with open(caminho + '.tmp', 'w') as f:
        f.write(CABECALHO_TCP + ''.join(linhas))
    os.replace(caminho + '.tmp', caminho)


def gera_dlt(n):
    """Bytes parecidos com DLT: cabeçalho, texto e um pouco de binário."""
    r = random.Random(7)
    partes, total = [], 0
    while total < n:
        p = (b'\x3d\x01\x00\x40MGHS' + ('ACP NAV RouteGuidanceService atualizou %d ' % r.randrange(10 ** 6)).encode()
             + bytes(r.randrange(256) for _ in range(24)))
        partes.append(p)
        total += len(p)
    return b''.join(partes)[:n]


class FalsoDaemon(threading.Thread):
    """Um dlt-daemon de mentira: manda `dados` em pedaços ao primeiro cliente;
    depois `fecha()` (a captura fecha: some o LISTEN) e fecha a porta sem
    derrubar o cliente, como o de verdade. Anota o que o cliente mandou e se
    e quando ele desconectou."""

    def __init__(self, dados, fecha, pedaco=4096, pausa=0.002):
        super().__init__(daemon=True)
        self.dados, self.fecha, self.pedaco, self.pausa = dados, fecha, pedaco, pausa
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind(('127.0.0.1', 0))
        self.srv.listen(1)
        self.porta = self.srv.getsockname()[1]
        self.recebido = b''
        self.fechou_em = self.desconectou_em = None

    def run(self):
        self.srv.settimeout(20)
        try:
            c, _ = self.srv.accept()
        except OSError:
            return
        for i in range(0, len(self.dados), self.pedaco):
            try:
                c.sendall(self.dados[i:i + self.pedaco])
            except OSError:
                break
            time.sleep(self.pausa)
        self.fechou_em = time.time()
        self.fecha()
        self.srv.close()
        c.settimeout(0.2)
        fim = time.time() + 15
        while time.time() < fim:
            try:
                r = c.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                self.desconectou_em = time.time()
                break
            if not r:
                self.desconectou_em = time.time()
                break
            self.recebido += r
        c.close()


def capturas(p):
    return {n for n in os.listdir(p['coleta']) if n.startswith('dlt-')}


def testa_dlt(zelador, receptor, abre_dlt, tmp, conf):
    """Devolve (nome do .txt da captura completa, os bytes mandados)."""
    p = zelador.pastas(conf)
    pasta = os.path.join(tmp, 'dlt')
    os.makedirs(pasta)
    tcp6, tcp4 = os.path.join(pasta, 'tcp6'), os.path.join(pasta, 'tcp')
    antigos = (zelador.TCP_TABELAS, zelador.DLT_PORTA, zelador.DLT_PASSO_S, zelador.DLT_FECHADA_S,
               zelador.DLT_MAX_CRU, zelador.relogio, zelador.captura_dlt)
    zelador.TCP_TABELAS = (tcp6, tcp4)
    zelador.DLT_PASSO_S = 0.1
    zelador.DLT_FECHADA_S = 0.5
    try:
        zelador.DLT_PORTA = 3490
        tabela(tcp6, linha_tcp(3490, '0A'))
        tabela(tcp4)
        ok('dlt: LISTEN na porta 3490 (tcp6) é a captura aberta', zelador.dlt_aberta())
        tabela(tcp6, linha_tcp(3490, '01'), linha_tcp(3491, '0A'))
        ok('uma conexão na 3490 ou outra porta em LISTEN não é', not zelador.dlt_aberta())
        tabela(tcp6)
        tabela(tcp4, linha_tcp(3490, '0A', v4=True))
        ok('no tcp (IPv4) também conta', zelador.dlt_aberta())
        os.unlink(tcp4)
        os.unlink(tcp6)
        ok('sem as tabelas: fechada', not zelador.dlt_aberta())

        dados = gera_dlt(300 << 10)
        d = FalsoDaemon(dados, lambda: tabela(tcp6))
        zelador.DLT_PORTA = d.porta
        tabela(tcp6, linha_tcp(d.porta, '0A'))
        tabela(tcp4)
        d.start()
        caminho = zelador.captura_dlt(conf)
        d.join(20)
        nome = os.path.basename(caminho or '')
        ok('a captura vira um .txt em coleta, sem sobrar .part',
           caminho is not None and os.path.dirname(caminho) == p['coleta'] and nome.endswith('.txt') and
           capturas(p) == {nome})
        ok('0600', caminho is not None and os.stat(caminho).st_mode & 0o777 == 0o600)
        texto = ler(caminho) if caminho else b''
        ok('começa pela linha que diz o que é', texto.startswith(b'# zelador-carro dlt:'))
        dlt, esperado, _ = abre_dlt.abre(caminho) if caminho else (b'', None, [])
        ok('abre_dlt devolve exatamente o que o daemon mandou', dlt == dados and esperado == len(dados))
        ok('o rodapé diz por que parou', b'bytes do DLT, a captura fechou' in texto)
        ok('o zelador não mandou nada ao daemon', d.recebido == b'')
        ok('e desconectou sozinho logo depois de a porta fechar',
           d.desconectou_em is not None and 0.3 <= d.desconectou_em - d.fechou_em <= 4)
        ok('o receptor aceita o nome', bool(receptor.NOME.fullmatch('coleta/' + nome)))
        ok('e o envio vai mandar', ('coleta', nome, caminho) in zelador.prontos(conf))

        antes = capturas(p)
        zelador.DLT_MAX_CRU = 50000
        d = FalsoDaemon(dados, lambda: tabela(tcp6))
        zelador.DLT_PORTA = d.porta
        tabela(tcp6, linha_tcp(d.porta, '0A'))
        d.start()
        c2 = zelador.captura_dlt(conf)
        d.join(20)
        zelador.DLT_MAX_CRU = antigos[4]
        dlt, esperado, _ = abre_dlt.abre(c2) if c2 else (b'', None, [])
        ok('no limite: para, desconecta e guarda o começo',
           dlt == dados[:50000] and esperado == 50000 and b'chegou ao limite' in ler(c2) and
           d.desconectou_em is not None and d.recebido == b'' and len(capturas(p) - antes) == 1)

        antes = capturas(p)
        chamadas = [0]

        def relogio_que_para():
            chamadas[0] += 1
            if chamadas[0] > 6:
                raise SystemExit(0)
            return antigos[5]()

        zelador.relogio = relogio_que_para
        d = FalsoDaemon(dados, lambda: tabela(tcp6), pausa=0.02)
        zelador.DLT_PORTA = d.porta
        tabela(tcp6, linha_tcp(d.porta, '0A'))
        d.start()
        try:
            zelador.captura_dlt(conf)
            parou = False
        except SystemExit:
            parou = True
        zelador.relogio = antigos[5]
        d.join(20)
        novos = sorted(capturas(p) - antes)
        c3 = os.path.join(p['coleta'], novos[0]) if len(novos) == 1 else None
        dlt, esperado, _ = abre_dlt.abre(c3) if c3 and c3.endswith('.txt') else (b'', None, [])
        ok('parado no meio (SIGTERM): fecha o .txt com o que chegou',
           parou and c3 is not None and c3.endswith('.txt') and 0 < len(dlt) < len(dados) and
           dados.startswith(dlt) and esperado == len(dlt) and b'bytes do DLT, parou' in ler(c3) and
           d.desconectou_em is not None)

        comprimido = gzip.compress(dados, 1)
        metade = comprimido[:len(comprimido) // 2 // 57 * 57]
        sobra = os.path.join(p['coleta'], 'dlt-20260101-000000.txt.part')
        # a última linha pela metade, como quando a central desliga no meio de uma escrita
        escreve(sobra, b'# zelador-carro dlt: teste\n# in\xc3\xadcio 2026-01-01T00:00:00Z\n' +
                base64.encodebytes(metade) + base64.encodebytes(comprimido[len(metade):len(metade) + 57])[:30])
        zelador.termina_sobras(conf)
        c4 = sobra[:-len('.part')]
        dlt, esperado, _ = abre_dlt.abre(c4) if os.path.exists(c4) else (b'', None, [])
        ok('sobra .part de uma central que desligou: vira .txt, marcada, e abre até onde chegou',
           not os.path.exists(sobra) and os.path.exists(c4) and b'# cortada' in ler(c4) and
           0 < len(dlt) < len(dados) and dados.startswith(dlt) and esperado is None)

        antes = capturas(p)
        livre = socket.socket()
        livre.bind(('127.0.0.1', 0))
        zelador.DLT_PORTA = livre.getsockname()[1]
        livre.close()
        tabela(tcp6, linha_tcp(zelador.DLT_PORTA, '0A'))
        t0 = time.time()
        r = zelador.captura_dlt(conf)
        ok('a porta aberta que recusa a conexão: desiste logo, sem arquivo',
           r is None and capturas(p) == antes and time.time() - t0 < 5)

        feitas = []
        zelador.captura_dlt = lambda c: feitas.append(1)
        tabela(tcp6, linha_tcp(zelador.DLT_PORTA, '0A'))
        e1 = zelador.passo_dlt(conf, False)
        e2 = zelador.passo_dlt(conf, e1)
        tabela(tcp6)
        e3 = zelador.passo_dlt(conf, e2)
        tabela(tcp6, linha_tcp(zelador.DLT_PORTA, '0A'))
        e4 = zelador.passo_dlt(conf, e3)
        ok('o serviço grava uma vez por abertura da captura',
           (e1, e2, e3, e4) == (True, True, False, True) and len(feitas) == 2)
    finally:
        (zelador.TCP_TABELAS, zelador.DLT_PORTA, zelador.DLT_PASSO_S, zelador.DLT_FECHADA_S,
         zelador.DLT_MAX_CRU, zelador.relogio, zelador.captura_dlt) = antigos

    # o serviço de verdade, como processo: fecha as sobras e espera a captura
    proc_dir = os.path.join(tmp, 'dlt-processo')
    atual = os.path.join(proc_dir, 'current')
    os.makedirs(atual)
    shutil.copy(os.path.join(RAIZ, 'ferramenta', 'zelador.py'), atual)
    conf_p = dict(conf, pasta=os.path.join(proc_dir, 'carro'))
    arq_conf = os.path.join(atual, 'zelador.conf')
    with open(arq_conf, 'w') as f:
        json.dump(conf_p, f)
    pp = zelador.pastas(conf_p)
    escreve(os.path.join(pp['coleta'], 'dlt-20260101-000001.txt.part'), b'# zelador-carro dlt: teste\n')
    proc = subprocess.Popen([sys.executable, '-I', os.path.join(atual, 'zelador.py'), 'dlt', '--conf', arq_conf],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    limite = time.time() + 10
    while time.time() < limite and not os.path.exists(os.path.join(pp['coleta'], 'dlt-20260101-000001.txt')):
        time.sleep(0.1)
    time.sleep(0.5)
    proc.terminate()
    saida = proc.communicate(timeout=10)[0]
    ok('o processo dlt fecha as sobras, espera a captura e sai limpo no SIGTERM',
       os.path.exists(os.path.join(pp['coleta'], 'dlt-20260101-000001.txt')) and
       'esperando a captura do app' in saida and proc.returncode == 0)
    return nome, dados


def testa_salvos(zelador, abre_salvo, tmp, conf):
    """Os arquivos do Salvar logs do Mapas no painel: copiados uma vez cada, sem
    mexer na pasta dele. Devolve (nome do .txt de um deles, o .tar.gz)."""
    p = zelador.pastas(conf)
    moc = os.path.join(tmp, 'moc-saved')
    os.makedirs(moc)
    conf_s = dict(conf, salvos=moc)

    def copias():
        return sorted(n for n in os.listdir(p['coleta']) if n.startswith('salvo-') and n.endswith('.txt'))

    ok('salvos: sem a pasta, nada e estado vazio', zelador.salvos(dict(conf, salvos=os.path.join(tmp, 'nao-ha')), {}) == {})
    ok('salvos: sem a chave na configuração, nada', zelador.salvos(conf, {}) == {})
    random.seed(7)
    a = bytes(random.getrandbits(8) for _ in range(300000))  # mais de um pedaço de leitura
    b = b'segundo arquivo'
    c = b'terceiro'
    escreve(os.path.join(moc, 'woc-logs-20261125T164304Z.tar.gz'), a)
    escreve(os.path.join(moc, 'woc-logs-20261125T170000Z.tar.gz'), b)
    escreve(os.path.join(moc, 'woc-logs-20261125T180000Z.tar.gz'), c)
    escreve(os.path.join(moc, '.woc-logs-20261125T190000Z.tar.gz.part'), b'ainda salvando')
    escreve(os.path.join(moc, 'outro.tar.gz'), b'nao e do salvar logs')
    os.symlink('/etc/hosts', os.path.join(moc, 'woc-logs-20261125T200000Z.tar.gz'))
    escreve(os.path.join(p['coleta'], 'salvo-woc-logs-20261124T000000Z.txt.part'), b'sobra')
    antes_moc = {n: ler(os.path.join(moc, n)) for n in os.listdir(moc) if not os.path.islink(os.path.join(moc, n))}

    estado = zelador.salvos(conf_s, {})
    ok('salvos: 2 por coleta, do mais antigo', copias() == ['salvo-woc-logs-20261125T164304Z.txt',
                                                             'salvo-woc-logs-20261125T170000Z.txt'])
    ok('salvos: o .part, outros nomes e links ficam de fora',
       sorted(estado) == ['woc-logs-20261125T164304Z.tar.gz', 'woc-logs-20261125T170000Z.tar.gz'])
    ok('salvos: a sobra .part nossa sai',
       not os.path.exists(os.path.join(p['coleta'], 'salvo-woc-logs-20261124T000000Z.txt.part')))
    estado = zelador.salvos(conf_s, estado)
    ok('salvos: na coleta seguinte, o terceiro', len(copias()) == 3 and len(estado) == 3)
    estado = zelador.salvos(conf_s, estado)
    ok('salvos: nada copiado de novo', len(copias()) == 3)
    ok('salvos: a pasta do Mapas no painel fica igual',
       {n: ler(os.path.join(moc, n)) for n in os.listdir(moc) if not os.path.islink(os.path.join(moc, n))} == antes_moc)
    txt = os.path.join(p['coleta'], 'salvo-woc-logs-20261125T164304Z.txt')
    ok('salvos: a cópia é 0600', os.stat(txt).st_mode & 0o777 == 0o600)
    dados, fim = abre_salvo.abre(txt)
    ok('abre_salvo: devolve o arquivo igual', dados == a and fim[0] == len(a))

    os.unlink(os.path.join(moc, 'woc-logs-20261125T164304Z.tar.gz'))
    estado = zelador.salvos(conf_s, estado)
    ok('salvos: o que o Mapas no painel apagou sai do estado',
       'woc-logs-20261125T164304Z.tar.gz' not in estado and len(estado) == 2)
    grande = os.path.join(moc, 'woc-logs-20261125T210000Z.tar.gz')
    with open(grande, 'wb') as f:
        f.truncate(zelador.SALVO_MAX + 1)
    estado = zelador.salvos(conf_s, estado)
    ok('salvos: um acima de 16 MB não é copiado, nem tentado de novo',
       len(copias()) == 3 and 'woc-logs-20261125T210000Z.tar.gz' in estado)
    os.unlink(grande)

    escreve(os.path.join(moc, 'woc-logs-20261125T220000Z.tar.gz'), b'vai mudar')
    lido = zelador.os.fstat

    def fstat_que_muda(fd, _chamadas=[0]):
        st = lido(fd)
        _chamadas[0] += 1
        if _chamadas[0] == 2:  # o fstat depois da leitura
            return os.stat_result(st[:8] + (st.st_mtime + 5,) + st[9:])
        return st
    zelador.os.fstat = fstat_que_muda
    try:
        estado = zelador.salvos(conf_s, estado)
    finally:
        zelador.os.fstat = lido
    ok('salvos: mudou durante a leitura, não copia e tenta de novo',
       len(copias()) == 3 and 'woc-logs-20261125T220000Z.tar.gz' not in estado and
       not [n for n in os.listdir(p['coleta']) if n.endswith('.part')])
    estado = zelador.salvos(conf_s, estado)
    ok('salvos: na coleta seguinte, copia', len(copias()) == 4)

    quebrado = os.path.join(tmp, 'quebrado.txt')
    with open(txt, 'rb') as f:
        linhas = f.read().split(b'\n')
    linhas[3] = base64.b64encode(b'x' * 57)
    escreve(quebrado, b'\n'.join(linhas))
    ok('abre_salvo: um que não confere não é gravado',
       abre_salvo.main(['abre_salvo.py', quebrado]) == 1 and not os.path.exists(os.path.join(tmp, 'quebrado.tar.gz')))

    for n in copias():
        if n != 'salvo-woc-logs-20261125T170000Z.txt':
            os.unlink(os.path.join(p['coleta'], n))
    return 'salvo-woc-logs-20261125T170000Z.txt', b


def main():
    tmp = tempfile.mkdtemp(prefix='zelador-teste-')
    try:
        receptor = modulo('receptor', os.path.join(RAIZ, 'receptor', 'receptor.py'))
        zelador = modulo('zelador', os.path.join(RAIZ, 'ferramenta', 'zelador.py'))
        abre_dlt = modulo('abre_dlt', os.path.join(RAIZ, 'receptor', 'abre_dlt.py'))
        abre_salvo = modulo('abre_salvo', os.path.join(RAIZ, 'receptor', 'abre_salvo.py'))
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
        nome_dlt, dados_dlt = testa_dlt(zelador, receptor, abre_dlt, tmp, conf)
        nome_salvo, dados_salvo = testa_salvos(zelador, abre_salvo, tmp, conf)

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
        chegou = os.path.join(casa, 'recebidos', 'coleta', nome_dlt)
        dlt, esperado, _ = abre_dlt.abre(chegou) if os.path.exists(chegou) else (b'', None, [])
        ok('a captura do DLT chega em casa e abre igual', dlt == dados_dlt and esperado == len(dados_dlt))
        r = abre_dlt.main(['abre_dlt.py', chegou]) if os.path.exists(chegou) else 1
        cru = chegou[:-len('.txt')] + '.dlt'
        ok('abre_dlt.py grava o .dlt ao lado', r == 0 and os.path.exists(cru) and ler(cru) == dados_dlt)
        chegou = os.path.join(casa, 'recebidos', 'coleta', nome_salvo)
        r = abre_salvo.main(['abre_salvo.py', chegou]) if os.path.exists(chegou) else 1
        tgz = chegou[:-len('.txt')] + '.tar.gz'
        ok('o Salvar logs chega em casa e abre_salvo.py grava o .tar.gz igual',
           r == 0 and os.path.exists(tgz) and ler(tgz) == dados_salvo)
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
