// SPDX-License-Identifier: MIT
/* zelador-escuta: grava, só lendo, a orientação da navegação BMW (SOME/IP).
 *
 *   zelador-escuta --pasta P [--limite-mb N] [--gira-kb N] [--gira-min N] [--dono UID] [servico ...]
 *
 * Serviços (hexa) padrão, todos na instância 0x0080: 0xFB1A (Guidance v7),
 * 0xFB1B (GuidanceEventList v5), 0xFB1C (GuidanceRenderedContent v3) e 0xFB35
 * (ProjectedModeGuiding v1). De cada um pede os eventos 0x80NN no grupo 0x00NN,
 * NN de 0x01 a 0x30 (o padrão do código do proxy da BMW), e assina os grupos;
 * um campo manda o valor atual na assinatura.
 *
 * Só pede e assina depois que o serviço está disponível há kEspera, para a
 * navegação registrar os eventos dela antes, e pede com o tipo desconhecido
 * (ET_UNKNOWN): quem oferece é que diz se é campo ou evento. Pedir antes, como
 * campo, podia deixar no roteador do SOME/IP um tipo que não é o da navegação.
 *
 * Cada mensagem vira uma linha (gravador.h): hora, tipo, serviço, evento,
 * tamanho, os textos legíveis e o conteúdo em hexa (até 16 KiB). Uma mensagem
 * igual à última do mesmo evento não é gravada de novo; quantas vieram assim
 * sai numa linha "repetidas" a cada minuto. A disponibilidade dos serviços e
 * o resultado das assinaturas também viram linhas.
 *
 * Não chama nenhum método da navegação e não oferece nada. Roda como root (a
 * política do SOME/IP da central só libera esses serviços para o root), com a
 * configuração da central (VSOMEIP_CONFIGURATION=/etc/vsomeip, que diz que o
 * roteamento é do vsomeipd), e não usa a rede. Sai com SIGTERM ou SIGINT,
 * desassinando e fechando o arquivo atual. */
#include <vsomeip/vsomeip.hpp>

#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include <atomic>
#include <chrono>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <vector>

#include "gravador.h"

