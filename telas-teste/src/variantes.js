// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * O que o app de teste mostra: a página de entrada (uma tela larga comum, que
 * já sabemos que funciona) com um botão por variante, e cada variante numa
 * tela própria. Lido pelo app (src/telas_teste.js) e pelo gerador do
 * uiDescription (tools/gerar.js), para os ids e nomes andarem juntos.
 *
 * Todas põem as peças no grupo PreviewMap, o único que a 0.0.2 mostrou à
 * direita; cada variante testa uma combinação de peças.
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
 * (Text) nas que têm texto e o desenho (Graphic) nas que têm desenho. Os
 * nomes vieram da interface da central (LT_Label_*). */
const PECAS = {
    texto: { widget: 'LT_Label_1TextDyn_Preview', texto: true, desenho: false },
    combo: { widget: 'LT_Label_BON_Preview_1Graphic_1Text', texto: true, desenho: true },
    desenho: { widget: 'LT_Label_1Graphic_Scalable', texto: false, desenho: true },
    desenhoFade: { widget: 'LT_Label_1FadingGraphic', texto: false, desenho: true },
    desenhoSimples: { widget: 'LT_Label_1Graphic', texto: false, desenho: true },
    textoTabela: { widget: 'LT_Label_1Text_PreviewTable', texto: true, desenho: false },
    texto4: { widget: 'LT_Label_4Row_1TextDyn', texto: true, desenho: false },
    texto5: { widget: 'LT_Label_5Row_1TextDyn_FixHeight', texto: true, desenho: false },
    texto6: { widget: 'LT_Label_6Row_1TextDyn', texto: true, desenho: false }
};

/* Cada variante: a tela (widget), o grupo da prévia e as peças dela. A 0.0.2
 * mostrou que só o grupo PreviewMap, na Regular_ContentHidden, desenha à
 * direita: um desenho no alto e uma linha de texto cortada embaixo. A 0.0.3
 * fica nesse grupo e separa as peças, para saber qual desenha o quê, e tenta
 * texto em várias linhas e o desenho com fade. */
const REGULAR = 'LT_State_Regular_ContentHidden';
const VARIANTES = [
    { n: 1, widget: REGULAR, previa: 'PreviewMap', pecas: ['texto'] },
    { n: 2, widget: REGULAR, previa: 'PreviewMap', pecas: ['combo'] },
    { n: 3, widget: REGULAR, previa: 'PreviewMap', pecas: ['desenho'] },
    { n: 4, widget: REGULAR, previa: 'PreviewMap', pecas: ['desenhoFade', 'texto4'] },
    { n: 5, widget: REGULAR, previa: 'PreviewMap', pecas: ['desenho', 'texto5'] },
    { n: 6, widget: REGULAR, previa: 'PreviewMap', pecas: ['desenhoSimples', 'texto6'] },
    { n: 7, widget: REGULAR, previa: 'PreviewMap', pecas: ['textoTabela'] },
    { n: 8, widget: 'LT_State_Wide_1List_Static_Preview', previa: 'PreviewMap', pecas: ['texto', 'combo', 'desenho'] },
    { n: 9, widget: REGULAR, previa: 'PreviewMap', pecas: ['texto', 'combo', 'desenho'] }
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
