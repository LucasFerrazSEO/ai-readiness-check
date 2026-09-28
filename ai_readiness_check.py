#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai-readiness-check — índice de prontidão técnica de um site para leitura por
buscadores e assistentes com IA (Google AI Mode/AI Overviews, Gemini,
Perplexity, ChatGPT, Claude), calculado a partir de sinais públicos do
próprio domínio.

O QUE FAZ
    Para cada site informado, baixa /llms.txt, /robots.txt e a home, e dá uma
    nota de 0 a 100, ponderada, com seis checagens:

        llms.txt graduado por qualidade .......... peso 25
        robots.txt e robôs de IA ................. peso 30
        schema de entidade na home ............... peso 25
        meta description da home ................. peso 5
        sinal declarado para agentes de IA ....... peso 15
        paridade FAQ visível x FAQPage ........... peso 3 (só se houver FAQPage)

    PASS vale o peso inteiro, PARCIAL vale metade, FAIL vale zero. A nota é
    a soma dividida pelo total de pesos aplicáveis.

    Depois roda um bloco avançado, informativo, que NÃO entra na nota:
    sitemap no robots.txt, Content Signals, sameAs, schema além da entidade,
    llms-full.txt, MCP Server Card, catálogo para agentes (ai-catalog.json),
    Markdown por negociação de conteúdo (Accept: text/markdown), rota /md/ e
    sondas de borda com User-Agent de robô de IA (status HTTP devolvido).

MÉTODO
    Porte em Python do motor da ferramenta online de prontidão para IA do
    lucasferrazseo.com, com as mesmas checagens, pesos e regra de pontuação,
    sem nada específico de WordPress (sem endpoint REST, sem cache, sem
    prompts). A lista de robôs de IA vem de ai_bots.json, no mesmo formato
    do repositório ai-bots-list. Rede com User-Agent identificável, timeout,
    intervalo entre requisições (--delay) e uma nova tentativa depois de 429.

USO
    python ai_readiness_check.py https://example.com/
    python ai_readiness_check.py https://example.com/ https://example.org/ --delay 2
    python ai_readiness_check.py https://example.com/ --no-probes
    python ai_readiness_check.py https://example.com/ --json
    python ai_readiness_check.py https://example.com/ --strict   # código de saída 1 se houver FAIL na nota

LIMITAÇÕES
    Mede sinais técnicos públicos, não a resposta de nenhum modelo: a nota é
    um índice próprio de prontidão, não previsão de citação. As checagens
    de HTML usam expressões regulares sobre o primeiro 1 MB da home e
    não executam JavaScript. As sondas de borda enviam o User-Agent público
    de cada robô a partir do seu IP: uma CDN que verifica robôs por IP pode
    bloquear a sonda sem bloquear o robô verdadeiro.

Autor: Lucas Ferraz (lucasferraz.com).
Licença: MIT. Dados de ai_bots.json: CC BY 4.0.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import sys
import time
from urllib.parse import urlparse

try:
    import requests
