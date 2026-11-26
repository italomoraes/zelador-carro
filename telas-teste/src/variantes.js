// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * O que o app de teste mostra: a página de entrada (uma tela larga comum, que
 * já sabemos que funciona) com um botão por variante, e cada variante numa
 * tela própria. Lido pelo app (src/telas_teste.js) e pelo gerador do
 * uiDescription (tools/gerar.js), para os ids e nomes andarem juntos.
 *
 * As variantes 1 a 5 tentam as telas da BMW com uma prévia à direita (os
 * nomes vieram da interface da central: LT_State_Wide_1List_Static_Preview,
 * LT_State_Regular_ContentHidden e LT_State_Regular_ContentHidden_PreviewLeft,
 * e os grupos ContentPreview e Content). Não sabemos se a BMW deixa um app de
 * fora usar essas telas, nem com que nome de grupo: é o que o teste mostra.
 * A 6 é a tela larga de hoje com a explicação embaixo da lista, a reserva.
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

/* Cada variante: a tela (widget), o grupo da lista e o da prévia (null: a
 * explicação vai na própria lista, embaixo dos itens). */
const VARIANTES = [
    { n: 1, widget: 'LT_State_Wide_1List_Static_Preview', lista: 'List', previa: 'ContentPreview' },
    { n: 2, widget: 'LT_State_Wide_1List_Static_Preview', lista: 'List', previa: 'Content' },
    { n: 3, widget: 'LT_State_Regular_ContentHidden', lista: 'List', previa: 'Content' },
    { n: 4, widget: 'LT_State_Regular_ContentHidden', lista: 'List', previa: 'ContentPreview' },
    { n: 5, widget: 'LT_State_Regular_ContentHidden_PreviewLeft', lista: 'List', previa: 'ContentPreview' },
    { n: 6, widget: 'LT_State_Wide', lista: 'List', previa: null }
];

/* Ids: estados 1 (entrada) e 10 + n; grupos 100 + 2 * estado (título),
 * + 1 (lista) e 300 + estado (prévia); componentes 1000 + 100 * n + i. */
const ENTRADA = { id: 1, nome: 'ST_ItaloTelas_Entrada', titulo: 2 };
const estado = (v) => ({
    id: 10 + v.n,
    nome: `ST_ItaloTelas_V${v.n}`,
    titulo: 1000 + 100 * v.n,
    item: (i) => ({ id: 1000 + 100 * v.n + 1 + i, nome: `telasV${v.n}Item${i}` }),
    texto: { id: 1000 + 100 * v.n + 20, nome: `telasV${v.n}Texto` },
    imagem: { id: 1000 + 100 * v.n + 21, nome: `telasV${v.n}Imagem` }
});
const botao = (v) => ({ id: 50 + v.n, nome: `telasAbre${v.n}` });
const INFO = { id: 40, nome: 'telasInfo' };

module.exports = { ITENS, VARIANTES, ENTRADA, estado, botao, INFO };
