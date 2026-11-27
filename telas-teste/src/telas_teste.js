// SPDX-License-Identifier: GPL-3.0-or-later
// O ciclo de vida (pontos de entrada, visibilidade, eventos de foco e de
// pressão, desligamento) segue o robertn_waze_cluster e a robertn_store de
// Robert Nisipeanu (GPL-3.0-or-later).
/**
 * italo_telas_teste: um app só para experimentar, sem mexer no Mapas no
 * painel, se as telas da BMW com uma explicação à direita funcionam num app
 * de fora (src/variantes.js). A entrada lista as variantes; cada uma mostra
 * os itens do Mapas no painel e, quando o seletor destaca um item, troca a
 * explicação e o desenho ao lado.
 *
 * Não faz nada além de mostrar: nenhum botão muda configuração. Anota o que
 * acontece (início, telas abertas, focos, erros) no log do app e em
 * /dev/shm/italo_telas_teste/registro.txt (RAM: some ao desligar), que o
 * puxar-pelo-hotspot.sh copia.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const OnlineApp = require('oap-sdk/src/core/OnlineApp.js');
const logging = require('oap-sdk/src/logging/logging');
const { ITENS, VARIANTES, ENTRADA, estado, botao, conteudo, pecaDoItem, quadros } = require('./variantes.js');

const logger = logging.getSDKLogger();
const PASTA = '/dev/shm/italo_telas_teste';
const REGISTRO = path.join(PASTA, 'registro.txt');
const REGISTRO_MAX = 512 * 1024;
const VALOR = 0;       // o valor de um evento de foco no parameterMap
const DEDUPE_MS = 400;

function isTrue(raw) {
    return raw === true || raw === 'true' || raw === 1 || raw === '1';
}

/* A pasta em /dev/shm (um nível só: sem o recursive, que o Node antigo não tem). */
function criaPasta() {
    try {
        fs.mkdirSync(PASTA);
    } catch (e) {
        if (e.code !== 'EEXIST') {
            throw e;
        }
    }
}

/* Uma linha no log do app e no registro em RAM. */
function anota(msg) {
    logger.info(`telas: ${msg}`);
    try {
        criaPasta();
        fs.chmodSync(PASTA, 0o755);
        let tam = 0;
        try {
            tam = fs.statSync(REGISTRO).size;
        } catch (e) {
            /* ainda não existe */
        }
        if (tam < REGISTRO_MAX) {
            fs.appendFileSync(REGISTRO, `${new Date().toISOString()} ${msg}\n`);
        }
    } catch (e) {
        /* sem /dev/shm: só o log do app */
    }
}

class TelasTeste extends OnlineApp {
    constructor() {
        super();
        this._comp = {};
        this._porId = {};
        this._focoPorId = {};
        this._ultimo = {};
        this._imagens = {};
        this._estados = {};
        this._iniciais = [];
        this._listas = {};
        this._animacao = {};
        this._pecaAtual = {};
        this._visivel = false;
        this._saindo = null;
        this.on('initialized', () => this._iniciar().catch((err) => anota(`ERRO no início: ${err && err.message}`)));
        this.on('shutdown', (motivo) => this._desligar(motivo));
        this.on('error', (err) => anota(`erro do OnlineApp: ${err && err.message}`));
        this.on('entryPointExecute', (uuid) => this._abrirEntrada(uuid));
        this.on('changeVisibility', (d) => {
            if (d && d.visible === false) {
                this._mostra(false);
            }
        });
    }

    _iniciar() {
        anota(`início ${this._packageJson && this._packageJson.version}, motivo ${this.startReason}`);
        if (!this.rhmiApplication) {
            anota('sem RhmiApplication neste início');
            return this.initialized();
        }
        const primeiro = ['ENTRY_POINT', 'LUM', 'BOOKMARK', 'START_WIDGET', 'TRIGGER_HMI', 'SPEECH_COMMAND']
            .includes(((this.getVisibilityData && this.getVisibilityData()) || {}).reason || this.startReason);
        return this._montar()
            .then(() => this._registrarEntrada())
            .then(() => {
                if (primeiro) {
                    this.registerActive();
                }
                return this.initialized();
            })
            .then(() => {
                if (primeiro) {
                    this._mostra(true);
                }
                const ultimo = this.getLastExecutedEntryPointUuid && this.getLastExecutedEntryPointUuid();
                return ultimo ? this._abrirEntrada(ultimo) : undefined;
            });
    }