except ImportError:  # pragma: no cover
    print("Falta a biblioteca requests. Rode: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)

UA_PADRAO = "ai-readiness-check/1.0 (+https://github.com/LucasFerrazSEO/ai-readiness-check)"
TIMEOUT = 10
ROTULO = {"pass": "PASS", "partial": "PARCIAL", "fail": "FAIL", "skip": "SKIP"}

BLOCO_JSONLD = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
TIPOS_ORG = {"organization", "localbusiness", "corporation", "professionalservice",
             "legalservice", "store"}
TIPOS_EXTRA = ("faqpage", "article", "blogposting", "website", "breadcrumblist",
               "product", "service")
ROBOS_BORDA = (
    ("gptbot", "Resposta ao GPTBot (OpenAI)",
     "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)"),
    ("claudebot", "Resposta ao ClaudeBot (Anthropic)",
     "Mozilla/5.0 (compatible; ClaudeBot/1.0; +https://www.anthropic.com/claude-bot)"),
    ("perplexitybot", "Resposta ao PerplexityBot (Perplexity)",
     "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"),
)


# --------------------------------------------------------------------- rede
class Cliente:
    """Requisições com UA identificável, timeout, intervalo e 1 retry em 429."""

    def __init__(self, delay: float) -> None:
        self.delay = max(0.0, delay)
        self.sessao = requests.Session()
        self._ultima = 0.0
        self.log_429: list[str] = []

    def _espera(self) -> None:
        falta = self.delay - (time.monotonic() - self._ultima)
        if falta > 0:
            time.sleep(falta)

    def get(self, url: str, ua: str = UA_PADRAO, accept: str = "*/*",
            max_bytes: int = 65536, max_redirects: int = 3) -> dict:
        for tentativa in (1, 2):
            self._espera()
            self.sessao.max_redirects = max_redirects
            try:
                resp = self.sessao.get(url, headers={"User-Agent": ua, "Accept": accept},
                                       timeout=TIMEOUT, stream=True, allow_redirects=True)
                corpo = b""
                for pedaco in resp.iter_content(8192):
                    corpo += pedaco
                    if len(corpo) >= max_bytes:
                        break
                resp.close()
            except requests.RequestException:
                self._ultima = time.monotonic()
                return {"ok": False, "code": 0, "ctype": "", "body": ""}
            self._ultima = time.monotonic()
            if resp.status_code == 429 and tentativa == 1:
                espera = resp.headers.get("Retry-After", "")
                espera_s = int(espera) if espera.isdigit() else 5
                time.sleep(min(espera_s, 30))
                continue
            if resp.status_code == 429:
                self.log_429.append(url)
            ctype = resp.headers.get("Content-Type", "").lower()
            enc = (resp.encoding or "utf-8") if "charset" in ctype else "utf-8"
            return {
                "ok": True,
                "code": resp.status_code,
                "ctype": ctype,
                "body": corpo[:max_bytes].decode(enc, errors="replace"),
            }
        return {"ok": False, "code": 0, "ctype": "", "body": ""}  # não alcançado


# ------------------------------------------------------------ utilidades
def carrega_bots(caminho: str) -> list[str]:
    with open(caminho, encoding="utf-8") as fh:
        dados = json.load(fh)
    return [b["user_agent"].lower() for b in dados.get("bots", []) if b.get("user_agent")]


def nos_jsonld(html: str) -> list[dict]:
    nos: list[dict] = []
    for bloco in BLOCO_JSONLD.findall(html or ""):
        try:
            dado = json.loads(bloco.strip())
        except json.JSONDecodeError:
            continue
        candidatos = dado if isinstance(dado, list) else [dado]
        for d in candidatos:
            if not isinstance(d, dict):
                continue
            grafo = d.get("@graph") if isinstance(d.get("@graph"), list) else [d]
            nos.extend(n for n in grafo if isinstance(n, dict))
    return nos


def tipos_do_no(no: dict) -> list[str]:
    t = no.get("@type")
    if not t:
        return []
    return [str(x).lower() for x in (t if isinstance(t, list) else [t])]


def texto_visivel(html: str) -> str:
    sem_script = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", html or "")
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"(?s)<[^>]+>", " ", sem_script))).strip()


def res(status: str, detalhe: str) -> dict:
    return {"status": status, "detalhe": detalhe}


