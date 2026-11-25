# SPDX-License-Identifier: MIT
"""zelador-carro: manda ao computador de casa o que a escuta e a coleta gravam.

    python3 -I zelador.py envio  [--conf ARQ]   o envio (começa root, larga o root)
    python3 -I zelador.py coleta [--conf ARQ]   a coleta (root, pelo timer)
    python3 -I zelador.py dlt    [--conf ARQ]   grava a captura do DLT (root, serviço)

Envio: como root, só prepara as pastas (donas do uid do envio, 0700); larga o
root (uid e gid do envio, sem grupos) antes de abrir qualquer conexão e
confere que não o recupera. A cada `intervalo_s`, se há arquivos prontos
(.txt) em dados/escuta e dados/coleta, conecta ao receptor por HTTPS,
conferindo o certificado dele (receptor.pem, ao lado deste arquivo: o único
aceito, com o IP do receptor), e manda um a um, do mais antigo: o conteúdo
comprimido, o nome e o sha256. Apaga cada um só depois que o receptor
confirma o mesmo sha256. Sem receptor (o carro longe de casa), tenta de novo
no próximo ciclo. O carro se apresenta com um id sorteado na primeira vez
(estado/carro.id); o receptor só aceita o primeiro id que vê.

Coleta, cada parte num .txt em dados/coleta, do dono do envio:
- o que entrou de novo nos arquivos de `coleta` da configuração: os logs do
  Mapas no painel e do cluster-render e o diário que o waze-on-cluster guarda
  na RAM (o CarPlay, o Android Auto, o systemd e o kernel, Wi-Fi incluído).
  Cada arquivo é seguido pelo inode quando gira (arquivo -> arquivo.1 -> ...
  -> arquivo.9), então o que entrou antes do giro não se perde nem se repete;
- o diário do mgu-uplink (as buscas e conexões do Wi-Fi da loja) desde a
  última coleta, pelo cursor do journalctl. O diário do sistema na central é
  volátil e curto (uns 4 min), por isso a coleta de cada minuto;
- o estado do Wi-Fi da loja (status.json do mgu-uplink, sem nomes de rede),
  quando muda;
- um resumo da central (hora, tempo ligado, carga, memória, espaço, versões
  das ferramentas, estado dos serviços do zelador e da internet), quando as
  ferramentas, os serviços ou a internet mudam, e a cada 30 min.
Só lê o sistema; escreve só na pasta do zelador.

DLT: o botão "Iniciar captura" do Mapas no painel abre, por até 5 min, a
porta do dlt-daemon (3490), com os logs dos programas da BMW (o CarPlay, o
Bluetooth, o Android Auto...) em INFO; fora disso o DLT fica desligado. O
serviço olha a cada 2 s se a porta abriu; quando abre, conecta em 127.0.0.1
e grava tudo o que chega num .txt em dados/coleta (o DLT em gzip, em base64,
com o começo, o fim e o tamanho em linhas "#"), até 3 s depois de a porta
fechar, ou até os limites. Só lê: nunca manda nada ao daemon nem muda o
nível dos logs. Lê sem parar, com um buffer grande, porque o daemon espera o
cliente que não lê (TimeOutOnSend = -1). Em casa, receptor/abre_dlt.py
devolve o DLT cru.

A internet da central (mgu-uplink) só deixa sair os uids registrados: o do
envio está no component.json ("internet", "uids"); o root não sai.
"""
import base64
import gzip
import hashlib
import http.client
import json
import os
import re
import secrets
import signal
import socket
import ssl
import subprocess
import sys
import time
import zlib

AQUI = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(AQUI, 'zelador.conf')
LIMITE_LEITURA = 4 << 20  # por arquivo de coleta (com os girados), por vez
RESUMO_S = 30 * 60  # um resumo sem mudança nas ferramentas, serviços e internet
GIRADOS = 9  # arquivo.1 a arquivo.9 (o diário do waze-on-cluster guarda 10 arquivos)
JOURNALCTL = ['journalctl']
UNIDADE_UPLINK = 'mgu-uplink.service'
STATUS_UPLINK = '/run/mgu-uplink/status.json'
BOOT_ID = '/proc/sys/kernel/random/boot_id'
LIMITE_DIARIO = 5000  # linhas do diário do uplink por vez
CAMPOS_WIFI = ('enabled', 'link', 'backend', 'paused', 'freq', 'allow5ghz', 'fiveOnly', 'scanning', 'signal',
               'error')
