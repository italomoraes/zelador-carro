// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * Mede em quantas linhas um texto quebra na prévia da central, com a fonte
 * da própria interface. A fonte é da BMW e não vem no repositório: o caminho
 * vem de BMW_FONT (o BMWTALG.ttf de /mnt/dataro/data/hmi/common/font, a que
 * a prévia usa). Sem ela, quem chama pula a conferência.
 *
 * Medidas da prévia (definições da interface, em unidades de 1920×720):
 * texto de 791 de largura (ContentPreviewTextW_ID7) e letra 42
 * (fontSizePreviewTable_ID7). A quebra é por palavra, como a da central;
 * conferido com fotos do carro (as linhas batem palavra por palavra).
 *
 *   BMW_FONT=... node tools/cabe.js "texto" ...
 */
'use strict';
const fs = require('fs');

const LARGURA = 791;
const TAMANHO = 42;

/* Lê do TTF só o necessário: unidades por em, larguras (hmtx) e o mapa de
 * caracteres (cmap formatos 4 e 12). */
function carregaFonte(arquivo) {
    const b = fs.readFileSync(arquivo);
    const tabelas = {};
    const n = b.readUInt16BE(4);
    for (let i = 0; i < n; i++) {
        const o = 12 + 16 * i;
        tabelas[b.toString('latin1', o, o + 4)] = b.readUInt32BE(o + 8);
    }
    const em = b.readUInt16BE(tabelas.head + 18);
    const nLargas = b.readUInt16BE(tabelas.hhea + 34);
    const larguraDoGlifo = (g) => b.readUInt16BE(tabelas.hmtx + 4 * Math.min(g, nLargas - 1));
    const mapa = new Map();
    const cmap = tabelas.cmap;
    const nSub = b.readUInt16BE(cmap + 2);
    for (let i = 0; i < nSub; i++) {
        const plat = b.readUInt16BE(cmap + 4 + 8 * i);
        const enc = b.readUInt16BE(cmap + 6 + 8 * i);
        const o = cmap + b.readUInt32BE(cmap + 8 + 8 * i);
        const formato = b.readUInt16BE(o);
        if (plat !== 3 && plat !== 0) {
            continue;
        }
        if (formato === 4 && (plat === 0 || enc === 1)) {
            const segs = b.readUInt16BE(o + 6) / 2;
            const fim = o + 14;
            const ini = fim + 2 * segs + 2;
            const delta = ini + 2 * segs;
            const desloc = delta + 2 * segs;
            for (let s = 0; s < segs; s++) {
                const c0 = b.readUInt16BE(ini + 2 * s);
                const c1 = b.readUInt16BE(fim + 2 * s);
                const d = b.readUInt16BE(delta + 2 * s);
                const r = b.readUInt16BE(desloc + 2 * s);
                for (let c = c0; c <= c1 && c !== 0xFFFF; c++) {
                    let g;
                    if (r === 0) {
                        g = (c + d) & 0xFFFF;
                    } else {
                        g = b.readUInt16BE(desloc + 2 * s + r + 2 * (c - c0));
                        g = g ? (g + d) & 0xFFFF : 0;
                    }
                    if (g && !mapa.has(c)) {
                        mapa.set(c, g);
                    }
                }
            }
        } else if (formato === 12) {
            const grupos = b.readUInt32BE(o + 12);
            for (let k = 0; k < grupos; k++) {
                const c0 = b.readUInt32BE(o + 16 + 12 * k);
                const c1 = b.readUInt32BE(o + 20 + 12 * k);
                const g0 = b.readUInt32BE(o + 24 + 12 * k);
                for (let c = c0; c <= c1; c++) {
                    if (!mapa.has(c)) {
                        mapa.set(c, g0 + c - c0);
                    }
                }
            }
        }
    }
    return {
        /* A largura do texto em unidades da tela; letra que a fonte não tem
         * conta como "M" (a central usaria outra fonte), e a lista volta junto. */
        mede(texto) {
            let w = 0;
            const faltam = [];
            for (const ch of texto) {
                let g = mapa.get(ch.codePointAt(0));
                if (!g) {
                    faltam.push(ch);
                    g = mapa.get(0x4D);
                }
                w += larguraDoGlifo(g);
            }
            return { largura: w * TAMANHO / em, faltam };
        }
    };
}

/* Quebra por palavra (espaço), como a central: as linhas e o que faltou na fonte. */
function quebra(fonte, texto, largura = LARGURA) {
    const linhas = [];
    const faltam = new Set();
    let atual = '';
    for (const palavra of texto.split(' ')) {
        const tentativa = atual ? `${atual} ${palavra}` : palavra;
        const m = fonte.mede(tentativa);
        m.faltam.forEach((c) => faltam.add(c));
        if (m.largura <= largura || !atual) {
            atual = tentativa;
        } else {
            linhas.push(atual);
            atual = palavra;
        }
    }
    if (atual) {
        linhas.push(atual);
    }
    return { linhas, faltam: [...faltam] };
}

module.exports = { carregaFonte, quebra, LARGURA, TAMANHO };

if (require.main === module) {
    if (!process.env.BMW_FONT) {
        console.error('BMW_FONT: o caminho do BMWTALG.ttf da central');
        process.exit(2);
    }
    const f = carregaFonte(process.env.BMW_FONT);
    process.argv.slice(2).forEach((t) => {
        const q = quebra(f, t);
        console.log(`${q.linhas.length} linhas${q.faltam.length ? ` (sem na fonte: ${q.faltam.join('')})` : ''}`);
        q.linhas.forEach((l) => console.log(`   |${l}|`));
    });
}
