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

**0.0.4 (26/11):** funciona nas 8 variantes, com a troca animada. As peças
`1Graphic_*` põem o desenho de fundo na área inteira da prévia e o texto por
cima (como nas configurações da BMW); as `Left_*` reservam um lugar pequeno
para o desenho e cortam o texto na 3ª linha.

**0.0.5:** desenhos no tamanho da área. Pelas definições da interface, a
prévia dessa tela tem 957×639 em unidades de 1920×720, e as telas menores
(1600×600, 1440×540, 1280×480) reduzem tudo por igual; um desenho nesse
tamanho deve servir a todas. `tools/desenhos.swift` desenha cada imagem
nesse tamanho, com a faixa do texto livre, e uma régua.

| Variante | Peça | Desenho | Dica |
|---|---|---|---|
| 1 | `1Graphic_1TextBottom` | 957×639, texto embaixo | completa |
| 2 | `1Graphic_1Text2Row` | 957×639, texto em cima | completa |
| 3 | `1Graphic_1Text3Row` | 957×639, texto em cima | completa |
| 4 | `Left_1Graphic_1Text_Bottom` | pequeno (300×220) | curta |
| 5 | `1Graphic_1TextBottom` | régua | completa |
| 6 | `Left_1Graphic_1Text_Bottom` | régua | curta |

**0.0.5 (26/11):** a variante 1 (`1Graphic_1TextBottom` com o desenho de
957×639) fica como nas configurações da BMW, e a régua confirmou a área. O
texto tem no máximo 3 linhas, de 791 de largura com letra 42: o que sobra
vai para a 3ª linha e é cortado no meio da letra.

**0.0.6:** as dicas encurtadas para caber em 3 linhas, e peças que podem
mostrar mais texto:

| Variante | Peça | Desenho | Texto |
|---|---|---|---|
| 1 | `1Graphic_1TextBottom` | 957×639, texto embaixo | dica (3 linhas) |
| 2 | `1Text` | sem desenho | longa |
| 3 | `Speller_6Row_1TextDyn` | sem desenho | longa |
| 4 | `1Graphic_2Text2Row` (título em `Text1`, texto em `Text2`) | régua | dica |
| 5 | `1Graphic_2Text2Row` | 957×639, texto embaixo | longa |
| 6 | `1Graphic_1TextTop_1TextBottom` (`Title_Text`, `Description_Text`) | régua | longa |

**O tamanho dos textos:** `tools/cabe.js` quebra o texto como a central,
com a fonte da própria interface (o `BMWTALG.ttf` de
`/mnt/dataro/data/hmi/common/font` na central, que não vem neste
repositório), e as linhas batem com as fotos. Com `BMW_FONT` apontando para
ela, `tools/teste.js` confere que cada dica cabe em 3 linhas.

**0.0.6 (26/11):** a `1Text` mostra a explicação longa inteira (8 linhas, a
área comporta ~10); as peças com título só mostram 1 ou 2 linhas.

**0.0.7:** o menu como os da BMW (Attention Assist, modo manobrista), sem
texto no topo da lista. "Mostrar em" é uma lista de opções
(`dropDownMenu`, como no Mapas no painel) com a explicação longa à direita,
só texto (`1Text`); os outros itens são caixas de marcar e um botão, com
desenho e 3 linhas (`1Graphic_1TextBottom`). A prévia troca de peça entre
os itens:

| Variante | Lista de opções | Como a prévia troca de peça |
|---|---|---|
| 1 | `LT_DropDownMenu_2Row` (nome e valor embaixo) | a tela aponta a outra peça (propriedade `Preview`) |
| 2 | `LT_DropDownMenu_2Row` | as duas peças no grupo, uma escondida (`Visible`) |
| 3 | `LT_DropDownMenu_2Row` | uma peça só (desenho e 3 linhas para todos) |
| 4 | `LT_DropDownMenu_1Row_2Col3070` (a de hoje no Mapas no painel) | propriedade `Preview` |

**0.0.7 (26/11):** o `dropDownMenu` (2Row e 1Row) abre as opções numa janela
por cima, como no Mapas no painel hoje. Trocar a peça da prévia pela
propriedade `Preview` funciona, mas a direita fica vazia por ~0,6 s;
`Visible` numa peça de prévia é recusado (`INVALID_PROPERTYID`).

**0.0.8:** a lista de opções que abre no lugar, com bolinhas, como no
Attention Assist: o tipo `valueList` com a peça `LT_ValueList_Regular`
(células `HeaderText`, `SelectedItem` e `ItemText`, as que a interface
aceita para ele).

| Variante | Prévia |
|---|---|
| 1 | desenho e 3 linhas para todos os itens (`1Graphic_1TextBottom`) |
| 2 | só texto, a explicação longa, para todos (`1Text`) |
| 3 | troca de peça como na 0.0.7, mas com a peça nova preenchida antes da troca |

**0.0.8 (26/11):** o `valueList` abre as opções no lugar, com bolinhas,
mas fechado não mostra a opção escolhida embaixo do nome. Trocar o tipo da
prévia deixa a direita vazia mesmo com a peça nova preenchida antes.

**0.0.9:** um tipo de prévia por menu e o valor embaixo do nome:

| Variante | Valor embaixo do nome | Prévia |
|---|---|---|
| 1 | as opções levam `ItemSelectionText` | só texto (longa) |
| 2 | o app escreve `SelectedItem` ao abrir e a cada escolha | só texto (longa) |
| 3 | os dois | desenho e 3 linhas |

O app anota os eventos crus da lista, para ver se o foco nas opções chega.

**0.0.9 (27/11):** o valor escolhido aparece embaixo do nome quando as
opções levam `ItemSelectionText`; escrever `SelectedItem` pelo app não
basta. A lista aberta manda o foco com o número da opção
(`parameterMap[2]`, e 4294967295 quando o foco está no nome).

**0.1.0:** cada opção do "Mostrar em" tem a sua explicação e o seu
desenho, com um tipo de prévia só no menu:

| Variante | Prévia |
|---|---|
| 1 | desenho e 3 linhas em tudo, opções incluídas |
| 2 | só texto em tudo; a explicação longa nos itens e a curta nas opções |

**0.1.0 (27/11):** ficou como queríamos: desenho e 3 linhas em tudo, uma
explicação e um desenho por opção.

**0.1.1:** a animação das configurações da BMW. Nos vídeos, o desenho novo
entra em ~0,8 s: o traço fino se desenha aos pedaços, engrossa e acende,
com um brilho vermelho atrás e uma grade de pontos. A peça de prévia só
recebe imagens paradas, então `tools/desenhos.swift` desenha 8 quadros
(`<nome>-anim0` a `7`) e o app troca o desenho quadro a quadro:

| Variante | Desenho |
|---|---|
| 1 | parado (o último quadro, com o brilho) |
| 2 | 8 quadros, um a cada 80 ms |
| 3 | 4 quadros, um a cada 160 ms |

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
- `tools/desenhos.swift`: as imagens de `package/imagens` (`swift tools/desenhos.swift package/imagens`).
- `tools/cabe.js`: em quantas linhas um texto quebra na prévia (`BMW_FONT=... node tools/cabe.js "texto"`).
- `tools/teste.js`: testa o app no computador, com um oap-sdk de mentira
  (`node tools/teste.js`).

O ciclo de vida do app segue o do Mapas no painel e o da loja, de Robert
Nisipeanu; por isso esta pasta é GPL-3.0-or-later (`LICENSE`). O resto do
repositório é MIT.
