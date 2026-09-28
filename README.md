**English** · [Português (Brasil)](README.pt-BR.md)

# ai-readiness-check

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) ![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg) [![Data: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-lightgrey.svg)](DATA-LICENSE)

`ai-readiness-check` is a free, open source command line tool that gives a
website a 0 to 100 technical readiness score for being read by AI search
engines and assistants (Google AI Mode and AI Overviews, Gemini,
Perplexity, ChatGPT, Claude). It fetches a few public files from the
domain (`/llms.txt`, `/robots.txt`, the home page and some well-known
paths), runs weighted checks and prints a PASS, PARCIAL (partial), FAIL
or SKIP checklist with the technical reason for each line. It is the
command line version of the engine behind the online
[AI visibility test](https://lucasferrazseo.com/ferramentas/teste-de-visibilidade-em-ia/).

The score is an index of our own for technical readiness. It is not a
prediction of citation by any AI. The report is printed in Brazilian
Portuguese.

## Contents

- [Background](#background)
- [What it checks](#what-it-checks)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [FAQ](#faq)
- [Limitations](#limitations)
- [Methodology](#methodology)
- [Contributing](#contributing)
- [Author](#author)
- [License](#license)

## Background

Before an AI assistant can cite a company, its crawlers have to be
allowed in, reach the server without being blocked at the edge, and find
something that says who the company is. Those conditions are visible from
outside, in files every site already serves. `ai-readiness-check` reads
them in one pass, so you can audit your own site, compare several sites,
or run it on a schedule without opening a browser.

## What it checks

**Scored checks.** PASS counts the full weight, PARCIAL counts half,
FAIL counts zero. The score is the sum divided by the total weight of the
checks that apply.

| Check | Weight | PASS when |
|---|---|---|
| `llms.txt`, graded by quality | 25 | the file answers 2xx, has at least 50 bytes, has absolute links and mentions the brand (taken from `og:site_name` or `<title>`); a short file without links, or one missing links or the brand, is PARCIAL |
| `robots.txt` and AI bots | 30 | at least one AI bot from `ai_bots.json` is named without `Disallow: /`; FAIL if a named AI bot, or `User-agent: *` with no named exception, gets `Disallow: /`; PARCIAL if no AI bot is named or the file is missing |
| Entity schema on the home page | 25 | an Organization, LocalBusiness (or listed subtype) node has `name`, `url`, `logo`/`image`, `sameAs` and `address`/`telephone`; 3 or 4 of 5 is PARCIAL |
| Home meta description | 5 | a `meta name="description"` with 20 characters or more |
| Signal declared for AI agents | 15 | `link rel="alternate" type="text/plain"`, `meta name="ai-content-declaration"`/`"ai-summary"` or `link rel="mcp"` on the home page (otherwise PARCIAL) |
| Visible FAQ x FAQPage parity | 3 | every `FAQPage` question in the JSON-LD also appears in the visible text; SKIP (out of the score) when there is no `FAQPage` |

Score bands: 75 or more is `alta` (high), 45 to 74 is `média` (medium),
below 45 is `baixa` (low).

**Advanced block (informational, outside the score).** Sitemap line in
`robots.txt`, Content Signals (`Content-Signal:`) in `robots.txt`, `sameAs`
in any JSON-LD node, content schema beyond the entity (FAQPage, Article,
BlogPosting, WebSite, BreadcrumbList, Product, Service), `llms-full.txt`
referenced in `llms.txt`, MCP Server Card at
`/.well-known/mcp/server-card.json`, agent catalog at
`/.well-known/ai-catalog.json`, Markdown by content negotiation
(`Accept: text/markdown`), a `/md/` route served as text, and edge probes:
the home page requested with the public user agents of GPTBot, ClaudeBot
and PerplexityBot. A 403, 429 or 5xx answer to a probe is FAIL.

## Requirements

Python 3.9 or newer and the `requests` library (see `requirements.txt`).

## Installation

```bash
git clone https://github.com/LucasFerrazSEO/ai-readiness-check.git
cd ai-readiness-check
pip install -r requirements.txt
```

## Usage

**1. Check a site.** The tool uses the origin (scheme and host) of the URL
you pass. A real output example:

```bash
python ai_readiness_check.py https://example.com/
```

```
=== ai-readiness-check: https://example.com ===
Nota de prontidão: 22/100 (faixa baixa) | HTTP da home: 200

Checagens da nota [peso]:
  FAIL    [25] llms.txt (graduado por qualidade): /llms.txt não respondeu com sucesso (HTTP 404).
  PARCIAL [30] robots.txt e robôs de IA: /robots.txt indisponível (HTTP 404); o acesso dos robôs de IA não está declarado.
  FAIL    [25] Schema de entidade na home: A home não tem bloco JSON-LD.
  FAIL    [ 5] Meta description da home: Sem meta description (ou com menos de 20 caracteres).
  PARCIAL [15] Sinal declarado para agentes de IA: Nenhum link rel="alternate" text/plain, meta ai-* ou link rel="mcp" na home.
  SKIP    [ -] Paridade FAQ visível x FAQPage: Sem FAQPage no JSON-LD da home; fora da nota.

Bloco avançado (informativo, fora da nota):
  FAIL    Sitemap declarado no robots.txt: Nenhuma linha Sitemap: no robots.txt.
  PARCIAL Content Signals no robots.txt: Nenhuma diretiva Content-Signal.
  ...
  PARCIAL Markdown por negociação (Accept: text/markdown): Content-Type devolvido: text/html (esperado text/markdown).
  PARCIAL Rota /md/ em texto: HTTP 404, text/html (esperado 2xx em text/markdown ou text/plain).
  PASS    Resposta ao GPTBot (OpenAI): HTTP 200 para este User-Agent.
  PASS    Resposta ao ClaudeBot (Anthropic): HTTP 200 para este User-Agent.
  PASS    Resposta ao PerplexityBot (Perplexity): HTTP 200 para este User-Agent.

(Índice próprio de prontidão técnica. Não prevê citação por nenhuma IA.)
```

And a site that implements the signals (real output, shortened):

```
=== ai-readiness-check: https://lucasferrazseo.com ===
Nota de prontidão: 100/100 (faixa alta) | HTTP da home: 200

Checagens da nota [peso]:
  PASS    [25] llms.txt (graduado por qualidade): /llms.txt com 56099 bytes, links absolutos e menção à marca "Lucas Ferraz SEO".
  PASS    [30] robots.txt e robôs de IA: 37 robô(s) de IA citado(s) por nome sem Disallow: /.
  PASS    [25] Schema de entidade na home: Nó de entidade com name, url, logo, sameAs e address/telephone.
  ...
  PASS    [ 3] Paridade FAQ visível x FAQPage: As 29 pergunta(s) do FAQPage aparecem no texto visível.
```

**2. Check several sites** with a longer interval between requests:

```bash
python ai_readiness_check.py https://example.com/ https://example.org/ --delay 2
```

**3. Skip the edge probes** (no request with an AI bot user agent):

```bash
python ai_readiness_check.py https://example.com/ --no-probes
```

**4. JSON output and CI.**

```bash
python ai_readiness_check.py https://example.com/ --json
python ai_readiness_check.py https://example.com/ --strict   # código de saída 1 se houver FAIL na nota
```

With `--strict`, the exit code is 1 when any scored check is FAIL. Other
options: `--max-urls` (default 10 sites per run) and `--bots-json` (a
different bot list in the same format).

## FAQ

**Is ai-readiness-check really free?**
Yes. The code is open source under the MIT license, with no sign-up, API
key or usage limit. The bot list in `ai_bots.json` is CC BY 4.0.

**How many requests does it make?**
About ten per site: `llms.txt`, `robots.txt`, the home page, four
well-known or content-negotiation requests and three edge probes (zero
with `--no-probes`). Requests are spaced by `--delay` (1 second by
default), use an identifiable user agent and a timeout, and a 429 answer
is retried once after a wait.

**Where does the bot list come from?**
From `ai_bots.json`, in the same format as the
[ai-bots-list](https://github.com/LucasFerrazSEO/ai-bots-list) repository
(`user_agent`, `provedor`, `produto`, `categoria`). You can replace it with
`--bots-json`.

**Does a score of 100 mean AI assistants will cite my site?**
No. The score is an index of technical readiness built from public
signals. It does not read any model's answer and does not predict
citation.

## Limitations

The HTML checks use regular expressions on the first 1 MB of the home
page and do not run JavaScript, so a site that injects JSON-LD or meta
tags on the client side may score lower than it deserves. Some patterns
depend on attribute order (for example `rel` before `type`). The edge
probes send the public user agent of each bot from your own IP address: a
CDN that verifies bots by IP range may block the probe while still
letting the real bot in, so a FAIL there is a lead to investigate, not a
verdict. Only the home page is analyzed.

## Methodology

This is a Python port of the engine behind the online AI visibility test
of [lucasferrazseo.com](https://lucasferrazseo.com/ferramentas/teste-de-visibilidade-em-ia/),
with the same checks, weights and scoring rule (partial counts half the
weight). Everything specific to WordPress or to the website (REST
endpoint, cache, per-item prompts) was removed. Two points differ on
purpose: the FAQ parity check ignores the text inside `<script>` tags, so
the JSON-LD itself is never counted as visible text, and the `/md/` route
only passes when it answers as `text/markdown` or `text/plain`.

## Contributing

Bug reports and suggestions are welcome through [GitHub Issues](https://github.com/LucasFerrazSEO/ai-readiness-check/issues).

## Author

[Lucas Ferraz](https://lucasferraz.com) is an SEO, website development and Generative Engine Optimization specialist and the founder of [Lucas Ferraz SEO](https://lucasferrazseo.com).

## License

Code: MIT. See [LICENSE](LICENSE). Data in `ai_bots.json`: CC BY 4.0, see [DATA-LICENSE](DATA-LICENSE).
