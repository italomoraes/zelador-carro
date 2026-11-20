// SPDX-License-Identifier: MIT
/* Testes do Gravador (gravador.h), com um relógio de mentira. Roda no Mac e
 * no Linux:  c++ -std=c++14 -Wall -Wextra -Werror -o teste_gravador teste_gravador.cpp && ./teste_gravador */
#include "gravador.h"

#include <stdlib.h>
#include <string.h>

#include <fstream>
#include <sstream>

static int falhas = 0;

static void ok(const char *o_que, bool deu) {
    printf("%s %s\n", deu ? "ok  " : "FALHA", o_que);
    if (!deu)
        falhas++;
}

static std::vector<std::string> nomes(const std::string &pasta) {
    std::vector<std::string> v;
    if (DIR *d = opendir(pasta.c_str())) {
        while (struct dirent *e = readdir(d))
            if (e->d_name[0] != '.')
                v.push_back(e->d_name);
        closedir(d);
    }
    std::sort(v.begin(), v.end());
    return v;
}

static std::string le(const std::string &arquivo) {
    std::ifstream f(arquivo);
    std::stringstream s;
    s << f.rdbuf();
    return s.str();
}

static bool termina(const std::string &s, const char *fim) {
    const size_t n = strlen(fim);
    return s.size() >= n && s.compare(s.size() - n, n, fim) == 0;
}

int main() {
    char modelo[] = "/tmp/zelador-teste-XXXXXX";
    const std::string raiz = mkdtemp(modelo);
    const std::string pasta = raiz + "/dados/escuta";
    time_t relogio = 1795000000; /* 2026-11-18 */
    auto agora = [&relogio] { return relogio; };

    {
        Gravador g(pasta, 1000000, 1000, 600, -1, agora);
        ok("abre cria as pastas que faltam", g.abre() && nomes(pasta).empty());
        struct stat st;
        ok("a pasta fica 0700", stat(pasta.c_str(), &st) == 0 && (st.st_mode & 0777) == 0700);
        ok("a primeira linha abre um .part", g.linha("um") && termina(g.atual(), ".part") &&
                                                 nomes(pasta).size() == 1 && le(g.atual()) == "um\n");
        ok("o arquivo fica 0600", stat(g.atual().c_str(), &st) == 0 && (st.st_mode & 0777) == 0600);
        relogio += 300;
        g.passo();
        ok("antes da idade, nada gira", nomes(pasta).size() == 1 && termina(nomes(pasta)[0], ".part"));
        relogio += 301;
        g.passo();
        const std::vector<std::string> n = nomes(pasta);
        ok("com idade, o .part vira .txt", n.size() == 1 && termina(n[0], ".txt") && g.atual().empty() &&
                                               le(pasta + "/" + n[0]) == "um\n");
        ok("o nome é a hora UTC de abertura", n.size() == 1 && n[0] == "escuta-20261118-110640-000.txt");
        g.passo();
        ok("sem nada escrito, passo não cria arquivo", nomes(pasta).size() == 1);
        /* por tamanho: 1000 bytes */
        const std::string grande(600, 'x');
        g.linha(grande);
        g.linha(grande);
        g.linha("depois");
        ok("passou do tamanho: o próximo é outro arquivo", nomes(pasta).size() == 3 &&
                                                                le(g.atual()) == "depois\n");
        ok("dois no mesmo segundo: o contador mantém a ordem", nomes(pasta)[1] == "escuta-20261118-111641-000.txt" &&
                                                              nomes(pasta)[2] == "escuta-20261118-111641-001.part");
    }
    {
        const std::vector<std::string> n = nomes(pasta);
        ok("ao sair, o atual vira .txt", n.size() == 3 && termina(n[2], "-001.txt"));
    }
    {
        /* um .part que sobrou (queda de energia) e um vazio */
        std::ofstream(pasta + "/escuta-20261118-080000-000.part") << "sobrou\n";
        std::ofstream(pasta + "/escuta-20261118-080001-000.part");
        Gravador g(pasta, 1000000, 1000, 600, -1, agora);
        g.abre();
        const std::vector<std::string> n = nomes(pasta);
        ok("ao abrir, o .part que sobrou vira .txt e o vazio some",
           n.size() == 4 && n[0] == "escuta-20261118-080000-000.txt" && le(pasta + "/" + n[0]) == "sobrou\n");
        g.linha("x");
        g.fecha();
        ok("fecha com algo escrito: .txt", nomes(pasta).size() == 5);
        g.fecha();
        ok("fecha de novo: nada muda", nomes(pasta).size() == 5);
    }
    {
        /* limite: 2500 bytes; cada arquivo ~1000 */
        const std::string pasta2 = raiz + "/limite";
        Gravador g(pasta2, 2500, 900, 600, -1, agora);
        g.abre();
        const std::string linha(499, 'y');
        for (int i = 0; i < 12; i++) {
            relogio += 1;
            g.linha(linha);
        }
        std::vector<std::string> n = nomes(pasta2);
        uint64_t total = 0;
        for (const std::string &a : n) {
            struct stat st;
            stat((pasta2 + "/" + a).c_str(), &st);
            total += st.st_size;
        }
        ok("o total fica no limite", total <= 2500);
        ok("ficam os mais novos", !n.empty() && termina(n.back(), ".part") && n.size() <= 3);
    }
    {
        Gravador g(raiz + "/vazio", 1000, 1000, 600, -1, agora);
        g.abre();
        g.fecha();
        ok("abrir e fechar sem escrever não deixa arquivo", nomes(raiz + "/vazio").empty());
    }
    {
        const std::string arquivo = raiz + "/um-arquivo";
        std::ofstream(arquivo) << "x";
        Gravador g(arquivo, 1000, 1000, 600, -1, agora);
        ok("uma pasta que é arquivo não serve", !g.abre());
    }
    const int r = system(("rm -rf '" + raiz + "'").c_str());
    (void)r;
    printf("%s\n", falhas ? "FALHOU" : "tudo ok");
    return falhas ? 1 : 0;
}