    /* Acha os estados e componentes; o que faltar fica anotado e o resto segue. */
    _montar() {
        const rhmi = this.rhmiApplication;
        this._entrada = rhmi.getByName(ENTRADA.nome);
        if (!this._entrada) {
            return Promise.reject(new Error(`uiDescription sem ${ENTRADA.nome}`));
        }
        this._copiarImagens();
        const estados = [this._entrada];
        VARIANTES.forEach((v) => {
            const e = estado(v);
            const st = rhmi.getByName(e.nome);
            anota(`variante ${v.n} (${v.widget} / ${v.previa}): estado ${st ? 'achado' : 'FALTANDO'}`);
            if (st) {
                estados.push(st);
                this._estados[v.n] = st;
                st.on('visible', (ev) => {
                    const vis = isTrue(ev && ev.visible);
                    anota(`variante ${v.n} ${vis ? 'visível' : 'escondida'}`);
                    if (vis) {
                        this._mostra(true);
                    }
                });
            }
            e.pecas.forEach((p) => this._achar(p.nome));
            ITENS.forEach((it, i) => {
                const nome = e.item(i).nome;
                const c = this._achar(nome);
                if (c && it.tipo === 'lista') {
                    try {
                        this._listas[Number(c.getId())] = { nome: `V${v.n}`, foco: (r) => {
                            anota(`variante ${v.n}: foco em "${it.nome}", opção ${r}`);
                            this._previa(v, i, r);
                        } };
                    } catch (e) {
                        /* sem id */
                    }
                }
                if (c) {
                    this._liga(nome, () => anota(`variante ${v.n}: apertou "${it.nome}" (só mostra)`));
                    c.on('change', (d) => {
                        anota(`variante ${v.n}: "${it.nome}" mudou: ${JSON.stringify(d)}`);
                        if (it.tipo === 'lista' && (v.valor === 'app' || v.valor === 'ambos')) {
                            this._escreveValor(v, c, d && d.row);
                        }
                    });
                    if (it.tipo === 'lista' && (v.valor === 'app' || v.valor === 'ambos')) {
                        this._iniciais.push(() => this._escreveValor(v, c, 0));
                    }
                    this._ligaFoco(nome, (foco) => {
                        if (v.porOpcao && it.tipo === 'lista') {
                            return; // a lista manda o foco com a opção: tratado no userEvent
                        }
                        if (foco) {
                            anota(`variante ${v.n}: foco em "${it.nome}"`);
                            this._previa(v, i);
                        }
                    });
                }
            });
            const b = botao(v).nome;
            if (this._achar(b)) {
                this._liga(b, () => this._abrir(e.nome));
            }
        });
        rhmi.on('userEvent', (ev) => {
            const id = Number(ev && ev.sourceId);
            if (this._listas[id]) {
                anota(`evento da lista ${this._listas[id].nome}: ${JSON.stringify(ev).slice(0, 300)}`);
                if (ev.eventType === 'FOCUS') {
                    /* a lista manda a opção em foco em parameterMap[2]; 4294967295 é o nome */
                    const r = Number((ev.parameterMap || {})[2]);
                    this._listas[id].foco(r >= 0 && r < 0xFFFFFFFF ? r : -1);
                }
            }
            if (ev && ev.eventType === 'ACTION' && this._porId[id]) {
                this._aperta(this._porId[id].nome, this._porId[id].fn);
            }
            if (ev && ev.eventType === 'FOCUS' && this._focoPorId[id]) {
                this._focoPorId[id](isTrue((ev.parameterMap || {})[VALOR]));
            }
        });
        rhmi.on('applicationStackChanged', (pilha) => {
            const chaves = pilha && typeof pilha === 'object' ? Object.keys(pilha) : [];
            if (chaves.length) {
                this._mostra(Object.prototype.hasOwnProperty.call(pilha, 'ROOT_APP'));
            }
        });
        rhmi.on('restoreHmi', () => anota('RESTORE_HMI'));
        return Promise.all(estados.map((st) => Promise.resolve(st.updateResources())
            .catch((err) => anota(`updateResources: ${err && err.message}`))))
            .then(() => this._registrarImagens())
            .then(() => {
                VARIANTES.forEach((v) => this._previa(v, 0));
                this._iniciais.forEach((fn) => fn());
                anota('telas prontas');
            });
    }

    _achar(nome) {
        const c = this.rhmiApplication.getByName(nome);
        if (!c) {
            anota(`componente FALTANDO: ${nome}`);
            return null;
        }
        this._comp[nome] = c;
        return c;
    }