namespace {

const char kVersao[] = "0.1.1";
const vsomeip::instance_t kInstancia = 0x0080;
const int kGrupos = 0x30;
const size_t kMaxHexa = 16384;
const std::chrono::seconds kEspera(5);

struct Servico {
    vsomeip::service_t id;
    vsomeip::major_version_t major;
};

std::mutex g_mutex;
std::unique_ptr<Gravador> g_gravador;
std::atomic<bool> g_parar(false);
/* a última mensagem de cada serviço/evento, e as repetidas desde o último aviso */
std::map<uint32_t, std::string> g_ultima;
std::map<uint32_t, unsigned> g_repetidas;
/* quando cada serviço ficou disponível pela primeira vez, e os já assinados */
std::map<vsomeip::service_t, std::chrono::steady_clock::time_point> g_disponivel_em;
std::set<vsomeip::service_t> g_assinados;

std::string hora() {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    char b[32];
    snprintf(b, sizeof b, "%ld.%03ld", (long)ts.tv_sec, (long)(ts.tv_nsec / 1000000));
    return b;
}

/* Uma linha no arquivo; quem chama segura g_mutex. */
void grava(const std::string &s) {
    if (g_gravador && !g_gravador->linha(hora() + " " + s))
        fprintf(stderr, "zelador-escuta: não gravou uma linha\n");
}

void grava_trancado(const std::string &s) {
    std::lock_guard<std::mutex> l(g_mutex);
    grava(s);
}

/* Trechos legíveis (ASCII e bytes de UTF-8) de 3 ou mais caracteres. */
std::string textos(const uint8_t *p, size_t n) {
    std::string out, cur;
    for (size_t i = 0; i <= n; i++) {
        const uint8_t c = i < n ? p[i] : 0;
        if ((c >= 0x20 && c < 0x7f && c != '|') || c >= 0x80) {
            cur.push_back(char(c));
        } else {
            if (cur.size() >= 3) {
                if (!out.empty())
                    out += " | ";
                out += cur;
            }
            cur.clear();
        }
    }
    return out;
}

std::string hexa(const uint8_t *p, size_t n) {
    static const char d[] = "0123456789abcdef";
    const size_t m = n < kMaxHexa ? n : kMaxHexa;
    std::string out;
    out.reserve(m * 2 + 3);
    for (size_t i = 0; i < m; i++) {
        out.push_back(d[p[i] >> 4]);
        out.push_back(d[p[i] & 15]);
    }
    if (m < n)
        out += "...";
    return out;
}

const char *tipo(vsomeip::message_type_e t) {
    switch (t) {
    case vsomeip::message_type_e::MT_NOTIFICATION: return "NOTIF";
    case vsomeip::message_type_e::MT_RESPONSE: return "RESP";
    case vsomeip::message_type_e::MT_ERROR: return "ERRO";
    case vsomeip::message_type_e::MT_REQUEST: return "REQ";
    case vsomeip::message_type_e::MT_REQUEST_NO_RETURN: return "REQNR";
    default: return "?";
    }
}

std::string hex4(unsigned v) {
    char b[8];
    snprintf(b, sizeof b, "%04x", v & 0xffff);
    return b;
}

void na_mensagem(const std::shared_ptr<vsomeip::message> &m) {
    const std::shared_ptr<vsomeip::payload> pl = m->get_payload();
    const uint8_t *p = pl ? pl->get_data() : nullptr;
    const size_t n = pl ? pl->get_length() : 0;
    const uint32_t chave = (uint32_t)m->get_service() << 16 | m->get_method();
    const std::string dados(p ? reinterpret_cast<const char *>(p) : "", n);
    std::lock_guard<std::mutex> l(g_mutex);
    auto u = g_ultima.find(chave);
    if (u != g_ultima.end() && u->second == dados) {
        g_repetidas[chave]++;
        return;
    }
    g_ultima[chave] = dados;
    grava(std::string(tipo(m->get_message_type())) + " " + hex4(m->get_service()) + "." + hex4(m->get_instance()) +
          " ev " + hex4(m->get_method()) + " len " + std::to_string(n) + " | textos: " + textos(p, n) +
          " | hexa: " + hexa(p, n));
}

/* As repetidas desde o último aviso, numa linha; quem chama segura g_mutex. */
void avisa_repetidas() {
    std::string s;
    for (const auto &r : g_repetidas)
        s += " " + hex4(r.first >> 16) + "/" + hex4(r.first) + " x" + std::to_string(r.second);
    if (!s.empty())
        grava("repetidas:" + s);
    g_repetidas.clear();
}

/* Pede os eventos e assina os grupos de um serviço; chamado sem g_mutex,
 * porque o vsomeip pode chamar os tratadores daqui mesmo. */
void assina(const std::shared_ptr<vsomeip::application> &app, const Servico &sv) {
    grava_trancado("assinando " + hex4(sv.id) + ": eventos 8001 a 80" + hex4(kGrupos).substr(2) +
                   ", disponível há " + std::to_string(kEspera.count()) + " s");
    for (int nn = 1; nn <= kGrupos; nn++) {
        const vsomeip::eventgroup_t g = vsomeip::eventgroup_t(nn);
        app->request_event(sv.id, kInstancia, vsomeip::event_t(0x8000 | nn), std::set<vsomeip::eventgroup_t>{g},
                           vsomeip::event_type_e::ET_UNKNOWN, vsomeip::reliability_type_e::RT_UNKNOWN);
    }
    for (int nn = 1; nn <= kGrupos; nn++)
        app->subscribe(sv.id, kInstancia, vsomeip::eventgroup_t(nn), sv.major);
}

void no_sinal(int) { g_parar = true; }

long numero(const char *s, long padrao) {
    if (!s)
        return padrao;
    char *fim = nullptr;
    const long v = strtol(s, &fim, 10);
    return fim && *fim == '\0' ? v : padrao;
}

}  // namespace