# ---------------------------------------------------------- checagens da nota
def checa_llms(r: dict, home_html: str) -> dict:
    if not (r["ok"] and 200 <= r["code"] < 300):
        return res("fail", f"/llms.txt não respondeu com sucesso (HTTP {r['code'] or 'sem resposta'}).")
    txt = r["body"].strip()
    tamanho = len(txt.encode("utf-8"))
    if tamanho < 50:
        return res("fail", f"/llms.txt existe, mas tem {tamanho} bytes (menos de 50).")
    tem_links = bool(re.search(r"\]\(https?://", txt)) or txt.count("http") >= 2
    marca = ""
    m = re.search(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)["\']', home_html, re.I)
    if m:
        marca = m.group(1).strip()
    else:
        mt = re.search(r"(?is)<title[^>]*>(.*?)</title>", home_html)
        if mt:
            titulo = html_lib.unescape(re.sub(r"<[^>]+>", "", mt.group(1)))
            marca = re.split(r"[|\-–—]", titulo)[0].strip()
    cita_marca = bool(marca) and marca.lower() in txt.lower()
    parece_auto = tamanho < 300 and not tem_links
    rotulo_marca = f'"{marca}"' if marca else "(marca não identificada na home)"
    if tem_links and cita_marca:
        return res("pass", f"/llms.txt com {tamanho} bytes, links absolutos e menção à marca {rotulo_marca}.")
    if parece_auto:
        return res("partial", f"/llms.txt curto ({tamanho} bytes) e sem links: padrão de arquivo genérico.")
    falta = "links absolutos para as páginas principais" if not tem_links else f"menção à marca {rotulo_marca}"
    return res("partial", f"/llms.txt com {tamanho} bytes, mas sem {falta}.")


def checa_robots(r: dict, bots: list[str]) -> dict:
    if not (r["ok"] and 200 <= r["code"] < 400):
        return res("partial", f"/robots.txt indisponível (HTTP {r['code'] or 'sem resposta'}); "
                              "o acesso dos robôs de IA não está declarado.")
    grupos: list[dict] = []
    atual = None
    for linha in r["body"].lower().splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        m = re.match(r"^user-agent\s*:\s*(.+)$", linha)
        if m:
            if atual is None or atual["has_rule"]:
                atual = {"agents": [], "disallow_root": False, "has_rule": False}
                grupos.append(atual)
            atual["agents"].append(m.group(1).strip())
            continue
        m = re.match(r"^disallow\s*:\s*(.*)$", linha)
        if atual is not None and m:
            atual["has_rule"] = True
            if m.group(1).strip() == "/":
                atual["disallow_root"] = True
        elif atual is not None and re.match(r"^allow\s*:", linha):
            atual["has_rule"] = True

    liberados, bloqueados, estrela_bloqueada = set(), set(), False
    for g in grupos:
        for ua in g["agents"]:
            if ua == "*" and g["disallow_root"]:
                estrela_bloqueada = True
            if ua in bots:
                (bloqueados if g["disallow_root"] else liberados).add(ua)

    if bloqueados:
        return res("fail", "Disallow: / para robô(s) de IA por nome: " + ", ".join(sorted(bloqueados)) + ".")
    if estrela_bloqueada and not liberados:
        return res("fail", "Disallow: / para User-agent: *, sem exceção nomeada para robôs de IA.")
    if liberados:
        return res("pass", f"{len(liberados)} robô(s) de IA citado(s) por nome sem Disallow: /.")
    return res("partial", "Nenhum robô de IA citado por nome; o acesso depende da regra genérica.")


def checa_entidade(html: str) -> dict:
    if not BLOCO_JSONLD.search(html):
        return res("fail", "A home não tem bloco JSON-LD.")
    nos = nos_jsonld(html)
    org = next((n for n in nos if set(tipos_do_no(n)) & TIPOS_ORG), None)
    if org is None:
        if any(tipos_do_no(n) for n in nos):
            return res("partial", "Há JSON-LD, mas sem nó Organization/LocalBusiness (ou subtipo listado).")
        return res("fail", "Nenhum nó de entidade com @type válido no JSON-LD da home.")
    faltando = []
    if not org.get("name"):
        faltando.append("name")
    if not org.get("url"):
        faltando.append("url")
    if not (org.get("logo") or org.get("image")):
        faltando.append("logo/image")
    if not org.get("sameAs"):
        faltando.append("sameAs")
    if not (org.get("address") or org.get("telephone")):
        faltando.append("address/telephone")
    completos = 5 - len(faltando)
    if completos == 5:
        return res("pass", "Nó de entidade com name, url, logo, sameAs e address/telephone.")
    if completos >= 3:
        return res("partial", f"Nó de entidade com {completos} de 5 campos. Falta: " + ", ".join(faltando) + ".")
    return res("fail", f"Nó de entidade com {completos} de 5 campos. Falta: " + ", ".join(faltando) + ".")


def checa_descricao(html: str) -> dict:
    ok = bool(re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'][^"\']{20,}["\']', html, re.I)
              or re.search(r'<meta[^>]+content=["\'][^"\']{20,}["\'][^>]+name=["\']description["\']', html, re.I))
    return res("pass", "Meta description com 20 caracteres ou mais.") if ok else \
        res("fail", "Sem meta description (ou com menos de 20 caracteres).")


