# Teste de telas

Um app à parte, só para experimentar, sem mexer no Mapas no painel
([idrive-apps](https://github.com/robertnisipeanu/idrive-apps)). A ideia é
dar ao menu do Mapas no painel as explicações que alguns menus da BMW
mostram: uma lista estreita à esquerda e, à direita, o texto e o desenho do
item que o seletor destaca.

A interface da central conhece telas com essa prévia e peças próprias para
ela. Não sabemos se um app de fora pode usá-las, nem em que grupo da tela as
peças vão; cada variante tenta uma combinação.

**0.0.1 (26/11):** as telas abriram e o foco nos itens chega ao app.
`LT_State_Regular_ContentHidden` é a lista estreita das configurações da BMW,
com a direita vazia; `LT_State_Wide_1List_Static_Preview` é a lista larga com
uma faixa vazia à direita; `LT_State_Regular_ContentHidden_PreviewLeft` põe a
lista à direita. Um label comum nos grupos `ContentPreview` e `Content` não
apareceu, e os desenhos falharam por não estarem registrados na interface.

**0.0.2 (26/11):** as peças de prévia da interface em vários grupos. Só o
grupo `PreviewMap`, na `LT_State_Regular_ContentHidden`, desenhou à direita:
o desenho do item no alto e uma linha de texto embaixo, cortada. Os outros
grupos deixaram a direita vazia.

**0.0.4:** em vez de adivinhar, o caminho que os apps da própria BMW usam
(o `x_call`, que vem instalado na central). A tela aponta, pela propriedade
`Preview` (id 4), um componente do tipo `preview` com uma peça
`LT_PreviewTable_*` no grupo `ContentPreview`. O app escreve a explicação na
célula `Description` e o desenho na `Illustration`.

| Variante | Tela | Peça |
|---|---|---|
| 1 | `Regular_ContentHidden` | `LT_PreviewTable_Left_1Graphic_1Text_Bottom` (a do `x_call`) |
| 2 | `Regular_ContentHidden` | `LT_PreviewTable_Left_1Graphic_1Text_Top` |
| 3 | `Regular_ContentHidden` | `LT_PreviewTable_1Graphic_1TextBottom` |
| 4 | `Regular_ContentHidden` | `LT_PreviewTable_1Graphic_1Text2Row` |
| 5 | `Regular_ContentHidden` | `LT_PreviewTable_1Graphic_1Text3Row` |
| 6 | `Regular_ContentHidden` | `LT_PreviewTable_1Text` |
| 7 | `Wide_1List_Static_Preview` | `LT_PreviewTable_Left_1Graphic_1Text_Bottom` |
| 8 | `CallScreen` (a tela do `x_call`) | `LT_PreviewTable_Left_1Graphic_1Text_Bottom` |

A 0.0.3 (labels no `PreviewMap`) foi substituída antes de ir ao carro.

Os itens são os do Mapas no painel, com dicas de exemplo. Apertar um item
não faz nada: o app só mostra.

## Como testar

1. Com o carro **parado**, instale **Teste de telas** pela loja (fonte
   `italomoraes/zelador-carro`).
2. Abra o app e entre em cada variante. Gire o seletor sobre os itens e veja
   se a direita mostra a explicação e o desenho, e se troca com animação.
3. Fotografe ou filme cada variante.
4. Remova o app pela loja.

O que o app anota (início, telas abertas, focos, erros) fica em
`/dev/shm/italo_telas_teste/registro.txt`, na RAM da central, até ela
desligar.

## Arquivos

- `src/variantes.js`: os itens, as dicas e as variantes.
- `src/telas_teste.js`: o app.
- `tools/gerar.js`: escreve o uiDescription, os textos e o `application.json`
  a partir de `src/variantes.js` (`node tools/gerar.js`).
- `tools/teste.js`: testa o app no computador, com um oap-sdk de mentira
  (`node tools/teste.js`).

O ciclo de vida do app segue o do Mapas no painel e o da loja, de Robert
Nisipeanu; por isso esta pasta é GPL-3.0-or-later (`LICENSE`). O resto do
repositório é MIT.
