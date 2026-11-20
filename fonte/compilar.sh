#!/bin/sh
# Compila o zelador-escuta para a central e o põe em ferramenta/.
#
#   sh fonte/compilar.sh
#
# Roda no Docker de outra máquina (o iMac, por SSH: IMAC=usuario@host), com a
# imagem de compilação do idrive-apps (Ubuntu 18.04, gcc 7.5;
# `make -C native/cluster-render image` lá) e uma cópia do idrive-apps em
# ~/projetos/idrive-apps, de onde vêm os cabeçalhos do vsomeip e a lista de
# símbolos da libvsomeip3 da central (native/cluster-render/dcsm). Liga contra
# uma fachada gerada dessa lista e confere: o carregador da central, cada
# função do vsomeip exportada pela biblioteca de lá, glibc até 2.27 e
# libstdc++ até a 6.0.24. Antes, roda os testes do gravador no mesmo ambiente.
set -eu
DIR=$(cd "$(dirname "$0")/.." && pwd)
IMAC=${IMAC-italomoraes@10.1.1.139}
IMG=${IMG-cluster-render-build:3699913768}
CR=${CR-projetos/idrive-apps/native/cluster-render}
SSH="ssh -o BatchMode=yes -o ConnectTimeout=10 -o LogLevel=ERROR"

rsync -a --delete --exclude build/ -e "$SSH" "$DIR/fonte/" "$IMAC:projetos/zelador-carro-fonte/"
$SSH "$IMAC" "export PATH=/usr/local/bin:\$PATH; docker run --rm --platform linux/amd64 --user \"\$(id -u):\$(id -g)\" \
  -v \"\$HOME/projetos/zelador-carro-fonte:/z\" -v \"\$HOME/$CR:/cr:ro\" -w /z $IMG sh -ec '
mkdir -p build/stub
g++ -std=c++14 -O2 -Wall -Wextra -Werror -o build/teste_gravador teste_gravador.cpp
build/teste_gravador | tail -n 1
python3 /cr/dcsm/tools/abi.py stub /cr/dcsm/abi/libvsomeip3.so.3.symbols build/stub/vsomeip_stub.S
g++ -shared -nostdlib -Wl,-soname,libvsomeip3.so.3 -o build/stub/libvsomeip3.so.3 build/stub/vsomeip_stub.S
g++ -std=c++14 -O2 -Wall -Wextra -Werror -isystem /cr/dcsm/third_party/vsomeip/interface -pthread \
    -o build/zelador-escuta zelador_escuta.cpp build/stub/libvsomeip3.so.3 \
    -Wl,--dynamic-linker=/lib/ld-linux-x86-64.so.2 -s
python3 /cr/dcsm/tools/abi.py check build/zelador-escuta /cr/dcsm/abi/libvsomeip3.so.3.symbols
'"
scp -q -o BatchMode=yes "$IMAC:projetos/zelador-carro-fonte/build/zelador-escuta" "$DIR/ferramenta/zelador-escuta"
chmod 0755 "$DIR/ferramenta/zelador-escuta"
ls -la "$DIR/ferramenta/zelador-escuta"
shasum -a 256 "$DIR/ferramenta/zelador-escuta"
