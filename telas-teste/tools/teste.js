// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * Testa o app no computador, com um oap-sdk de mentira: o uiDescription
 * gerado bate com src/variantes.js, o app acha tudo, a entrada abre cada
 * variante e o foco num item troca a explicação e o desenho.
 *
 *   node tools/teste.js
 */
'use strict';
const assert = require('assert');
const EventEmitter = require('events');
const fs = require('fs');
const Module = require('module');
const os = require('os');
const path = require('path');
const { ITENS, VARIANTES, estado, botao } = require('../src/variantes.js');
const gerar = require('./gerar.js');

let ok = 0;
const confere = (cond, msg) => { assert.ok(cond, msg); ok++; };

/* 1. O uiDescription gerado. */
const PKG = path.join(__dirname, '..', 'package');
const ui = JSON.parse(fs.readFileSync(path.join(PKG, 'rhmiData/uiDescriptions/ID7/uiDescription.json'), 'utf8'));
const xml = fs.readFileSync(path.join(PKG, 'rhmiData/uiDescriptions/ID7/application.xml'), 'utf8');
confere(JSON.stringify(ui) === JSON.stringify(gerar.uiDescription()) && xml === gerar.xml(), 'arquivos gerados em dia (rode tools/gerar.js)');
const ids = [];
const nomes = {};
Object.keys(ui.containers).forEach((cid) => {
    ids.push(Number(cid));
    Object.keys(ui.containers[cid].components).forEach((id) => {
        ids.push(Number(id));
        nomes[ui.containers[cid].components[id].name] = Number(id);
        confere(xml.includes(`<component id="${id}" `), `componente ${id} no application.xml`);
    });
});
confere(new Set(ids).size === ids.length, 'ids sem repetição');
VARIANTES.forEach((v) => {
    const e = estado(v);
    confere(xml.includes(`<container id="${e.id}" type="state" widget="${v.widget}">`), `variante ${v.n} com a tela ${v.widget}`);
    confere(xml.includes(`name="${v.previa}"`), `variante ${v.n} com o grupo ${v.previa}`);
    e.pecas.forEach((p) => confere(xml.includes(`<component id="${p.id}" type="label" widget="${p.widget}">`), `variante ${v.n}: peça ${p.widget}`));
});
const app = JSON.parse(fs.readFileSync(path.join(PKG, 'rhmiData/application.json'), 'utf8')).application;
confere(fs.existsSync(path.join(PKG, 'rhmiData/variantGroups/Common/images', app.entryPoints[0].icon)), 'ícone do ponto de entrada existe');
new Set(ITENS.map((i) => i.imagem)).forEach((n) => confere(fs.existsSync(path.join(PKG, 'imagens', `${n}.png`)), `imagem ${n}.png`));

/* 2. O app com um oap-sdk de mentira. */
const chamadas = [];
class Comp extends EventEmitter {
    constructor(nome, id) { super(); this.nome = nome; this.id = id; }
    getId() { return this.id; }
    setValue(row, cell, value, type) { chamadas.push({ nome: this.nome, cell, value, type }); return Promise.resolve(); }
    updateResources() { return Promise.resolve(); }
}
const comps = {};
Object.keys(ui.containers).forEach((cid) => {
    const c = ui.containers[cid];
    comps[c.name] = new Comp(c.name, Number(cid));
    Object.keys(c.components).forEach((id) => { comps[c.components[id].name] = new Comp(c.components[id].name, Number(id)); });
});
const registrados = [];
const rhmi = Object.assign(new EventEmitter(), {
    getByName: (n) => comps[n] || null,
    getResourceBundle: () => ({ createResourceHandles: (arqs) => { registrados.push(...arqs); return Promise.resolve(); } }),
    flush: () => { chamadas.push({ flush: true }); return Promise.resolve(); },
    openState: (n) => { chamadas.push({ abre: n }); return Promise.resolve(); },
    openEntryState: () => Promise.resolve(),
    mapEntryState: () => Promise.resolve()
});
let instancia = null;
class OnlineApp extends EventEmitter {
    constructor() { super(); instancia = this; this.rhmiApplication = rhmi; this.startReason = 'ENTRY_POINT'; this._packageJson = { version: 'teste' };
        this.appDescription = { application: app }; }
    start() { return Promise.resolve(); }
    initialized() { this._initialized = true; return Promise.resolve(); }
    registerActive() { return Promise.resolve(); }
    getEntryPoints() { return [{ getDescription: () => app.entryPoints[0], init: () => Promise.resolve(), setAvailability: () => Promise.resolve() }]; }
}
const sdk = {
    'oap-sdk/src/core/OnlineApp.js': OnlineApp,
    'oap-sdk/src/logging/logging': { getSDKLogger: () => ({ info() {}, warn() {}, error() {} }) }
};
const resolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...resto) { return sdk[req] ? req : resolve.call(this, req, ...resto); };
Object.keys(sdk).forEach((k) => { require.cache[k] = { id: k, filename: k, loaded: true, exports: sdk[k] }; });