int main(int argc, char **argv) {
    std::string pasta;
    long limite_mb = 100, gira_kb = 1024, gira_min = 10, dono = -1;
    std::vector<Servico> servicos;
    for (int i = 1; i < argc; i++) {
        const std::string a = argv[i];
        const char *v = i + 1 < argc ? argv[i + 1] : nullptr;
        if (a == "--pasta" && v) {
            pasta = v;
            i++;
        } else if (a == "--limite-mb" && v) {
            limite_mb = numero(v, -1);
            i++;
        } else if (a == "--gira-kb" && v) {
            gira_kb = numero(v, -1);
            i++;
        } else if (a == "--gira-min" && v) {
            gira_min = numero(v, -1);
            i++;
        } else if (a == "--dono" && v) {
            dono = numero(v, -2);
            i++;
        } else {
            const vsomeip::service_t s = vsomeip::service_t(strtoul(a.c_str(), nullptr, 16));
            const vsomeip::major_version_t mj = s == 0xFB1A ? 7 : s == 0xFB1B ? 5 : s == 0xFB1C ? 3
                                                : s == 0xFB35 ? 1 : vsomeip::ANY_MAJOR;
            if (!s) {
                fprintf(stderr, "zelador-escuta: argumento desconhecido: %s\n", a.c_str());
                return 2;
            }
            servicos.push_back({s, mj});
        }
    }
    if (pasta.empty() || limite_mb < 1 || gira_kb < 1 || gira_min < 1 || dono < -1 ||
        (uint64_t)limite_mb * 1024 < (uint64_t)gira_kb * 2) {
        fprintf(stderr, "uso: zelador-escuta --pasta P [--limite-mb N] [--gira-kb N] [--gira-min N] [--dono UID] "
                        "[servico ...]  (o limite tem de caber dois arquivos)\n");
        return 2;
    }
    if (servicos.empty())
        servicos = {{0xFB1A, 7}, {0xFB1B, 5}, {0xFB1C, 3}, {0xFB35, 1}};

    g_gravador.reset(new Gravador(pasta, (uint64_t)limite_mb << 20, (uint64_t)gira_kb << 10, gira_min * 60, dono));
    if (!g_gravador->abre()) {
        fprintf(stderr, "zelador-escuta: a pasta %s não serve\n", pasta.c_str());
        return 1;
    }
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = no_sinal;
    sigaction(SIGTERM, &sa, nullptr);
    sigaction(SIGINT, &sa, nullptr);

    std::shared_ptr<vsomeip::application> app = vsomeip::runtime::get()->create_application("zelador-escuta");
    if (!app || !app->init()) {
        fprintf(stderr, "zelador-escuta: o vsomeip não iniciou\n");
        return 1;
    }
    std::string lista;
    for (const Servico &sv : servicos)
        lista += " " + hex4(sv.id);
    fprintf(stderr, "zelador-escuta %s: gravando em %s, serviços%s\n", kVersao, pasta.c_str(), lista.c_str());
    grava_trancado(std::string("inicio: zelador-escuta ") + kVersao + ", serviços" + lista);

    for (const Servico &sv : servicos) {
        app->register_availability_handler(
            sv.id, kInstancia,
            [](vsomeip::service_t s, vsomeip::instance_t i, bool a) {
                std::lock_guard<std::mutex> l(g_mutex);
                grava("servico " + hex4(s) + "." + hex4(i) + (a ? " DISPONIVEL" : " indisponivel"));
                if (a && !g_disponivel_em.count(s))
                    g_disponivel_em[s] = std::chrono::steady_clock::now();
            },
            vsomeip::ANY_MAJOR, vsomeip::ANY_MINOR);
        app->register_message_handler(sv.id, kInstancia, vsomeip::ANY_METHOD, na_mensagem);
        for (int nn = 1; nn <= kGrupos; nn++) {
            app->register_subscription_status_handler(
                sv.id, kInstancia, vsomeip::eventgroup_t(nn), vsomeip::event_t(0x8000 | nn),
                [](const vsomeip::service_t s, const vsomeip::instance_t, const vsomeip::eventgroup_t gg,
                   const vsomeip::event_t, const uint16_t codigo) {
                    grava_trancado("assinatura " + hex4(s) + " grupo " + hex4(gg) + ": " +
                                   (codigo == 0 ? "aceita" : "recusada (" + std::to_string(codigo) + ")"));
                },
                true);
        }
        app->request_service(sv.id, kInstancia, sv.major, vsomeip::ANY_MINOR);
    }

    std::thread laco([app] { app->start(); });
    auto ultimo_aviso = std::chrono::steady_clock::now();
    while (!g_parar) {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        std::vector<Servico> assinar;
        {
            std::lock_guard<std::mutex> l(g_mutex);
            g_gravador->passo();
            const auto agora = std::chrono::steady_clock::now();
            if (agora - ultimo_aviso >= std::chrono::minutes(1)) {
                ultimo_aviso = agora;
                avisa_repetidas();
            }
            for (const Servico &sv : servicos) {
                auto d = g_disponivel_em.find(sv.id);
                if (d != g_disponivel_em.end() && !g_assinados.count(sv.id) && agora - d->second >= kEspera) {
                    g_assinados.insert(sv.id);
                    assinar.push_back(sv);
                }
            }
        }
        for (const Servico &sv : assinar)
            assina(app, sv);
    }

    std::set<vsomeip::service_t> assinados;
    {
        std::lock_guard<std::mutex> l(g_mutex);
        assinados = g_assinados;
    }
    for (const Servico &sv : servicos) {
        if (assinados.count(sv.id)) {
            for (int nn = 1; nn <= kGrupos; nn++) {
                app->unsubscribe(sv.id, kInstancia, vsomeip::eventgroup_t(nn));
                app->release_event(sv.id, kInstancia, vsomeip::event_t(0x8000 | nn));
            }
        }
        app->release_service(sv.id, kInstancia);
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(300));
    app->clear_all_handler();
    app->stop();
    laco.join();
    {
        std::lock_guard<std::mutex> l(g_mutex);
        avisa_repetidas();
        grava("fim");
        g_gravador->fecha();
    }
    fprintf(stderr, "zelador-escuta: saiu\n");
    return 0;
}