def checa_declaracao(html: str) -> dict:
    sinais = []
    if re.search(r'<link[^>]+rel=["\']alternate["\'][^>]+type=["\']text/plain["\']', html, re.I):
        sinais.append('link rel="alternate" type="text/plain"')
    if re.search(r'<meta[^>]+name=["\']ai-(content-declaration|summary)["\']', html, re.I):
        sinais.append("meta ai-content-declaration/ai-summary")
    if re.search(r'<link[^>]+rel=["\']mcp["\']', html, re.I):
        sinais.append('link rel="mcp"')
    if sinais:
        return res("pass", "Sinal declarado na home: " + "; ".join(sinais) + ".")
    return res("partial", 'Nenhum link rel="alternate" text/plain, meta ai-* ou link rel="mcp" na home.')


def checa_faq(html: str) -> dict | None:
    perguntas = []
    for no in nos_jsonld(html):
        if "faqpage" in tipos_do_no(no):
            me = no.get("mainEntity")
            for q in (me if isinstance(me, list) else [me] if isinstance(me, dict) else []):
                if isinstance(q, dict) and q.get("name"):
                    perguntas.append(re.sub(r"\s+", " ", str(q["name"])).strip())
    if not perguntas:
        return None
    visivel = texto_visivel(html).lower()
    ausentes = [q for q in perguntas if q.lower() not in visivel]
    achadas = len(perguntas) - len(ausentes)
    if achadas == 0:
        return res("fail", f"{len(perguntas)} pergunta(s) no FAQPage e nenhuma no texto visível.")
    if ausentes:
        ex = '"; "'.join(ausentes[:2])
        return res("partial", f"{achadas} de {len(perguntas)} pergunta(s) do FAQPage no texto visível. "
                              f'Ausentes (ex.): "{ex}".')
    return res("pass", f"As {len(perguntas)} pergunta(s) do FAQPage aparecem no texto visível.")


