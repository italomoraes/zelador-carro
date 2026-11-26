# SPDX-License-Identifier: MIT
"""receptor do zelador-carro: recebe por HTTPS o que a central manda e guarda.

    python3 receptor.py [--pasta DIR] [--porta N] [--sem-aviso]

Na pasta (padrão ~/zelador-carro): receptor.pem e receptor.key (o
certificado que a ferramenta do carro leva, instalar.sh os cria),
carro.id (o primeiro carro que mandar algo; só ele é aceito depois) e
recebidos/<escuta|coleta>/<arquivo>.

POST /arquivo com X-Zelador-Carro (o id do carro), X-Zelador-Nome
(escuta/<arquivo>.txt ou coleta/<arquivo>.txt), X-Zelador-Sha256 e
X-Zelador-Gzip: confere tudo, grava (o mesmo nome com o mesmo conteúdo de
novo só é confirmado) e responde {"ok": true, "sha256": ...}; só então o
carro apaga o seu. Qualquer outra coisa recebe um erro 4xx e nada é gravado.

Quando chega um "Salvar logs" do Mapas no painel (coleta/salvo-woc-logs-*.txt),
cria um lembrete na lista "Zelador" do app Lembretes, que o iCloud leva ao
iPhone: "Logs do carro recebidos (HH:MM, N MB)". Os lembretes antigos da lista
são marcados como concluídos. Na primeira vez o macOS pergunta se o receptor
pode controlar o Lembretes. --sem-aviso desliga.
"""
import hashlib
import http.server
import json
import os
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import threading
import time
import zlib

MAX_CORPO = 64 << 20
MAX_CONTEUDO = 256 << 20
MIN_LIVRE = 1 << 30
NOME = re.compile(r'(escuta|coleta)/([A-Za-z0-9][A-Za-z0-9._-]{0,120}\.txt)')
ID = re.compile(r'[0-9a-f]{64}')
SALVO = re.compile(r'salvo-woc-logs-\d{8}T\d{6}Z(-[0-9a-f]{8})?\.txt')
FIM = re.compile(rb'^# fim: (\d+) bytes, sha256 [0-9a-f]{64}$', re.M)
LISTA = 'Zelador'
# o texto e a lista vão como argumentos, nunca dentro do script; o alarme
# fica 30 s à frente, o tempo de o iCloud levar o lembrete ao iPhone
LEMBRETE = '''on run argv
    set titulo to item 1 of argv
    set nomeLista to item 2 of argv
    tell application "Reminders"
        if not (exists list nomeLista) then make new list with properties {name:nomeLista}
        set l to list nomeLista
        repeat with r in (reminders of l whose completed is false)
            set completed of r to true
        end repeat
        make new reminder at end of l with properties {name:titulo, remind me date:((current date) + 30)}
    end tell
end run'''


def texto_aviso(conteudo, quando=None):
    """"Logs do carro recebidos (HH:MM, N MB)": o tamanho do .tar.gz, do rodapé."""
    m = FIM.search(conteudo[-4096:])
    hora = time.strftime('%H:%M', time.localtime(quando))
    if not m:
        return 'Logs do carro recebidos (%s)' % hora
    mb = ('%.1f' % (int(m.group(1)) / 1048576.0)).replace('.', ',')
    return 'Logs do carro recebidos (%s, %s MB)' % (hora, mb)


def avisa_lembrete(titulo):
    """Cria o lembrete pelo osascript; erros só vão para o log."""
    try:
        r = subprocess.run(['osascript', '-e', LEMBRETE, titulo, LISTA], stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
                           universal_newlines=True)
    except (OSError, subprocess.TimeoutExpired) as e:
        log('aviso no Lembretes falhou: %s' % e)
        return False
    if r.returncode != 0:
        log('aviso no Lembretes falhou: %s' % (r.stderr.strip() or r.returncode))
        return False
    log('aviso no Lembretes: %s' % titulo)
    return True


