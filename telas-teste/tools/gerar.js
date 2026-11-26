// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * Escreve o uiDescription do app de teste (application.xml e
 * uiDescription.json, iDrive 7), os textos do RHMI e o application.json, a
 * partir de src/variantes.js. O formato segue o do Mapas no painel e da loja
 * (robertnisipeanu/idrive-apps e mgu-store).
 *
 *   node tools/gerar.js
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { ITENS, VARIANTES, ENTRADA, estado, botao, INFO } = require('../src/variantes.js');

const APP = require('../mgu-app.json');
const PKG = path.join(__dirname, '..', APP.tree);
const RHMI = path.join(PKG, 'rhmiData');
const ID7 = path.join(RHMI, 'uiDescriptions', 'ID7');
const TEXTOS = path.join(RHMI, 'variantGroups', 'Common', 'texts');
const TITULO = 'Teste de telas';

/* Os arquivos de texto do RHMI que o Mapas no painel traz (um por idioma). */
const IDIOMAS = ['ar_AE', 'cs_CZ', 'da_DK', 'de_DE', 'el_GR', 'en_GB', 'en_US', 'es_ES', 'es_MX', 'fi_FI',
    'fr_CA', 'fr_FR', 'he_IL', 'hu_HU', 'id_ID', 'it_IT', 'ja_JP', 'ko_KR', 'nl_BE', 'nl_NL', 'no_NO', 'pl_PL',
    'pt_BR', 'pt_PT', 'ro_RO', 'ru_RU', 'sk_SK', 'sl_SI', 'sv_SE', 'th_TH', 'tr_TR', 'uk_UA', 'vi_VN', 'zh_CN',
    'zh_TW', 'zh_yue_Hans_CN', 'zh_yue_Hant_CN'];

/* Os estados, cada um com os seus grupos e componentes. */
function estados() {
    const entrada = {
        id: ENTRADA.id, nome: ENTRADA.nome, widget: 'LT_State_Wide', titulo: ENTRADA.titulo,
        grupos: [{ nome: 'List', componentes: [
            { id: INFO.id, nome: INFO.nome, tipo: 'label', widget: 'LT_Label_4Row_1TextDyn', foco: 0,
                celulas: { Text: 'Cada botão abre uma versão da tela de dicas. Gire o botão sobre os itens e veja se a explicação aparece.' } }
        ].concat(VARIANTES.map((v) => ({
            id: botao(v).id, nome: botao(v).nome, tipo: 'button', widget: 'LT_Button_1Row', foco: 3,
            celulas: { Text: `Variante ${v.n}: ${estado(v).pecas.map((p) => p.widget.replace(/^LT_(Label|PreviewTable)_/, '')).join(' + ')}${!estado(v).pecas.some((p) => p.desenho) ? ' / sem desenho' : v.imagens ? ` / desenho ${v.imagens}` : ' / desenho pequeno'}${v.dica ? ` / dica ${v.dica}` : ''}` }
        }))) }]
    };
    const variantes = VARIANTES.map((v) => {
        const e = estado(v);
        const itens = ITENS.map((it, i) => ({
            id: e.item(i).id, nome: e.item(i).nome, tipo: 'button', widget: 'LT_Button_1Row', foco: 3, celulas: { Text: it.nome }
        }));
        const pecas = e.pecas.map((p) => p.componente === 'preview' ?
            { id: p.id, nome: p.nome, tipo: 'preview', widget: p.widget, simples: true, celulas: {} } :
            { id: p.id, nome: p.nome, tipo: 'label', widget: p.widget, foco: 0, celulas: p.texto ? { Text: ITENS[0].dica } : {} });
        const previa = e.pecas.find((p) => p.componente === 'preview');
        const grupos = v.previa === 'List' ?
            [{ nome: 'List', componentes: itens.concat(pecas) }] :
            [{ nome: v.previa, id: 300 + e.id, componentes: pecas }, { nome: 'List', componentes: itens }]; // a prévia antes, como no x_call
        return { id: e.id, nome: e.nome, widget: v.widget, titulo: e.titulo, pai: ENTRADA.id, previa: previa && previa.id, grupos };
    });
    return [entrada].concat(variantes);
}

