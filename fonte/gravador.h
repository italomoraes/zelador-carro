// SPDX-License-Identifier: MIT
/* Gravador: as linhas da escuta em arquivos que giram, com limite de espaço.
 *
 * Grava em <pasta>/escuta-AAAAMMDD-HHMMSS-NNN.part (hora UTC de abertura; NNN
 * conta os abertos no mesmo segundo, para a ordem dos nomes ser a do tempo).
 * O .part vira .txt,
 * pronto para o envio, quando gira: ao passar de gira_bytes, quando tem algo
 * escrito há mais de gira_s segundos (linha() e passo() olham isso) e ao
 * fechar. Ao abrir, um .part que sobrou de uma execução anterior vira .txt
 * (ou some, se vazio). Ao abrir e a cada giro, os .txt mais antigos são
 * apagados até sobrar espaço para um atual cheio (gira_bytes) dentro de
 * limite_bytes; um arquivo pode passar de gira_bytes pela última linha.
 *
 * Com dono >= 0, as pastas criadas, a pasta e cada arquivo passam a ser desse
 * uid e gid (o envio, sem root, lê e apaga), com modos 0700 e 0600. Não é
 * seguro entre threads: quem chama segura um mutex. */
#ifndef ZELADOR_GRAVADOR_H
#define ZELADOR_GRAVADOR_H

#include <dirent.h>
#include <stdio.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>

class Gravador {
public:
    Gravador(const std::string &pasta, uint64_t limite_bytes, uint64_t gira_bytes, long gira_s, long dono,
             std::function<time_t()> agora = [] { return time(nullptr); })
        : pasta_(pasta), limite_(limite_bytes), gira_bytes_(gira_bytes), gira_s_(gira_s), dono_(dono),
          agora_(agora) {}
    ~Gravador() { fecha(); }
    Gravador(const Gravador &) = delete;
    Gravador &operator=(const Gravador &) = delete;

    /* A pasta pronta e o que sobrou fechado; false se ela não serve. */
    bool abre() {
        if (!cria_pasta(pasta_))
            return false;
        for (const std::string &n : lista(".part")) {
            const std::string de = pasta_ + "/" + n;
            struct stat st;
            if (stat(de.c_str(), &st) == 0 && st.st_size == 0)
                unlink(de.c_str());
            else
                rename(de.c_str(), (de.substr(0, de.size() - 5) + ".txt").c_str());
        }
        limpa();
        return true;
    }

    /* Uma linha (sem o \n); gira antes, se for a hora. False se não gravou. */
    bool linha(const std::string &s) {
        passo();
        if (!f_ && !novo())
            return false;
        if (fwrite(s.data(), 1, s.size(), f_) != s.size() || fputc('\n', f_) == EOF || fflush(f_) != 0) {
            fecha();
            return false;
        }
        escrito_ += s.size() + 1;
        return true;
    }

    /* Gira o atual se ele já tem idade (chamado de tempos em tempos). */
    void passo() {
        if (f_ && (escrito_ >= gira_bytes_ || (escrito_ > 0 && agora_() - aberto_ >= gira_s_)))
            fecha();
    }

    /* O atual vira .txt se tem algo; some se está vazio. */
    void fecha() {
        if (!f_)
            return;
        fclose(f_);
        f_ = nullptr;
        if (escrito_ == 0)
            unlink(atual_.c_str());
        else
            rename(atual_.c_str(), (atual_.substr(0, atual_.size() - 5) + ".txt").c_str());
        atual_.clear();
        escrito_ = 0;
        limpa();
    }

    const std::string &atual() const { return atual_; }

private:
    bool cria_pasta(const std::string &p) {
        struct stat st;
        if (stat(p.c_str(), &st) != 0) {
            const size_t barra = p.find_last_of('/');
            if (barra != std::string::npos && barra > 0 && !cria_pasta(p.substr(0, barra)))
                return false;
            if (mkdir(p.c_str(), 0700) != 0 && stat(p.c_str(), &st) != 0)
                return false;
            dono(p);
        }
        if (p == pasta_) {
            dono(p);
            chmod(p.c_str(), 0700);
        }
        return stat(p.c_str(), &st) == 0 && S_ISDIR(st.st_mode);
    }

    void dono(const std::string &p) {
        if (dono_ >= 0 && chown(p.c_str(), (uid_t)dono_, (gid_t)dono_) != 0) {
            /* sem o dono, o envio não lê: a escuta segue e o envio avisa */
        }
    }

    bool novo() {
        const time_t t = agora_();
        struct tm tm;
        gmtime_r(&t, &tm);
        char base[64];
        strftime(base, sizeof base, "escuta-%Y%m%d-%H%M%S", &tm);
        std::string nome;
        for (int i = 0; i < 1000; i++) {
            char n[8];
            snprintf(n, sizeof n, "-%03d", i);
            nome = pasta_ + "/" + base + n;
            struct stat st;
            if (stat((nome + ".part").c_str(), &st) != 0 && stat((nome + ".txt").c_str(), &st) != 0)
                break;
        }
        atual_ = nome + ".part";
        f_ = fopen(atual_.c_str(), "wx");
        if (!f_) {
            atual_.clear();
            return false;
        }
        fchmod(fileno(f_), 0600);
        if (dono_ >= 0 && fchown(fileno(f_), (uid_t)dono_, (gid_t)dono_) != 0) {
            /* idem */
        }
        aberto_ = t;
        escrito_ = 0;
        return true;
    }

    /* Os nomes da pasta "escuta-*<fim>", em ordem (a do tempo). */
    std::vector<std::string> lista(const char *fim) const {
        std::vector<std::string> nomes;
        DIR *d = opendir(pasta_.c_str());
        if (!d)
            return nomes;
        const std::string f(fim);
        while (struct dirent *e = readdir(d)) {
            const std::string n(e->d_name);
            if (n.compare(0, 7, "escuta-") == 0 && n.size() > f.size() + 7 &&
                n.compare(n.size() - f.size(), f.size(), f) == 0)
                nomes.push_back(n);
        }
        closedir(d);
        std::sort(nomes.begin(), nomes.end());
        return nomes;
    }

    void limpa() {
        std::vector<std::string> txt = lista(".txt");
        std::vector<uint64_t> tam;
        uint64_t total = std::max(escrito_, gira_bytes_);
        for (const std::string &n : txt) {
            struct stat st;
            tam.push_back(stat((pasta_ + "/" + n).c_str(), &st) == 0 ? (uint64_t)st.st_size : 0);
            total += tam.back();
        }
        for (size_t i = 0; i < txt.size() && total > limite_; i++) {
            if (unlink((pasta_ + "/" + txt[i]).c_str()) == 0)
                total -= tam[i];
        }
    }

    std::string pasta_;
    uint64_t limite_, gira_bytes_;
    long gira_s_, dono_;
    std::function<time_t()> agora_;
    FILE *f_ = nullptr;
    std::string atual_;
    time_t aberto_ = 0;
    uint64_t escrito_ = 0;
};

#endif