    /* Os desenhos vão para a RAM, legíveis pela interface (como o QR code do Mapas no painel). */
    _copiarImagens() {
        const origem = path.join(__dirname, '..', 'imagens');
        try {
            criaPasta();
            fs.chmodSync(PASTA, 0o755);
            fs.readdirSync(origem).filter((n) => /\.png$/.test(n)).forEach((n) => {
                const destino = path.join(PASTA, n);
                fs.copyFileSync(path.join(origem, n), destino);
                fs.chmodSync(destino, 0o644);
                this._imagens[n.replace(/\.png$/, '')] = destino;
            });
            anota(`imagens: ${Object.keys(this._imagens).join(', ') || 'nenhuma'}`);
        } catch (err) {
            anota(`imagens: ${err && err.message}`);
        }
    }

    /* A interface só mostra um desenho registrado no pacote de recursos do
     * app (como o QR code do Mapas no painel): sem isso o setValue falha com
     * "Cannot create ParameterValueUnion for value: undefined" (0.0.1). */
    _registrarImagens() {
        const arquivos = Object.keys(this._imagens).map((k) => this._imagens[k]);
        if (!arquivos.length) {
            return Promise.resolve();
        }
        return Promise.resolve()
            .then(() => this.rhmiApplication.getResourceBundle().createResourceHandles(arquivos))
            .then(() => {
                this._imagensProntas = true;
                anota(`imagens registradas: ${arquivos.length}`);
            })
            .catch((err) => anota(`registrar imagens: ${err && err.message}`));
    }

    /* A explicação e o desenho do item i nas peças da variante v; cada erro
     * fica anotado com a peça, para saber qual a interface aceita. */
    _previa(v, i, r) {
        const e = estado(v);
        const it = ITENS[i];
        const mostra = conteudo(v, i, r);
        const escritas = [];
        const usada = pecaDoItem(v, i);
        if (v.troca && !v.preenche) {
            escritas.push(this._trocaPeca(v, usada));
        }
        e.pecas.forEach((p, k) => {
            const c = this._comp[p.nome];
            if (k !== usada) {
                return;
            }
            if (!c) {
                return;
            }
            if (p.texto) {
                escritas.push(Promise.resolve(c.setValue(0, p.celTexto || 'Text', v.previa === 'List' && !p.desenho ? `${it.nome}: ${mostra.texto}` : mostra.texto, 'Text'))
                    .catch((err) => anota(`variante ${v.n}: ${p.widget} texto: ${err && err.message}`)));
            }
            if (p.celTitulo) {
                escritas.push(Promise.resolve(c.setValue(0, p.celTitulo, mostra.titulo, 'Text'))
                    .catch((err) => anota(`variante ${v.n}: ${p.widget} título: ${err && err.message}`)));
            }
            if (p.desenho && this._imagensProntas && this._imagens[mostra.imagem]) {
                escritas.push(Promise.resolve(c.setValue(0, p.celDesenho || 'Graphic', this._imagens[mostra.imagem], 'ResourceId'))
                    .catch((err) => anota(`variante ${v.n}: ${p.widget} desenho: ${err && err.message}`)));
            }
        });
        const flush = () => Promise.resolve(this.rhmiApplication.flush && this.rhmiApplication.flush());
        this._anima(v, e.pecas[usada], mostra.imagem);
        return Promise.all(escritas)
            .then(flush)
            /* preenche: a peça nova recebe o conteúdo antes de a tela apontar
             * para ela, para ver se o vazio da troca diminui. */
            .then(() => (v.troca && v.preenche ? this._trocaPeca(v, usada).then(flush) : undefined))
            .catch((err) => anota(`variante ${v.n}: flush: ${err && err.message}`));
    }

    /* Os quadros seguintes da animação do desenho, um a cada v.animacao.ms;
     * um foco novo na mesma variante cancela a animação anterior. */
    _anima(v, p, imagem) {
        const vez = (this._animacao[v.n] || 0) + 1;
        this._animacao[v.n] = vez;
        if (!v.animacao || !p || !p.desenho) {
            return;
        }
        const c = this._comp[p.nome];
        const lista = quadros(v, imagem).slice(1);
        const proximo = (k) => {
            if (this._animacao[v.n] !== vez || k >= lista.length || !c || !this._imagens[lista[k]]) {
                return;
            }
            Promise.resolve(c.setValue(0, p.celDesenho || 'Graphic', this._imagens[lista[k]], 'ResourceId'))
                .then(() => this.rhmiApplication.flush && this.rhmiApplication.flush())
                .catch((err) => anota(`variante ${v.n}: quadro ${lista[k]}: ${err && err.message}`))
                .then(() => setTimeout(() => proximo(k + 1), v.animacao.ms));
        };
        setTimeout(() => proximo(0), v.animacao.ms);
    }

