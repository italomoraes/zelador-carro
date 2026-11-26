// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * O que o app de teste mostra: a página de entrada (uma tela larga comum, que
 * já sabemos que funciona) com um botão por variante, e cada variante numa
 * tela própria. Lido pelo app (src/telas_teste.js) e pelo gerador do
 * uiDescription (tools/gerar.js), para os ids e nomes andarem juntos.
 *
 * Todas usam o componente de prévia da BMW (tipo "preview"); cada variante
 * testa uma tela ou uma peça LT_PreviewTable_*.
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

/* As peças que vão na prévia. A 0.0.3 tentava labels; a 0.0.4 segue o que
 * os apps da própria BMW fazem (x_call, no backup da central): um componente
 * do tipo "preview" com uma peça LT_PreviewTable_*, apontado pela
 * propriedade Preview (id 4) da tela, com a explicação na célula Description
 * e o desenho na Illustration. */
const prev = (widget) => ({ widget, componente: 'preview', texto: true, desenho: true,
    celTexto: 'Description', celDesenho: 'Illustration' });
const PECAS = {
    esqBaixo: prev('LT_PreviewTable_Left_1Graphic_1Text_Bottom'),
    esqCima: prev('LT_PreviewTable_Left_1Graphic_1Text_Top'),
    baixo: prev('LT_PreviewTable_1Graphic_1TextBottom'),
    duasLinhas: prev('LT_PreviewTable_1Graphic_1Text2Row'),
    tresLinhas: prev('LT_PreviewTable_1Graphic_1Text3Row'),
    soTexto: Object.assign(prev('LT_PreviewTable_1Text'), { desenho: false })
};

/* Cada variante: a tela, o grupo da prévia (ContentPreview, como no x_call)
 * e a peça. A 0.0.2 mostrou que labels comuns só aparecem no PreviewMap; a
 * 0.0.4 testa o caminho da BMW. A 8 é a tela exata do x_call, a referência. */
const REGULAR = 'LT_State_Regular_ContentHidden';
const VARIANTES = [
    { n: 1, widget: REGULAR, previa: 'ContentPreview', pecas: ['esqBaixo'] },
    { n: 2, widget: REGULAR, previa: 'ContentPreview', pecas: ['esqCima'] },
    { n: 3, widget: REGULAR, previa: 'ContentPreview', pecas: ['baixo'] },
    { n: 4, widget: REGULAR, previa: 'ContentPreview', pecas: ['duasLinhas'] },
    { n: 5, widget: REGULAR, previa: 'ContentPreview', pecas: ['tresLinhas'] },
    { n: 6, widget: REGULAR, previa: 'ContentPreview', pecas: ['soTexto'] },
    { n: 7, widget: 'LT_State_Wide_1List_Static_Preview', previa: 'ContentPreview', pecas: ['esqBaixo'] },
    { n: 8, widget: 'LT_State_CallScreen', previa: 'ContentPreview', pecas: ['esqBaixo'] }
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
