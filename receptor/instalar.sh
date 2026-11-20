#!/bin/sh
# Instala o receptor do zelador-carro neste Mac, para o usuário atual.
#
#   sh receptor/instalar.sh IP [PORTA]
#
# IP: o endereço deste Mac na rede de casa. O certificado leva esse IP, e o
# carro só fala com ele. Cria ~/zelador-carro com o receptor, o certificado
# (receptor.pem: público, vai na ferramenta do carro) e a chave (receptor.key,
# 0600: fica só aqui), e um LaunchAgent que mantém o receptor rodando enquanto
# o usuário está logado. Rodar de novo atualiza o receptor e o reinicia; o
# certificado fica (apague receptor.key e receptor.pem para trocar, e leve o
# novo receptor.pem para a ferramenta).
#
# Desinstalar:
#   launchctl bootout gui/$(id -u)/local.zelador-carro.receptor
#   rm ~/Library/LaunchAgents/local.zelador-carro.receptor.plist
set -eu
IP=${1:?uso: sh instalar.sh IP [PORTA]}
PORTA=${2:-47321}
DIR=$(cd "$(dirname "$0")" && pwd)
P="$HOME/zelador-carro"
ROTULO=local.zelador-carro.receptor
PLIST="$HOME/Library/LaunchAgents/$ROTULO.plist"

mkdir -p "$P" "$HOME/Library/LaunchAgents"
chmod 700 "$P"
cp "$DIR/receptor.py" "$P/receptor.py"
if [ ! -f "$P/receptor.key" ]; then
    (umask 077 && openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=zelador-carro receptor" \
        -addext "subjectAltName=IP:$IP" -keyout "$P/receptor.key" -out "$P/receptor.pem" 2>/dev/null)
    chmod 600 "$P/receptor.key"
    chmod 644 "$P/receptor.pem"
fi
cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$ROTULO</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$P/receptor.py</string>
        <string>--pasta</string><string>$P</string>
        <string>--porta</string><string>$PORTA</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ThrottleInterval</key><integer>30</integer>
    <key>StandardOutPath</key><string>$P/receptor.log</string>
    <key>StandardErrorPath</key><string>$P/receptor.log</string>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)/$ROTULO" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "receptor instalado: porta $PORTA, pasta $P"
openssl x509 -in "$P/receptor.pem" -noout -subject -ext subjectAltName 2>/dev/null || true
