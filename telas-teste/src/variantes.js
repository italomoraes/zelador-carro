// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * O que o app de teste mostra: a página de entrada (uma tela larga comum, que
 * já sabemos que funciona) com um botão por variante, e cada variante numa
 * tela própria. Lido pelo app (src/telas_teste.js) e pelo gerador do
 * uiDescription (tools/gerar.js), para os ids e nomes andarem juntos.
 *
 * As variantes 1 a 9 põem as peças de prévia da BMW em grupos de nomes
 * diferentes, nas duas telas com espaço à direita; não sabemos qual grupo a
 * interface desenha ali: é o que o teste mostra. A 10 é a tela larga de hoje
 * com a explicação e o desenho embaixo da lista, a reserva.
 */
'use strict';

/* Os itens de exemplo, com as dicas que o Mapas no painel poderia dar. */
const ITENS = [
    {
        nome: 'Mostrar em',
        dica: 'Escolhe onde o mapa do celular aparece: no painel de instrumentos, no HUD (a projeção no para-brisa), nos dois ou em nenhum.',
        imagem: 'painel'
    },
    {
        nome: 'Ocultar a caixa de seta da BMW',
        dica: 'Esconde o quadro de manobra da navegação da BMW enquanto o nosso mapa está no painel, para a seta não aparecer em dobro.',
        imagem: 'seta'
    },
    {
        nome: 'CarPlay: Patch',
        dica: 'Libera o mapa do CarPlay no painel, para Google Maps e Waze. O Apple Maps tem o seu próprio mapa no painel.',
        imagem: 'celular'
    },
    {
        nome: 'Android Auto',
        dica: 'O mesmo para o Android Auto: o patch põe o mapa no painel, e o zoom muda a escala.',
        imagem: 'celular'
    },
    {
        nome: 'Logs',
        dica: '"Salvar logs" guarda o que já aconteceu nos últimos minutos. Toque logo depois de um problema; ele chega em casa sozinho.',
        imagem: 'logs'
    }
];

/* As peças que vão na prévia. Cada uma é um label; o app escreve o texto
 * (Text) nas que têm texto e o desenho (Graphic) nas que têm desenho. As três
 * primeiras são peças de prévia que a interface da central conhece. */
const PECAS = {
    texto: { widget: 'LT_Label_1TextDyn_Preview', texto: true, desenho: false },
    combo: { widget: 'LT_Label_BON_Preview_1Graphic_1Text', texto: true, desenho: true },
    desenho: { widget: 'LT_Label_1Graphic_Scalable', texto: false, desenho: true },
    texto4: { widget: 'LT_Label_4Row_1TextDyn', texto: true, desenho: false }
};
const PREVIA = ['texto', 'combo', 'desenho'];

/* Cada variante: a tela (widget), o grupo da prévia e as peças dela. O grupo
 * 'List' põe as peças na própria lista, depois dos itens. Os nomes de grupo
 * vieram da interface da central (eGfxIdLayoutGroup_*). A 0.0.1 mostrou que
 * a Regular_ContentHidden é a lista estreita da BMW, com a direita vazia
 * (o grupo ContentPreview ou Content com um label comum não aparece), e que a
 * Wide_1List_Static_Preview deixa uma faixa vazia à direita. */
const VARIANTES = [
    { n: 1, widget: 'LT_State_Regular_ContentHidden', previa: 'ContentPreview', pecas: PREVIA },
    { n: 2, widget: 'LT_State_Regular_ContentHidden', previa: 'Content', pecas: PREVIA },
    { n: 3, widget: 'LT_State_Regular_ContentHidden', previa: 'ListStatic', pecas: PREVIA },
    { n: 4, widget: 'LT_State_Regular_ContentHidden', previa: 'Table', pecas: PREVIA },
    { n: 5, widget: 'LT_State_Regular_ContentHidden', previa: 'PreviewMap', pecas: PREVIA },
    { n: 6, widget: 'LT_State_Regular_ContentHidden', previa: 'MainGroup', pecas: PREVIA },
    { n: 7, widget: 'LT_State_Regular_ContentHidden', previa: 'List', pecas: PREVIA },
    { n: 8, widget: 'LT_State_Wide_1List_Static_Preview', previa: 'ContentPreview', pecas: PREVIA },
    { n: 9, widget: 'LT_State_Wide_1List_Static_Preview', previa: 'ListStatic', pecas: PREVIA },
    { n: 10, widget: 'LT_State_Wide', previa: 'List', pecas: ['texto4', 'desenho'] }
];

/* Ids: estados 1 (entrada) e 10 + n; grupos 100 + 2 * estado (título),
 * + 1 (lista) e 300 + estado (prévia); componentes 1000 + 100 * n + i
 * (itens a partir de + 1, peças a partir de + 20). */
const ENTRADA = { id: 1, nome: 'ST_ItaloTelas_Entrada', titulo: 2 };
const estado = (v) => ({
    id: 10 + v.n,
    nome: `ST_ItaloTelas_V${v.n}`,
    titulo: 1000 + 100 * v.n,
    item: (i) => ({ id: 1000 + 100 * v.n + 1 + i, nome: `telasV${v.n}Item${i}` }),
    pecas: v.pecas.map((k, i) => Object.assign({ id: 1000 + 100 * v.n + 20 + i, nome: `telasV${v.n}Peca${i}`, tipo: k }, PECAS[k]))
});
const botao = (v) => ({ id: 50 + v.n, nome: `telasAbre${v.n}` });
const INFO = { id: 40, nome: 'telasInfo' };

module.exports = { ITENS, PECAS, VARIANTES, ENTRADA, estado, botao, INFO };
