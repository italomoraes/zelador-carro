# SPDX-License-Identifier: MIT
"""zelador-carro: manda ao computador de casa o que a escuta e a coleta gravam.

    python3 -I zelador.py envio  [--conf ARQ]   o envio (começa root, larga o root)
    python3 -I zelador.py coleta [--conf ARQ]   a coleta (root, pelo timer)

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

Coleta: o que entrou de novo nos arquivos de `coleta` da configuração (o log
do Mapas no painel) e um resumo da central (hora, tempo ligado, carga,
memória, espaço, versões das ferramentas, estado dos serviços do zelador e da
internet), cada um num .txt em dados/coleta, do dono do envio. O resumo é
gravado quando as ferramentas, os serviços ou a internet mudam, e a cada 30
min. Só lê o sistema; escreve só na pasta do zelador.

A internet da central (mgu-uplink) só deixa sair os uids registrados: o do
envio está no component.json ("internet", "uids"); o root não sai.
"""
import gzip
import hashlib
import http.client
import json
import os
import secrets
import signal
import ssl
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(AQUI, 'zelador.conf')
LIMITE_LEITURA = 4 << 20  # por arquivo de coleta, por vez
RESUMO_S = 30 * 60  # um resumo sem mudança nas ferramentas, serviços e internet


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
                'waze-on-cluster.service', 'mgu-uplink.service']
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
    for nome, caminho in sorted(conf['coleta'].items()):
        try:
            st = os.stat(caminho)
        except OSError:
            continue
        antes = estado.get(nome, {})
        pos = antes.get('pos', 0)
        if antes.get('ino') != st.st_ino or st.st_size < pos:
            pos = 0
        if st.st_size > pos:
            with open(caminho, 'rb') as f:
                f.seek(pos)
                novo = f.read(min(st.st_size - pos, LIMITE_LEITURA))
            if novo:
                grava_coleta(conf, nome, novo)
                pos += len(novo)
        estado[nome] = {'ino': st.st_ino, 'pos': pos}
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


def main(argv):
    if len(argv) < 2 or argv[1] not in ('envio', 'coleta'):
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
    else:
        coleta(conf)


if __name__ == '__main__':
    main(sys.argv)