function xml() {
    const l = ['<?xml version="1.0" encoding="UTF-8"?>', '<!-- SPDX-License-Identifier: GPL-3.0-or-later -->', '<application>'];
    estados().forEach((s) => {
        l.push(`    <container id="${s.id}" type="state" widget="${s.widget}">`);
        if (s.pai) {
            l.push(`        <property id="9" value="${s.pai}"/>`);
        }
        if (s.previa) {
            l.push(`        <property id="4" value="${s.previa}"/>`);
        }
        l.push(`        <layoutGroup id="${100 + 2 * s.id}" name="Titlebar">`,
            `            <component id="${s.titulo}" type="title">`,
            '                <property id="2" value="1"/>',
            '            </component>',
            '        </layoutGroup>');
        s.grupos.forEach((g) => {
            l.push(`        <layoutGroup id="${g.id || 101 + 2 * s.id}" name="${g.nome}">`);
            if (!g.componentes.every((c) => c.simples)) {
                l.push('            <property id="3" value="1"/>'); // como no x_call, o grupo só da prévia vai sem ela
            }
            g.componentes.forEach((c) => {
                if (c.simples) {
                    l.push(`            <component id="${c.id}" type="${c.tipo}" widget="${c.widget}"/>`);
                    return;
                }
                l.push(`            <component id="${c.id}" type="${c.tipo}" widget="${c.widget}">`,
                    '                <property id="2" value="1"/>',
                    `                <property id="3" value="${c.foco}"/>`,
                    '            </component>');
            });
            l.push('        </layoutGroup>');
        });
        l.push('    </container>');
    });
    l.push('</application>', '');
    return l.join('\n');
}

function uiDescription() {
    const containers = {};
    estados().forEach((s) => {
        const components = {
            [s.titulo]: {
                type: 'title', name: `${s.nome}_Title`,
                properties: { Visible: { value: 1, type: 'UInt' } },
                rows: [{ Text: { value: 'SID_TELAS_TITLE', type: 'StringId' } }]
            }
        };
        s.grupos.forEach((g) => g.componentes.forEach((c) => {
            const cells = {};
            Object.keys(c.celulas).forEach((k) => { cells[k] = { value: c.celulas[k], type: 'Text' }; });
            if (c.simples) {
                components[c.id] = { type: c.tipo, name: c.nome };
                return;
            }
            components[c.id] = {
                type: c.tipo, name: c.nome,
                properties: { Visible: { value: 1, type: 'UInt' }, Focusable: { value: c.foco, type: 'UInt' } },
                rows: [cells]
            };
        }));
        const props = {};
        if (s.pai) {
            props.ParentState = { value: s.pai, type: 'UInt' };
        }
        if (s.previa) {
            props.Preview = { value: s.previa, type: 'UInt' };
        }
        containers[s.id] = Object.assign({ type: 'state', name: s.nome },
            Object.keys(props).length ? { properties: props } : {}, { components });
    });
    return { schemaVersion: '1.3.0', containers };
}

function applicationJson() {
    return {
        schemaVersion: '1.3.0',
        application: {
            uuid: '26f89071-6326-4283-a223-b454721b5165',
            type: 'OnlineApp',
            name: APP.id,
            vendor: 'Italo Moraes',
            version: APP.version,
            defaultLanguage: 'en_GB',
            uiDescriptions: [{
                applicationFilePath: './uiDescriptions/ID7/application.xml',
                uiDescriptionFilePath: './uiDescriptions/ID7/uiDescription.json',
                hmi: ['ID7']
            }],
            stringBundleUuid: '1b44a929-0597-460a-8141-201286c1a399',
            resourceBundleUuid: '3498781a-80e1-48ca-8db4-7aec2d7dd7f2',
            variantGroups: [{ stringsPath: './variantGroups/Common/texts', resourcesPath: './variantGroups/Common/images', hmi: ['ID7'], brands: ['BMW'] }],
            entryPoints: [{
                name: APP.id,
                uuid: 'fa8df646-325f-4b2a-b899-e60a0b8ef642',
                textId: 'SID_TELAS_TITLE',
                icon: 'italo_telas_teste_icon.png',
                insertionStateId: 20974,
                insertionFocusId: 2,
                insertionMode: 'INSERT_BELOW',
                insertionOrder: 0,
                insertionPriority: 0,
                previewType: 'NONE',
                bookmarkable: true,
                private: null,
                appearance: 'DEFAULT',
                isGroupHeader: false,
                insertionGroup: 0
            }]
        }
    };
}

function escreve(arq, conteudo) {
    fs.mkdirSync(path.dirname(arq), { recursive: true });
    fs.writeFileSync(arq, typeof conteudo === 'string' ? conteudo : JSON.stringify(conteudo, null, 2) + '\n');
}

function gerar() {
    escreve(path.join(ID7, 'application.xml'), xml());
    escreve(path.join(ID7, 'uiDescription.json'), uiDescription());
    escreve(path.join(RHMI, 'application.json'), applicationJson());
    IDIOMAS.forEach((n) => escreve(path.join(TEXTOS, `${n}.json`), { SID_TELAS_TITLE: TITULO }));
    const pkg = JSON.parse(fs.readFileSync(path.join(PKG, 'package.json'), 'utf8'));
    pkg.version = APP.version;
    escreve(path.join(PKG, 'package.json'), pkg);
    escreve(path.join(PKG, 'npm-shrinkwrap.json'), { name: APP.id, version: APP.version, lockfileVersion: 1, requires: true, dependencies: {} });
}

if (require.main === module) {
    gerar();
    const s = estados();
    console.log(`${s.length} estados, ${s.reduce((n, e) => n + e.grupos.reduce((m, g) => m + g.componentes.length, 0), 0)} componentes`);
}

module.exports = { estados, xml, uiDescription };