    /* Mostra a peça k da prévia da variante v: pela propriedade Preview da
     * tela ou escondendo as outras peças (Visible). Erros anotados. */
    _trocaPeca(v, k) {
        if (this._pecaAtual[v.n] === k) {
            return Promise.resolve();
        }
        this._pecaAtual[v.n] = k;
        const e = estado(v);
        const p = e.pecas[k];
        if (v.troca === 'preview') {
            const st = this._estados[v.n];
            return st ? Promise.resolve(st.setProperty('Preview', p.id, 'UInt'))
                .then(() => anota(`variante ${v.n}: prévia -> ${p.widget}`))
                .catch((err) => anota(`variante ${v.n}: trocar Preview: ${err && err.message}`)) : Promise.resolve();
        }
        return Promise.all(e.pecas.map((q, j) => this._comp[q.nome] &&
            Promise.resolve(this._comp[q.nome].setProperty('Visible', j === k ? 1 : 0, 'UInt'))
                .catch((err) => anota(`variante ${v.n}: Visible de ${q.widget}: ${err && err.message}`))))
            .then(() => anota(`variante ${v.n}: visível -> ${p.widget}`));
    }

    /* Escreve a opção escolhida (SelectedItem) na lista, para ver se o nome
     * passa a mostrar o valor embaixo, como no Attention Assist. */
    _escreveValor(v, c, row) {
        if (row === undefined || row === null) {
            return;
        }
        Promise.resolve(c.setValue('SelectedItem', row, 'UInt'))
            .then(() => this.rhmiApplication.flush && this.rhmiApplication.flush())
            .then(() => anota(`variante ${v.n}: SelectedItem = ${row}`))
            .catch((err) => anota(`variante ${v.n}: SelectedItem: ${err && err.message}`));
    }

    _abrir(nome) {
        anota(`abrindo ${nome}`);
        Promise.resolve(this.rhmiApplication.openState(nome))
            .then(() => anota(`abriu ${nome}`))
            .catch((err) => anota(`openState ${nome} falhou: ${err && err.message}`));
    }

    _liga(nome, fn) {
        const c = this._comp[nome];
        try {
            this._porId[Number(c.getId())] = { nome, fn };
        } catch (e) {
            /* sem id: só os eventos do componente */
        }
        c.on('action', () => this._aperta(nome, fn));
    }

    _ligaFoco(nome, fn) {
        const c = this._comp[nome];
        try {
            this._focoPorId[Number(c.getId())] = fn;
        } catch (e) {
            /* sem id */
        }
        c.on('focus', (ev) => fn(isTrue(ev && ev.value)));
    }

    _aperta(nome, fn) {
        const agora = Date.now();
        if (agora - (this._ultimo[nome] || 0) < DEDUPE_MS) {
            return;
        }
        this._ultimo[nome] = agora;
        try {
            fn();
        } catch (err) {
            anota(`${nome}: ${err && err.message}`);
        }
    }

    _registrarEntrada() {
        const desc = (this.appDescription && this.appDescription.application.entryPoints) || [];
        const nosso = this.getEntryPoints().find((ep) => desc.some((d) => d.uuid === ep.getDescription().uuid));
        if (!nosso) {
            return Promise.reject(new Error('nenhum ponto de entrada entregue pelo gerenciador'));
        }
        const d = nosso.getDescription();
        return nosso.init()
            .then(() => this.rhmiApplication.mapEntryState(d.uuid, this._entrada))
            .then(() => nosso.setAvailability('ENABLED'))
            .then(() => anota('ponto de entrada ligado'));
    }

    _abrirEntrada(uuid) {
        if (this._saindo || !this.rhmiApplication || !uuid) {
            return Promise.resolve();
        }
        this._mostra(true);
        return Promise.resolve(this.rhmiApplication.openEntryState(uuid))
            .catch((err) => anota(`openEntryState falhou: ${err && err.message}`));
    }

    _mostra(vis) {
        if (this._saindo || this._visivel === vis) {
            return;
        }
        this._visivel = vis;
        if (!this._initialized || !this._appStatusService) {
            return;
        }
        const r = vis ? [this.registerActive(), this.registerHmiVisible()] : [this.unregisterHmiVisible(), this.registerInactive()];
        r.forEach((p) => Promise.resolve(p).catch((err) => anota(`status do app: ${err && err.message}`)));
    }

    _desligar(motivo) {
        if (this._saindo) {
            return this._saindo;
        }
        anota(`desligando: ${JSON.stringify(motivo)}`);
        this._saindo = Promise.resolve()
            .then(() => this.destroyBundles().catch(() => undefined))
            .then(() => process.exit(0));
        return this._saindo;
    }
}

const app = new TelasTeste();
app.start().catch((err) => anota(`não iniciou: ${err && err.message}`));