ESTADO_FIXO = ('resumo', 'resumo_quando', 'uplink', 'wifi')  # o resto do estado são os arquivos de `coleta`
DLT_PORTA = 3490  # a que a captura do app abre no dlt-daemon
TCP_TABELAS = ('/proc/net/tcp6', '/proc/net/tcp')  # o daemon ouve em :::3490
DLT_PASSO_S = 2  # de quanto em quanto tempo olha se a captura abriu
DLT_TENTATIVAS = 3  # conexões por captura aberta
DLT_FECHADA_S = 3  # depois que a porta fecha, ainda lê esse tempo e desconecta
DLT_MAX_S = 6 * 60  # a captura do app dura até 5 min
DLT_MAX_CRU = 96 << 20  # bytes do DLT por captura (a de 19/11 teve 60 MB em 5 min)
DLT_MAX_ARQ = 32 << 20  # o .txt (gzip em base64); o receptor aceita até 64 MB
DLT_BUFFER = 8 << 20  # folga no buffer de recepção, para o daemon nunca esperar por nós
RCVBUFFORCE = getattr(socket, 'SO_RCVBUFFORCE', 33 if sys.platform.startswith('linux') else None)


def log(msg):
    print('zelador-carro: ' + msg, flush=True)


def le_conf(caminho):
    with open(caminho) as f:
        c = json.load(f)
    for k in ('receptor', 'porta', 'uid', 'pasta', 'intervalo_s', 'limite_mb', 'coleta'):
        if k not in c:
            raise SystemExit('zelador-carro: %s sem "%s"' % (caminho, k))
    if not isinstance(c['uid'], int) or c['uid'] <= 0:
        raise SystemExit('zelador-carro: uid inválido')
    return c


def pastas(conf):
    base = conf['pasta']
    return {
        'dados': os.path.join(base, 'dados'),
        'escuta': os.path.join(base, 'dados', 'escuta'),
        'coleta': os.path.join(base, 'dados', 'coleta'),
        'estado': os.path.join(base, 'estado'),
    }


def prepara_pastas(conf):
    """Como root: as pastas do zelador, do uid do envio, 0700."""
    uid = conf['uid']
    base = conf['pasta']
    os.makedirs(base, exist_ok=True)
    modo = os.stat(base).st_mode & 0o7777
    if not modo & 0o001:
        os.chmod(base, modo | 0o001)  # só atravessar
    p = pastas(conf)
    for nome in ('dados', 'escuta', 'coleta', 'estado'):
        os.makedirs(p[nome], mode=0o700, exist_ok=True)
        os.chown(p[nome], uid, uid)
        os.chmod(p[nome], 0o700)
    for nome in ('escuta', 'coleta', 'estado'):
        for n in os.listdir(p[nome]):
            c = os.path.join(p[nome], n)
            if os.path.isfile(c) and not os.path.islink(c):
                os.chown(c, uid, uid)
                os.chmod(c, 0o600)


def larga_root(uid):
    os.setgroups([])
    os.setgid(uid)
    os.setuid(uid)
    try:
        os.setuid(0)
    except PermissionError:
        pass
    else:
        raise SystemExit('zelador-carro: o root voltou depois de largado')
    if (os.getuid(), os.geteuid(), os.getgid(), os.getegid()) != (uid, uid, uid, uid) or os.getgroups():
        raise SystemExit('zelador-carro: não largou o root')


def carro_id(estado):
    caminho = os.path.join(estado, 'carro.id')
    try:
        with open(caminho) as f:
            cid = f.read().strip()
        if len(cid) == 64 and all(c in '0123456789abcdef' for c in cid):
            return cid
    except FileNotFoundError:
        pass
    cid = secrets.token_hex(32)
    tmp = caminho + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(cid + '\n')
    os.replace(tmp, caminho)
    return cid


def prontos(conf):
    """(sub, nome, caminho) dos .txt de escuta e coleta, do mais antigo."""
    p = pastas(conf)
    achados = []
    for sub in ('escuta', 'coleta'):
        try:
            nomes = os.listdir(p[sub])
        except FileNotFoundError:
            continue
        for n in nomes:
            c = os.path.join(p[sub], n)
            if n.endswith('.txt') and os.path.isfile(c) and not os.path.islink(c):
                try:
                    achados.append((os.stat(c).st_mtime, sub, n, c))
                except FileNotFoundError:
                    pass
    achados.sort()
    return [(s, n, c) for _, s, n, c in achados]