/* As imagens vão para /dev/shm, que o macOS não tem: o teste aponta para uma pasta temporária. */
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'telas-'));
const fonte = fs.readFileSync(path.join(__dirname, '..', 'src', 'telas_teste.js'), 'utf8')
    .replace("'/dev/shm/italo_telas_teste'", JSON.stringify(tmp))
    .replace("path.join(__dirname, '..', 'imagens')", JSON.stringify(path.join(PKG, 'imagens')));
const m = new Module(path.join(__dirname, '..', 'src', 'telas_teste.js'));
m.paths = Module._nodeModulePaths(path.join(__dirname, '..', 'src'));
m.filename = path.join(__dirname, '..', 'src', 'telas_teste.js');
m._compile(fonte, m.filename);

const espera = () => new Promise((r) => setTimeout(r, 30));
(async () => {
    instancia.emit('initialized');
    await espera();
    const registro = fs.readFileSync(path.join(tmp, 'registro.txt'), 'utf8');
    if (!registro.includes('telas prontas') || /FALTANDO|ERRO/.test(registro)) console.log(registro);
    confere(registro.includes('telas prontas') && !registro.includes('FALTANDO') && !registro.includes('ERRO'), 'o app achou tudo');
    confere(fs.existsSync(path.join(tmp, 'painel.png')), 'imagens copiadas');
    confere(registrados.length === 4 && registrados.every((a) => a.startsWith(tmp)), 'imagens registradas na interface antes de usar');
    for (const v of VARIANTES) {
        const e = estado(v);
        chamadas.length = 0;
        rhmi.emit('userEvent', { eventType: 'ACTION', sourceId: nomes[botao(v).nome], parameterMap: {} });
        await espera();
        confere(chamadas.some((c) => c.abre === e.nome), `o botão abre a variante ${v.n}`);
        for (let i = 0; i < ITENS.length; i++) {
            chamadas.length = 0;
            if (i % 2) {
                comps[e.item(i).nome].emit('focus', { value: true });
            } else {
                rhmi.emit('userEvent', { eventType: 'FOCUS', sourceId: nomes[e.item(i).nome], parameterMap: { 0: true } });
            }
            await espera();
            e.pecas.forEach((p) => {
                const t = chamadas.find((c) => c.nome === p.nome && c.cell === 'Text');
                confere(p.texto ? t && t.value.includes(ITENS[i].dica) : !t, `variante ${v.n}, item ${i}, ${p.widget}: texto`);
                const g = chamadas.find((c) => c.nome === p.nome && c.cell === 'Graphic');
                confere(p.desenho ? g && g.type === 'ResourceId' && g.value === path.join(tmp, `${ITENS[i].imagem}.png`) : !g,
                    `variante ${v.n}, item ${i}, ${p.widget}: desenho`);
            });
            const ultimo = chamadas.map((c) => !!c.flush).lastIndexOf(true);
            confere(ultimo === chamadas.length - 1, `variante ${v.n}, item ${i}: flush depois das escritas`);
        }
        chamadas.length = 0;
        comps[e.item(0).nome].emit('focus', { value: false });
        await espera();
        confere(!chamadas.length, `variante ${v.n}: perder o foco não muda nada`);
    }
    fs.rmSync(tmp, { recursive: true, force: true });
    console.log(`${ok} conferências ok`);
})().catch((err) => { console.error(err); process.exit(1); });
