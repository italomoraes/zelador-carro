# zelador-carro

Ferramenta de depuração para a central iDrive 7 (MGU) de uma BMW, instalada e
removida pela [mgu Store](https://github.com/robertnisipeanu/mgu-store). Ela
grava, só lendo, a orientação da navegação BMW, o log do app "Mapas no
painel" ([idrive-apps](https://github.com/robertnisipeanu/idrive-apps)) e o
que o CarPlay e o Wi-Fi da loja registram, e manda tudo ao computador de casa
quando o carro está no Wi-Fi de casa.

Feita para **um carro e um computador**: o endereço e o certificado do
receptor estão em `ferramenta/`. Para outro par, instale o receptor
(`receptor/instalar.sh`) e troque `ferramenta/zelador.conf` e
`ferramenta/receptor.pem`.

## Na central

| Serviço | Como roda | O que faz |
|---|---|---|
| `zelador-carro-escuta` | root, sem rede | Assina (só lê) os atributos da orientação da navegação BMW (SOME/IP `0xFB1A`, `0xFB1B`, `0xFB1C` e `0xFB35`, instância `0x0080`) e grava cada mensagem nova em `/var/opt/zelador-carro/dados/escuta`, um arquivo por minuto, até 100 MB. Só assina 5 s depois que a navegação oferece o serviço, sem dizer o tipo dos eventos. Não chama métodos nem oferece serviços. |
| `zelador-carro-coleta` (timer, a cada minuto) | root, sem rede | Copia para `dados/coleta` o que entrou nos logs do Mapas no painel e do cluster-render e no diário que o waze-on-cluster guarda na RAM (CarPlay, Android Auto, systemd e kernel, Wi-Fi incluído), seguindo cada arquivo quando ele gira. Copia também o diário do mgu-uplink (as buscas e conexões do Wi-Fi da loja), o estado do Wi-Fi quando muda (sem nomes de rede) e um resumo da central (versões, serviços, espaço, internet). |
| `zelador-carro-envio` | uid 59473 (larga o root ao começar) | A cada 15 s, manda os arquivos prontos ao receptor por HTTPS, conferindo o certificado dele, e apaga cada um só depois da confirmação. Longe de casa, espera. |

## Segurança

- **Nada escuta na central.** É a central que chama o receptor, e a internet
  dela (mgu-uplink) bloqueia toda conexão de entrada.
- **O root não usa a rede, e a rede não usa o root.** O mgu-uplink só deixa
  sair os uids que uma ferramenta registra (o do envio, no `component.json`),
  nunca o root. A escuta precisa ser root porque a política do SOME/IP da
  central só libera esses serviços para ele.
- **Só um destino.** O envio aceita apenas o certificado do receptor
  (`ferramenta/receptor.pem`, com o IP dele); o receptor aceita apenas o
  primeiro carro que se apresenta.
- **Sem comandos de fora e sem segredos aqui.** A ferramenta só publica; a
  chave do receptor fica só no computador de casa.
- **Os dados ficam fechados.** Até o envio, numa pasta só do uid do envio
  (0700). Eles têm rotas e a posição do carro.
- **Remover tira tudo.** A remoção pela loja apaga os serviços, a pasta da
  ferramenta com os dados e a permissão de internet.
- Se um programa da ferramenta travar, só o serviço dele reinicia, nunca a
  central (a loja põe os programas na lista de falhas da BMW e roda os
  serviços com `LimitCORE=1`).

## Instalar

1. **No computador de casa** (macOS): `sh receptor/instalar.sh <IP>`. Ele cria
   o certificado e deixa o receptor rodando (LaunchAgent, porta 47321). Reserve
   esse IP para o computador no roteador.
2. **Na loja do carro:** ligue o Wi-Fi e salve a rede de casa. Depois adicione a
   fonte `italomoraes/zelador-carro`, instale **Zelador do carro (depuração)**
   e reinicie a central quando a loja pedir: os serviços começam na próxima
   partida.
3. O que chega fica em `~/zelador-carro/recebidos/`, e o registro do receptor
   em `~/zelador-carro/receptor.log`.

## Desenvolver

- `sh fonte/compilar.sh` compila a escuta para a central, no Docker de outra
  máquina; o cabeçalho do script diz o que ela precisa.
- Testes da gravação: `c++ -std=c++14 -o /tmp/teste_gravador fonte/teste_gravador.cpp && /tmp/teste_gravador`.
- Testes do envio, da coleta e do receptor, de ponta a ponta em 127.0.0.1:
  `python3 -I testes/teste_envio.py`.

## Licença

MIT ([`LICENSE`](LICENSE)).