def contexto(cert):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(cafile=cert)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def manda(conf, ctx, cid, sub, nome, caminho):
    """True se o receptor confirmou e o arquivo foi apagado."""
    with open(caminho, 'rb') as f:
        dados = f.read()
    sha = hashlib.sha256(dados).hexdigest()
    corpo = gzip.compress(dados, 6)
    con = http.client.HTTPSConnection(conf['receptor'], conf['porta'], context=ctx, timeout=20)
    try:
        con.request('POST', '/arquivo', body=corpo, headers={
            'Content-Type': 'application/octet-stream',
            'X-Zelador-Carro': cid,
            'X-Zelador-Nome': sub + '/' + nome,
            'X-Zelador-Sha256': sha,
            'X-Zelador-Gzip': '1',
        })
        r = con.getresponse()
        resposta = r.read(4096)
    finally:
        con.close()
    try:
        ok = r.status == 200 and json.loads(resposta.decode()).get('sha256') == sha
    except ValueError:
        ok = False
    if not ok:
        log('o receptor recusou %s/%s: %d %s' % (sub, nome, r.status, resposta[:200].decode(errors='replace')))
        return False
    os.unlink(caminho)
    return True


def envio(conf):
    if os.geteuid() == 0:
        prepara_pastas(conf)
        larga_root(conf['uid'])
    elif os.geteuid() != conf['uid']:
        raise SystemExit('zelador-carro: o envio roda como root ou como o uid %d' % conf['uid'])
    p = pastas(conf)
    cid = carro_id(p['estado'])
    ctx = contexto(os.path.join(AQUI, 'receptor.pem'))
    log('envio: uid %d, receptor %s:%d, a cada %d s' % (os.getuid(), conf['receptor'], conf['porta'],
                                                       conf['intervalo_s']))
    situacao = None
    while True:
        lista = prontos(conf)
        mandados = 0
        tamanho = 0
        for sub, nome, caminho in lista:
            try:
                t = os.path.getsize(caminho)
                if not manda(conf, ctx, cid, sub, nome, caminho):
                    break
                mandados += 1
                tamanho += t
                if situacao != 'alcancado':
                    situacao = 'alcancado'
                    log('receptor alcançado')
            except FileNotFoundError:
                continue
            except (OSError, ssl.SSLError, http.client.HTTPException) as e:
                motivo = '%s: %s' % (type(e).__name__, e)
                if situacao != motivo:
                    situacao = motivo
                    log('receptor fora do alcance (%s); tento de novo a cada %d s' % (motivo, conf['intervalo_s']))
                break
        if mandados:
            log('mandou %d arquivo(s), %d KB' % (mandados, (tamanho + 1023) // 1024))
        time.sleep(conf['intervalo_s'])


def grava_coleta(conf, nome, conteudo):
    """Um .txt em dados/coleta, do dono do envio, 0600."""
    p = pastas(conf)
    os.makedirs(p['coleta'], mode=0o700, exist_ok=True)
    quando = time.strftime('%Y%m%d-%H%M%S', time.gmtime())
    base = os.path.join(p['coleta'], '%s-%s' % (nome, quando))
    caminho = base + '.txt'
    i = 1
    while os.path.exists(caminho):
        caminho = '%s-%d.txt' % (base, i)
        i += 1
    tmp = caminho + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(conteudo)
    if os.geteuid() == 0:
        os.chown(tmp, conf['uid'], conf['uid'])
    os.replace(tmp, caminho)


def limpa_coleta(conf):
    """Os mais antigos de dados/coleta saem enquanto ela passa da metade do limite."""
    p = pastas(conf)
    limite = conf['limite_mb'] << 19
    try:
        nomes = sorted(n for n in os.listdir(p['coleta']) if n.endswith('.txt'))
    except FileNotFoundError:
        return
    tam = {n: os.path.getsize(os.path.join(p['coleta'], n)) for n in nomes}
    total = sum(tam.values())
    for n in sorted(nomes, key=lambda n: os.path.getmtime(os.path.join(p['coleta'], n))):
        if total <= limite:
            break
        os.unlink(os.path.join(p['coleta'], n))
        total -= tam[n]


def le_arquivo(caminho, limite=1 << 16):
    try:
        with open(caminho, 'rb') as f:
            return f.read(limite).decode(errors='replace')
    except OSError:
        return ''


def geracoes(caminho):
    """O arquivo e os girados dele, do mais antigo ao atual: [(caminho, stat)]."""
    achados = []
    for c in ['%s.%d' % (caminho, i) for i in range(GIRADOS, 0, -1)] + [caminho]:
        try:
            achados.append((c, os.stat(c)))
        except OSError:
            pass
    return achados


def le_novo(caminho, antes, limite=LIMITE_LEITURA):
    """O que entrou em `caminho` desde `antes` ({'ino', 'pos'}), até `limite`
    bytes, e o novo estado. O arquivo de antes é achado pelo inode entre o
    atual e os girados, e o que veio depois dele é lido inteiro. Sem ele (a
    primeira vez, ou girou além do último), lê todos, do mais antigo."""
    gens = geracoes(caminho)
    inicio, pos = 0, 0
    for i, (_, st) in enumerate(gens):
        if st.st_ino == antes.get('ino'):
            inicio, pos = i, antes.get('pos', 0)
            if st.st_size < pos:  # truncado
                pos = 0
            break
    partes, lidos, estado = [], 0, antes
    for c, st in gens[inicio:]:
        if lidos >= limite:
            break
        try:
            with open(c, 'rb') as f:
                if os.fstat(f.fileno()).st_ino != st.st_ino:
                    break  # girou agora: o resto fica para a próxima vez
                f.seek(pos)
                pedaco = f.read(limite - lidos)
        except OSError:
            break
        partes.append(pedaco)
        lidos += len(pedaco)
        estado = {'ino': st.st_ino, 'pos': pos + len(pedaco)}
        pos = 0
    return b''.join(partes), estado


def hora_utc(us):
    s, resto = divmod(int(us), 1000000)
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(s)) + '.%06dZ' % resto


def mensagem(e):
    m = e.get('MESSAGE', '')
    if isinstance(m, list):  # o journalctl manda como lista de bytes o que não é texto
        try:
            m = bytes(m).decode(errors='replace')
        except (TypeError, ValueError):
            m = repr(m)
    return str(m).replace('\n', ' ')


def diario_uplink(antes):
    """As linhas novas do diário do mgu-uplink desde `antes` ({'boot',
    'cursor', 'us'}) e o novo estado. Se o journalctl recusa o cursor, lê o
    boot todo e deixa de fora o que não é mais novo que a última linha lida."""
    boot = le_arquivo(BOOT_ID).strip()
    mesmo_boot = antes.get('boot') == boot and antes.get('cursor')
    base = JOURNALCTL + ['-o', 'json', '--no-pager', '-u', UNIDADE_UPLINK]
    tentativas = [(base + ['--after-cursor=' + antes['cursor'], '-b'], 0)] if mesmo_boot else []
    tentativas.append((base + ['-b'], antes.get('us', 0) if mesmo_boot else 0))
    for cmd, desde in tentativas:
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return b'', antes
        if r.returncode == 0:
            break
    else:
        return b'', antes
    linhas = []
    estado = dict(antes, boot=boot) if mesmo_boot else {'boot': boot}
    for bruta in r.stdout.splitlines()[-LIMITE_DIARIO:]:
        try:
            e = json.loads(bruta)
            us = int(e.get('__REALTIME_TIMESTAMP', 0))
        except (ValueError, TypeError, AttributeError):
            continue
        if us <= desde:
            continue
        quem = e.get('SYSLOG_IDENTIFIER') or e.get('_COMM') or UNIDADE_UPLINK
        pid = e.get('_PID') or e.get('SYSLOG_PID')
        linhas.append('%s %s%s: %s\n' % (hora_utc(us), quem, '[%s]' % pid if pid else '', mensagem(e)))
        estado = {'boot': boot, 'cursor': e.get('__CURSOR'), 'us': us}
    return ''.join(linhas).encode(), estado


def estado_wifi():
    """O estado do Wi-Fi da loja (status.json do mgu-uplink) em uma linha, sem
    nomes de rede nem endereços; None sem o arquivo."""
    try:
        with open(STATUS_UPLINK) as f:
            s = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(s, dict):
        return None
    w = s.get('wifi') if isinstance(s.get('wifi'), dict) else {}
    d = s.get('device') if isinstance(s.get('device'), dict) else {}
    campos = {'state': s.get('state'), 'device': d.get('kind')}
    campos.update((k, w[k]) for k in CAMPOS_WIFI if k in w)
    if isinstance(campos.get('error'), str):  # "could not join "<rede>" ...": sem o nome
        campos['error'] = re.sub(r'"(?:[^"\\]|\\.)*"', '"…"', campos['error'])
    return json.dumps(campos, sort_keys=True, ensure_ascii=False)


def resumo(conf):
    linhas = []
    try:
        segundos = float(le_arquivo('/proc/uptime').split()[0])
        linhas.append('ligada há %d min' % (segundos // 60))
    except (IndexError, ValueError):
        pass
    linhas.append('carga: ' + le_arquivo('/proc/loadavg').strip())
    mem = {}
    for linha in le_arquivo('/proc/meminfo').splitlines():
        k, _, v = linha.partition(':')
        mem[k] = v.strip()
    linhas.append('memória: total %s, disponível %s' % (mem.get('MemTotal', '?'), mem.get('MemAvailable', '?')))
    try:
        st = os.statvfs('/var/opt')
        linhas.append('/var/opt: %d MB livres de %d MB' % (st.f_bavail * st.f_frsize >> 20,
                                                           st.f_blocks * st.f_frsize >> 20))
    except OSError:
        pass
    versoes = []
    try:
        for n in sorted(os.listdir('/var/opt')):
            alvo = os.path.join('/var/opt', n, 'current')
            if os.path.islink(alvo):
                versoes.append('%s %s' % (n, os.path.basename(os.readlink(alvo))))
    except OSError:
        pass
    linhas.append('ferramentas: ' + ', '.join(versoes))
    unidades = ['zelador-carro-escuta.service', 'zelador-carro-envio.service', 'zelador-carro-coleta.timer',
                'zelador-carro-dlt.service', 'waze-on-cluster.service', 'waze-on-cluster-journal.service',
                'mgu-uplink.service']
    try:
        r = subprocess.run(['systemctl', 'is-active'] + unidades, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=20, universal_newlines=True)
        estados = r.stdout.split()
        linhas.append('serviços: ' + ', '.join('%s %s' % (u, e) for u, e in zip(unidades, estados)))
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        with open('/run/mgu-uplink/status.json') as f:
            s = json.load(f)
        linhas.append('internet: %s' % json.dumps({k: s.get(k) for k in ('state', 'kind', 'online') if k in s},
                                                 ensure_ascii=False))
    except (OSError, ValueError):
        pass
    p = pastas(conf)
    for sub in ('escuta', 'coleta'):
        try:
            nomes = os.listdir(p[sub])
            linhas.append('%s: %d arquivo(s), %d KB' % (sub, len(nomes), sum(
                os.path.getsize(os.path.join(p[sub], n)) for n in nomes) >> 10))
        except OSError:
            pass
    return '\n'.join(linhas) + '\n'


def coleta(conf):
    p = pastas(conf)
    os.makedirs(p['estado'], mode=0o700, exist_ok=True)
    caminho_estado = os.path.join(p['estado'], 'coleta.json')
    try:
        with open(caminho_estado) as f:
            estado = json.load(f)
    except (OSError, ValueError):
        estado = {}
    estado = {k: v for k, v in estado.items() if k in conf['coleta'] or k in ESTADO_FIXO}
    for nome, caminho in sorted(conf['coleta'].items()):
        novo, estado[nome] = le_novo(caminho, estado.get(nome, {}))
        if novo:
            grava_coleta(conf, nome, novo)
    diario, estado['uplink'] = diario_uplink(estado.get('uplink', {}))
    wifi = estado_wifi()
    if wifi is not None and wifi != estado.get('wifi'):
        diario += ('%s wifi: %s\n' % (hora_utc(time.time() * 1000000), wifi)).encode()
        estado['wifi'] = wifi
    if diario:
        grava_coleta(conf, 'uplink', diario)
    texto = resumo(conf)
    fixo = '\n'.join(l for l in texto.splitlines() if l.startswith(('ferramentas:', 'serviços:', 'internet:')))
    marca = hashlib.sha256(fixo.encode()).hexdigest()
    agora = time.time()
    if estado.get('resumo') != marca or agora - estado.get('resumo_quando', 0) >= RESUMO_S:
        quando = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(agora))
        grava_coleta(conf, 'resumo', ('hora: %s\n' % quando + texto).encode())
        estado['resumo'] = marca
        estado['resumo_quando'] = agora
    limpa_coleta(conf)
    tmp = caminho_estado + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(estado, f)
    if os.geteuid() == 0:
        os.chown(tmp, conf['uid'], conf['uid'])
    os.chmod(tmp, 0o600)
    os.replace(tmp, caminho_estado)


def relogio():
    """Segundos que andam também com a central dormindo (CLOCK_BOOTTIME), onde há."""
    c = getattr(time, 'CLOCK_BOOTTIME', None)
    return time.clock_gettime(c) if c is not None else time.monotonic()


def iso_agora():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def dlt_aberta():
    """True se algo ouve (LISTEN) na porta do DLT: a captura do app está aberta."""
    for tabela in TCP_TABELAS:
        try:
            with open(tabela) as f:
                linhas = f.read().splitlines()[1:]
        except OSError:
            continue
        for linha in linhas:
            campos = linha.split()
            if len(campos) > 3 and campos[3] == '0A':
                try:
                    if int(campos[1].rsplit(':', 1)[1], 16) == DLT_PORTA:
                        return True
                except (IndexError, ValueError):
                    pass
    return False


def conecta_dlt():
    """Um socket conectado à porta do DLT (127.0.0.1, ou ::1), ou None."""
    for familia, host in ((socket.AF_INET, '127.0.0.1'), (socket.AF_INET6, '::1')):
        try:
            s = socket.socket(familia, socket.SOCK_STREAM)
        except OSError:
            continue
        try:
            try:  # acima do rmem_max: só com CAP_NET_ADMIN, só no Linux
                if RCVBUFFORCE is None:
                    raise OSError('sem SO_RCVBUFFORCE')
                s.setsockopt(socket.SOL_SOCKET, RCVBUFFORCE, DLT_BUFFER)
            except OSError:
                try:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, DLT_BUFFER)
                except OSError:
                    pass
            s.settimeout(5)
            s.connect((host, DLT_PORTA))
            s.settimeout(1)
            return s
        except OSError:
            s.close()
    return None


class SaidaDlt:
    """O .txt de uma captura: linhas "#" e o DLT em gzip, em base64 (linhas de 76)."""

    def __init__(self, caminho):
        fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.f = os.fdopen(fd, 'wb')
        self.z = zlib.compressobj(1, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
        self.pendente = b''
        self.escritos = 0

    def _escreve(self, b):
        self.f.write(b)
        self.escritos += len(b)

    def linha(self, texto):
        self._escreve((texto + '\n').encode())

    def dados(self, bloco):
        self.pendente += self.z.compress(bloco)
        corte = len(self.pendente) // 57 * 57
        if corte:
            self._escreve(base64.encodebytes(self.pendente[:corte]))
            self.pendente = self.pendente[corte:]

    def fecha(self, rodape):
        try:
            self.pendente += self.z.flush()
            if self.pendente:
                self._escreve(base64.encodebytes(self.pendente))
            self.linha(rodape)
        finally:
            self.f.close()


def entrega(conf, parte, caminho):
    """O .part pronto vira o .txt que o envio manda (do dono do envio, 0600)."""
    if os.geteuid() == 0:
        os.chown(parte, conf['uid'], conf['uid'])
    os.chmod(parte, 0o600)
    os.replace(parte, caminho)


def captura_dlt(conf):
    """Grava uma captura, de quando conecta até DLT_FECHADA_S depois de a porta
    fechar (o daemon não derruba quem já está conectado), o daemon fechar a
    conexão, DLT_MAX_S ou os limites. O caminho do .txt, ou None se não
    conectou."""
    s = None
    for i in range(DLT_TENTATIVAS):
        s = conecta_dlt()
        if s is not None or not dlt_aberta():
            break
        if i + 1 < DLT_TENTATIVAS:
            time.sleep(DLT_PASSO_S)
    if s is None:
        log('dlt: a captura abriu, mas a porta %d não aceitou a conexão' % DLT_PORTA)
        return None
    p = pastas(conf)
    base = os.path.join(p['coleta'], 'dlt-' + time.strftime('%Y%m%d-%H%M%S', time.gmtime()))
    caminho, i = base + '.txt', 1
    while os.path.exists(caminho) or os.path.exists(caminho + '.part'):
        caminho = '%s-%d.txt' % (base, i)
        i += 1
    parte = caminho + '.part'
    cru, motivo = 0, 'parou'
    try:
        saida = SaidaDlt(parte)
    except OSError as e:
        s.close()
        log('dlt: não consegui criar %s: %s' % (parte, e))
        return None
    try:
        saida.linha('# zelador-carro dlt: o que o dlt-daemon mandou pela porta %d na captura do app '
                    '(o DLT em gzip, em base64)' % DLT_PORTA)
        saida.linha('# início %s' % iso_agora())
        log('dlt: a captura abriu; gravando em %s' % os.path.basename(caminho))
        comeco = teste = relogio()
        fechada = None
        while True:
            agora = relogio()
            if agora - comeco >= DLT_MAX_S:
                motivo = 'passou de %d s' % DLT_MAX_S
                break
            if agora - teste >= 1:
                teste = agora
                if dlt_aberta():
                    fechada = None
                elif fechada is None:
                    fechada = agora
            if fechada is not None and agora - fechada >= DLT_FECHADA_S:
                motivo = 'a captura fechou'
                break
            try:
                bloco = s.recv(1 << 16)
            except socket.timeout:
                continue
            except OSError as e:
                motivo = 'a conexão caiu (%s)' % e
                break
            if not bloco:
                motivo = 'o daemon fechou a conexão'
                break
            bloco = bloco[:DLT_MAX_CRU - cru]
            try:
                saida.dados(bloco)
            except OSError as e:
                motivo = 'erro ao gravar (%s)' % e
                break
            cru += len(bloco)
            if cru >= DLT_MAX_CRU or saida.escritos >= DLT_MAX_ARQ:
                motivo = 'chegou ao limite'
                break
    finally:
        s.close()  # antes de tudo: o daemon nunca fica esperando por nós
        try:
            saida.fecha('# fim %s: %d bytes do DLT, %s' % (iso_agora(), cru, motivo))
            entrega(conf, parte, caminho)
        except OSError as e:
            log('dlt: não consegui fechar %s: %s' % (os.path.basename(parte), e))
    log('dlt: captura gravada, %d KB do DLT em %s (%s)' % (cru >> 10, os.path.basename(caminho), motivo))
    return caminho


def termina_sobras(conf):
    """As capturas que ficaram pela metade (a central desligou ou o serviço parou
    no meio) fecham como estão, com uma linha dizendo isso."""
    p = pastas(conf)
    try:
        nomes = os.listdir(p['coleta'])
    except OSError:
        return
    for n in sorted(nomes):
        if n.startswith('dlt-') and n.endswith('.txt.part'):
            parte = os.path.join(p['coleta'], n)
            try:
                with open(parte, 'ab') as f:
                    f.write(b'\n# cortada: o servi\xc3\xa7o parou no meio da captura\n')
                entrega(conf, parte, parte[:-len('.part')])
                log('dlt: a captura cortada %s foi fechada como estava' % n[:-len('.part')])
            except OSError as e:
                log('dlt: não consegui fechar %s: %s' % (n, e))


def passo_dlt(conf, esperando_fechar):
    """Um passo do serviço: grava se a captura abriu, uma vez por abertura.
    Devolve se deve esperar a porta fechar antes da próxima."""
    if not dlt_aberta():
        return False
    if not esperando_fechar:
        captura_dlt(conf)
    return True


def dlt(conf):
    p = pastas(conf)
    os.makedirs(p['coleta'], mode=0o700, exist_ok=True)
    termina_sobras(conf)
    log('dlt: esperando a captura do app (porta %d)' % DLT_PORTA)
    esperando = False
    while True:
        esperando = passo_dlt(conf, esperando)
        time.sleep(DLT_PASSO_S)


def main(argv):
    if len(argv) < 2 or argv[1] not in ('envio', 'coleta', 'dlt'):
        raise SystemExit(__doc__)
    conf_arq = CONF
    if len(argv) == 4 and argv[2] == '--conf':
        conf_arq = argv[3]
    elif len(argv) != 2:
        raise SystemExit(__doc__)
    conf = le_conf(conf_arq)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    if argv[1] == 'envio':
        envio(conf)
    elif argv[1] == 'dlt':
        dlt(conf)
    else:
        coleta(conf)


if __name__ == '__main__':
    main(sys.argv)
