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
        tipo: 'lista',
        opcoes: ['Painel de instrumentos', 'HUD', 'Painel e HUD', 'Nenhum'],
        previa: 'texto',
        dica: 'Escolhe onde o mapa do celular aparece: no painel de instrumentos, no HUD, nos dois ou em nenhum.',
        longa: 'Escolhe onde o mapa do celular aparece: no painel de instrumentos, no HUD (a projeção no para-brisa), nos dois ou em nenhum. No painel, o mapa ocupa o lugar do da BMW enquanto a navegação do celular está ativa; no HUD, aparece a seta da próxima manobra. Para voltar ao normal, escolha Nenhum.',
        curta: 'Onde o mapa do celular aparece: painel, HUD, os dois ou nenhum.',
        imagem: 'painel'
    },
    {
        nome: 'Ocultar a caixa de seta da BMW',
        tipo: 'marca',
        previa: 'desenho',
        dica: 'Esconde a seta de manobra da BMW enquanto o nosso mapa está no painel, para não aparecer em dobro.',
        longa: 'Esconde o quadro de manobra da navegação da BMW enquanto o nosso mapa está no painel, para a seta não aparecer em dobro. Quando o nosso mapa sai do painel, o quadro da BMW volta sozinho. Desligue se você prefere ver as duas setas ao mesmo tempo.',
        curta: 'Esconde a seta da BMW enquanto o nosso mapa está no painel.',
        imagem: 'seta'
    },
    {
        nome: 'CarPlay: Patch',
        tipo: 'marca',
        previa: 'desenho',
        dica: 'Libera o mapa do CarPlay no painel, para Google Maps e Waze. O Apple Maps tem o seu próprio mapa no painel.',
        longa: 'Libera o mapa do CarPlay no painel, para Google Maps e Waze. O Apple Maps já tem o seu próprio mapa no painel e não precisa disto. O patch muda o programa do CarPlay na central; para desfazer, desligue aqui e reinicie a central pelo app ou pela Loja.',
        curta: 'Mapa do CarPlay no painel, para Google Maps e Waze.',
        imagem: 'celular'
    },
    {
        nome: 'Android Auto',
        tipo: 'marca',
        previa: 'desenho',
        dica: 'O mesmo para o Android Auto: o patch põe o mapa no painel, e o zoom muda a escala.',
        longa: 'O mesmo para o Android Auto: o patch põe o mapa do celular no painel, e o zoom muda a escala do mapa. Funciona com Google Maps e Waze. Para desfazer, desligue aqui e reinicie a central pelo app ou pela Loja.',
        curta: 'O mesmo para o Android Auto, com zoom.',
        imagem: 'celular'
    },
    {
        nome: 'Salvar logs',
        tipo: 'botao',
        previa: 'desenho',
        dica: '"Salvar logs" guarda os últimos minutos. Toque logo depois de um problema; ele chega em casa sozinho.',
        longa: '"Salvar logs" guarda o que já aconteceu nos últimos minutos. Toque logo depois de um problema: os registros ficam no carro e chegam em casa sozinhos, pela internet do carro. Nada é enviado para outro lugar.',
        curta: 'Guarda os últimos minutos. Toque logo depois de um problema.',
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
    baixo: prev('LT_PreviewTable_1Graphic_1TextBottom'),
    duasLinhas: prev('LT_PreviewTable_1Graphic_1Text2Row'),
    tresLinhas: prev('LT_PreviewTable_1Graphic_1Text3Row'),
    soTexto: Object.assign(prev('LT_PreviewTable_1Text'), { desenho: false }),
    seisLinhas: Object.assign(prev('LT_PreviewTable_Speller_6Row_1TextDyn'), { desenho: false }),
    /* Título e texto, nas células que as definições da interface dão (Spec_PreviewTables). */
    tituloTexto: Object.assign(prev('LT_PreviewTable_1Graphic_2Text2Row'), { celTitulo: 'Text1', celTexto: 'Text2' }),
    cimaBaixo: Object.assign(prev('LT_PreviewTable_1Graphic_1TextTop_1TextBottom'),
        { celTitulo: 'Title_Text', celTexto: 'Description_Text', celDesenho: 'Illustration_Graphic' })
};

/* Cada variante: a tela, o grupo da prévia (ContentPreview, como no x_call),
 * as peças, os desenhos e a dica. Até a 0.0.6 os itens eram botões simples;
 * a 0.0.7 monta o menu como os da BMW (Attention Assist, modo manobrista):
 * "Mostrar em" é uma lista de opções (dropDownMenu, como no Mapas no painel)
 * e o resto são caixas de marcar e um botão. Sem texto no topo da lista: a
 * explicação fica toda à direita, só texto (1Text, até ~10 linhas) para o
 * "Mostrar em" e desenho com 3 linhas (1Graphic_1TextBottom) para os outros.
 *   menu: a peça da lista de opções;
 *   troca: como a prévia muda de peça entre os itens ('preview': a tela
 *     aponta outra peça pela propriedade Preview; 'visivel': as duas peças
 *     ficam no grupo e uma é escondida); sem troca, uma peça só.
 *   imagens: '' o desenho pequeno; 'baixo' / 'cima' 957×639 com a faixa do
 *   texto livre embaixo / em cima; 'regua' a régua.
 *   dica: '' a dica (até 3 linhas); 'curta'; 'longa'. Nas variantes com
 *   menu, cada item usa a longa se a prévia dele é só texto. */
const REGULAR = 'LT_State_Regular_ContentHidden';
/* A 0.0.7 mostrou que o dropDownMenu (2Row ou 1Row) abre as opções numa
 * janela por cima, como no Mapas no painel; a lista que abre no lugar, com
 * bolinhas (Attention Assist), é o valueList (LT_ValueList_Regular: cabeçalho
 * LT_Button_ValueList_Header e opções LT_RadioButton_ValueList_Regular).
 * Trocar a peça da prévia pela propriedade Preview funciona, mas a direita
 * fica vazia ~0,6 s; Visible é recusado (INVALID_PROPERTYID). A 0.0.8:
 * a lista de opções no lugar e três jeitos de explicar. */
const VARIANTES = [
    { n: 1, widget: REGULAR, previa: 'ContentPreview', menu: 'LT_ValueList_Regular', pecas: ['baixo'], imagens: 'baixo' },
    { n: 2, widget: REGULAR, previa: 'ContentPreview', menu: 'LT_ValueList_Regular', pecas: ['soTexto'], imagens: '', dica: 'longa' },
    { n: 3, widget: REGULAR, previa: 'ContentPreview', menu: 'LT_ValueList_Regular', pecas: ['soTexto', 'baixo'], troca: 'preview', preenche: true, imagens: 'baixo' }
];

/* A peça da prévia que mostra o item i na variante v (o índice em pecas). */
const pecaDoItem = (v, i) => {
    if (!v.troca) {
        return 0;
    }
    return ITENS[i].previa === 'texto' ? v.pecas.indexOf('soTexto') : v.pecas.indexOf('baixo');
};

/* O que a variante v mostra para o item i: o texto e o nome do desenho. */
const conteudo = (v, i) => {
    const it = ITENS[i];
    return {
        titulo: it.nome,
        texto: v.dica ? it[v.dica] : (v.troca && it.previa === 'texto' ? it.longa : it.dica),
        imagem: v.imagens === 'regua' ? 'regua' : (v.imagens ? `${it.imagem}-${v.imagens}` : it.imagem)
    };
};

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

module.exports = { ITENS, PECAS, VARIANTES, ENTRADA, estado, botao, INFO, conteudo, pecaDoItem };