def log(msg):
    print('%s %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg), flush=True)


class Recebedor(http.server.BaseHTTPRequestHandler):
    server_version = 'zelador-receptor'
    sys_version = ''
    timeout = 60

    def log_message(self, fmt, *args):
        pass

    def responde(self, codigo, obj):
        corpo = json.dumps(obj).encode()
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(corpo)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(corpo)
        if codigo != 200:
            log('recusado (%d) de %s: %s' % (codigo, self.client_address[0], obj.get('erro')))

    def do_GET(self):
        self.responde(404, {'erro': 'nada aqui'})

    def do_POST(self):
        pasta = self.server.pasta
        if self.path != '/arquivo':
            return self.responde(404, {'erro': 'nada aqui'})
        cid = self.headers.get('X-Zelador-Carro', '')
        nome = self.headers.get('X-Zelador-Nome', '')
        sha = self.headers.get('X-Zelador-Sha256', '')
        comprimido = self.headers.get('X-Zelador-Gzip') == '1'
        try:
            tamanho = int(self.headers.get('Content-Length', ''))
        except ValueError:
            return self.responde(411, {'erro': 'sem tamanho'})
        if tamanho < 0 or tamanho > MAX_CORPO:
            return self.responde(413, {'erro': 'grande demais'})
        # o corpo é lido antes de qualquer recusa: recusar com ele por ler
        # derruba a conexão, e o carro não veria a resposta
        corpo = self.rfile.read(tamanho)
        if len(corpo) != tamanho:
            return self.responde(400, {'erro': 'corpo incompleto'})
        if not ID.fullmatch(cid) or not ID.fullmatch(sha):
            return self.responde(400, {'erro': 'id ou sha256 inválido'})
        m = NOME.fullmatch(nome)
        if not m:
            return self.responde(400, {'erro': 'nome inválido'})
        aceito = os.path.join(pasta, 'carro.id')
        if os.path.exists(aceito):
            with open(aceito) as f:
                if f.read().strip() != cid:
                    return self.responde(403, {'erro': 'outro carro'})
        if shutil.disk_usage(pasta).free < MIN_LIVRE:
            return self.responde(507, {'erro': 'pouco espaço'})
        if comprimido:
            d = zlib.decompressobj(16 + zlib.MAX_WBITS)
            try:
                conteudo = d.decompress(corpo, MAX_CONTEUDO + 1)
            except zlib.error:
                return self.responde(400, {'erro': 'gzip inválido'})
            if len(conteudo) > MAX_CONTEUDO or d.unconsumed_tail or not d.eof:
                return self.responde(400, {'erro': 'gzip grande demais ou incompleto'})
        else:
            conteudo = corpo
        if hashlib.sha256(conteudo).hexdigest() != sha:
            return self.responde(400, {'erro': 'sha256 não confere'})
        if not os.path.exists(aceito):
            tmp = aceito + '.tmp'
            with open(tmp, 'w') as f:
                f.write(cid + '\n')
            os.replace(tmp, aceito)
            log('carro aceito: %s...' % cid[:12])
        destino_pasta = os.path.join(pasta, 'recebidos', m.group(1))
        os.makedirs(destino_pasta, mode=0o700, exist_ok=True)
        destino = os.path.join(destino_pasta, m.group(2))
        if os.path.exists(destino):
            with open(destino, 'rb') as f:
                if hashlib.sha256(f.read()).hexdigest() == sha:
                    return self.responde(200, {'ok': True, 'sha256': sha})
            destino = destino[:-4] + '-' + sha[:8] + '.txt'
        tmp = destino + '.' + secrets.token_hex(4) + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(conteudo)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, destino)
        log('recebido %s (%d KB)' % (os.path.relpath(destino, pasta), (len(conteudo) + 1023) // 1024))
        self.responde(200, {'ok': True, 'sha256': sha})
        if self.server.aviso and m.group(1) == 'coleta' and SALVO.fullmatch(os.path.basename(destino)):
            # numa thread: a primeira vez o macOS pergunta, e isso não segura o carro
            threading.Thread(target=self.server.aviso, args=(texto_aviso(conteudo),), daemon=True).start()


class Servidor(http.server.ThreadingHTTPServer):
    """Cada conexão na sua thread, com o TLS feito lá e prazo de 60 s: um
    cliente parado não segura os outros."""
    daemon_threads = True

    def __init__(self, endereco, pasta, aviso=None):
        super().__init__(endereco, Recebedor)
        self.pasta = pasta
        self.aviso = aviso
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        self.ctx.load_cert_chain(os.path.join(pasta, 'receptor.pem'), os.path.join(pasta, 'receptor.key'))

    def finish_request(self, request, client_address):
        request.settimeout(60)
        try:
            tls = self.ctx.wrap_socket(request, server_side=True)
        except (OSError, ssl.SSLError) as e:
            log('conexão sem TLS válido de %s: %s' % (client_address[0], e))
            return
        try:
            self.RequestHandlerClass(tls, client_address, self)
        finally:
            tls.close()


def servidor(pasta, porta, endereco='', aviso=None):
    """aviso(titulo): chamado quando chega um "Salvar logs"; None, nenhum."""
    return Servidor((endereco, porta), pasta, aviso)


def main(argv):
    pasta = os.path.expanduser('~/zelador-carro')
    porta = 47321
    aviso = avisa_lembrete if sys.platform == 'darwin' else None
    i = 1
    while i < len(argv):
        if argv[i] == '--sem-aviso':
            aviso = None
            i += 1
            continue
        if argv[i] == '--pasta' and i + 1 < len(argv):
            pasta = argv[i + 1]
        elif argv[i] == '--porta' and i + 1 < len(argv):
            porta = int(argv[i + 1])
        else:
            raise SystemExit(__doc__)
        i += 2
    os.umask(0o077)
    srv = servidor(pasta, porta, aviso=aviso)
    log('receptor em :%d, guardando em %s' % (porta, os.path.join(pasta, 'recebidos')))
    srv.serve_forever()


if __name__ == '__main__':
    main(sys.argv)