# ------------------------------------------------------------ bloco avançado
def avancado(origem: str, robots: str, llms: str, html: str, cli: Cliente, sondas: bool) -> list[dict]:
    av = []

    def item(i, rotulo, r):
        av.append({"id": i, "label": rotulo, **r})

    tem_sitemap = bool(re.search(r"^\s*sitemap\s*:", robots or "", re.I | re.M))
    item("sitemap", "Sitemap declarado no robots.txt",
         res("pass", "Linha Sitemap: presente.") if tem_sitemap else res("fail", "Nenhuma linha Sitemap: no robots.txt."))

    tem_cs = bool(re.search(r"content-signal\s*:", robots or "", re.I))
    item("content_signals", "Content Signals no robots.txt",
         res("pass", "Diretiva Content-Signal presente.") if tem_cs else res("partial", "Nenhuma diretiva Content-Signal."))

    nos = nos_jsonld(html)
    tem_sameas = any(n.get("sameAs") for n in nos)
    item("sameas", "sameAs no JSON-LD",
         res("pass", "Pelo menos um nó com sameAs.") if tem_sameas else res("partial", "Nenhum nó com sameAs."))
    extras = sorted({t for n in nos for t in tipos_do_no(n) if t in TIPOS_EXTRA})
    item("schema_extra", "Schema além da entidade",
         res("pass", "Tipos encontrados: " + ", ".join(extras) + ".") if extras
         else res("partial", "Nenhum dos tipos " + ", ".join(TIPOS_EXTRA) + "."))

    tem_full = bool(re.search(r"llms-full\.txt", llms or "", re.I))
    item("llms_full", "llms-full.txt referenciado no llms.txt",
         res("pass", "O llms.txt aponta para llms-full.txt.") if tem_full
         else res("partial", "O llms.txt não menciona llms-full.txt."))

    r = cli.get(origem + "/.well-known/mcp/server-card.json", accept="application/json",
                max_bytes=8192, max_redirects=2)
    ok = r["ok"] and 200 <= r["code"] < 300 and "json" in r["ctype"]
    item("mcp_card", "MCP Server Card (/.well-known/mcp/server-card.json)",
         res("pass", f"HTTP {r['code']}, {r['ctype'] or 'sem content-type'}.") if ok
         else res("partial", f"Não encontrado como JSON (HTTP {r['code'] or 'sem resposta'})."))

    r = cli.get(origem + "/.well-known/ai-catalog.json", accept="application/json",
                max_bytes=16384, max_redirects=2)
    ok = r["ok"] and 200 <= r["code"] < 300 and "json" in r["ctype"]
    skills = ok and bool(re.search(r"agent[- ]?skill|skills", r["body"], re.I))
    item("ard", "Catálogo para agentes (/.well-known/ai-catalog.json)",
         res("pass", f"HTTP {r['code']}, JSON" + (", com skills declaradas." if skills else ".")) if ok
         else res("partial", f"Não encontrado como JSON (HTTP {r['code'] or 'sem resposta'})."))

    r = cli.get(origem + "/", accept="text/markdown", max_bytes=4096, max_redirects=2)
    ok = r["ok"] and "markdown" in r["ctype"]
    item("markdown", "Markdown por negociação (Accept: text/markdown)",
         res("pass", f"Content-Type devolvido: {r['ctype']}.") if ok
         else res("partial", f"Content-Type devolvido: {r['ctype'] or 'nenhum'} (esperado text/markdown)."))

    r = cli.get(origem + "/md/", max_bytes=4096, max_redirects=2)
    ok = r["ok"] and 200 <= r["code"] < 300 and ("markdown" in r["ctype"] or "text/plain" in r["ctype"])
    item("md_path", "Rota /md/ em texto",
         res("pass", f"HTTP {r['code']}, {r['ctype']}.") if ok
         else res("partial", f"HTTP {r['code'] or 'sem resposta'}, {r['ctype'] or 'sem content-type'} "
                             "(esperado 2xx em text/markdown ou text/plain)."))

    for i, rotulo, ua in ROBOS_BORDA:
        if not sondas:
            item(i, rotulo, res("skip", "Sonda de borda desligada (--no-probes)."))
            continue
        r = cli.get(origem + "/", ua=ua, max_bytes=2048, max_redirects=2)
        if not r["ok"] or r["code"] == 0:
            item(i, rotulo, res("partial", "Sem resposta nesta rodada (timeout ou erro de conexão)."))
        elif r["code"] in (403, 429) or r["code"] >= 500:
            item(i, rotulo, res("fail", f"HTTP {r['code']} para este User-Agent (possível bloqueio na borda)."))
        else:
            item(i, rotulo, res("pass", f"HTTP {r['code']} para este User-Agent."))
    return av


# ----------------------------------------------------------------- execução
def avalia(url: str, cli: Cliente, bots: list[str], sondas: bool) -> dict:
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    p = urlparse(url)
    if not p.hostname:
        return {"url": url, "erro": "URL inválida."}
    origem = f"{p.scheme}://{p.hostname}" + (f":{p.port}" if p.port else "")

    llms = cli.get(origem + "/llms.txt", max_bytes=65536)
    robots = cli.get(origem + "/robots.txt", max_bytes=65536)
    home = cli.get(origem + "/", max_bytes=1048576)
    if not home["ok"] or home["code"] == 0:
        return {"url": url, "origem": origem, "erro": "A home não respondeu (timeout ou erro de conexão)."}
    html = home["body"]

    checks = [
        {"id": "llms", "peso": 25, "label": "llms.txt (graduado por qualidade)", **checa_llms(llms, html)},
        {"id": "robots", "peso": 30, "label": "robots.txt e robôs de IA", **checa_robots(robots, bots)},
        {"id": "entidade", "peso": 25, "label": "Schema de entidade na home", **checa_entidade(html)},
        {"id": "descricao", "peso": 5, "label": "Meta description da home", **checa_descricao(html)},
        {"id": "declaracao", "peso": 15, "label": "Sinal declarado para agentes de IA", **checa_declaracao(html)},
    ]
    faq = checa_faq(html)
    if faq:
        checks.append({"id": "faq_paridade", "peso": 3, "label": "Paridade FAQ visível x FAQPage", **faq})
    else:
        checks.append({"id": "faq_paridade", "peso": 0, "label": "Paridade FAQ visível x FAQPage",
                       **res("skip", "Sem FAQPage no JSON-LD da home; fora da nota.")})

    total = sum(c["peso"] for c in checks if c["status"] != "skip")
    pontos = sum(c["peso"] if c["status"] == "pass" else c["peso"] / 2 if c["status"] == "partial" else 0
                 for c in checks if c["status"] != "skip")
    nota = int(round(pontos / total * 100)) if total else 0
    nivel = "alta" if nota >= 75 else "média" if nota >= 45 else "baixa"

    return {
        "url": url,
        "origem": origem,
        "http_home": home["code"],
        "nota": nota,
        "nivel": nivel,
        "checks": checks,
        "avancado": avancado(origem, robots["body"] if robots["ok"] else "",
                             llms["body"] if llms["ok"] and 200 <= llms["code"] < 300 else "",
                             html, cli, sondas),
    }


