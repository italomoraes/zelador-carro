# Teste de telas

Um app à parte, só para experimentar, sem mexer no Mapas no painel
([idrive-apps](https://github.com/robertnisipeanu/idrive-apps)). A ideia é
dar ao menu do Mapas no painel as explicações que alguns menus da BMW
mostram: uma lista estreita à esquerda e, à direita, o texto e o desenho do
item que o seletor destaca.

A interface da central conhece telas com essa prévia
(`LT_State_Wide_1List_Static_Preview`, `LT_State_Regular_ContentHidden`,
`LT_State_Regular_ContentHidden_PreviewLeft`) e grupos com os nomes
`ContentPreview` e `Content`. Mas não sabemos se um app de fora pode usá-las,
nem com que grupo. Cada variante tenta uma combinação:

| Variante | Tela | Grupo da prévia |
|---|---|---|
| 1 | `LT_State_Wide_1List_Static_Preview` | `ContentPreview` |
| 2 | `LT_State_Wide_1List_Static_Preview` | `Content` |
| 3 | `LT_State_Regular_ContentHidden` | `Content` |
| 4 | `LT_State_Regular_ContentHidden` | `ContentPreview` |
| 5 | `LT_State_Regular_ContentHidden_PreviewLeft` | `ContentPreview` |
| 6 | `LT_State_Wide` (a tela de hoje) | nenhum: a explicação vai embaixo da lista |

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