def imprime(r: dict) -> None:
    print(f"\n=== ai-readiness-check: {r.get('origem', r['url'])} ===")
    if "erro" in r:
        print(f"  ERRO  {r['erro']}")
        return
    print(f"Nota de prontidão: {r['nota']}/100 (faixa {r['nivel']}) | HTTP da home: {r['http_home']}\n")
    print("Checagens da nota [peso]:")
    for c in r["checks"]:
        peso = f"[{c['peso']:>2}]" if c["status"] != "skip" else "[ -]"
        print(f"  {ROTULO[c['status']]:<8}{peso} {c['label']}: {c['detalhe']}")
    print("\nBloco avançado (informativo, fora da nota):")
    for c in r["avancado"]:
        print(f"  {ROTULO[c['status']]:<8}{c['label']}: {c['detalhe']}")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(description="Índice de prontidão técnica de um site para IA (0 a 100).")
    ap.add_argument("urls", nargs="+", help="URL(s) do site; a checagem usa a origem (esquema + host)")
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    ap.add_argument("--strict", action="store_true", help="código de saída 1 se alguma checagem da nota der FAIL")
    ap.add_argument("--no-probes", action="store_true",
                    help="pula as sondas de borda com User-Agent de robô de IA")
    ap.add_argument("--delay", type=float, default=1.0, help="intervalo entre requisições, em segundos (padrão 1.0)")
    ap.add_argument("--max-urls", type=int, default=10, help="máximo de sites por execução (padrão 10)")
    ap.add_argument("--bots-json", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_bots.json"),
                    help="lista de robôs de IA no formato do ai-bots-list (padrão: ai_bots.json ao lado do script)")
    args = ap.parse_args()

    try:
        bots = carrega_bots(args.bots_json)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Não consegui ler {args.bots_json}: {exc}", file=sys.stderr)
        sys.exit(2)

    urls = list(dict.fromkeys(args.urls))
    if len(urls) > args.max_urls:
        print(f"Aviso: {len(urls)} URLs informadas; só as {args.max_urls} primeiras serão checadas (--max-urls).",
              file=sys.stderr)
        urls = urls[:args.max_urls]

    cli = Cliente(args.delay)
    resultados = [avalia(u, cli, bots, not args.no_probes) for u in urls]

    if args.json:
        print(json.dumps({"resultados": resultados, "respostas_429": cli.log_429}, ensure_ascii=False, indent=2))
    else:
        for r in resultados:
            imprime(r)
        if cli.log_429:
            print("\nHTTP 429 mesmo depois da nova tentativa em: " + ", ".join(cli.log_429))
        print("\n(Índice próprio de prontidão técnica. Não prevê citação por nenhuma IA.)")

    erro = any("erro" in r for r in resultados)
    falha = any(c["status"] == "fail" for r in resultados if "checks" in r for c in r["checks"])
    sys.exit(2 if erro and len(resultados) == 1 else 1 if (args.strict and (falha or erro)) else 0)


if __name__ == "__main__":
    main()
