[English](README.md) · **Português (Brasil)**

# ai-readiness-check

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) ![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg) [![Data: CC BY 4.0](https://img.shields.io/badge/Data-CC%20BY%204.0-lightgrey.svg)](DATA-LICENSE)

O `ai-readiness-check` é uma ferramenta de linha de comando gratuita e de
código aberto que dá a um site uma nota de 0 a 100 de prontidão técnica
para leitura por buscadores e assistentes com IA (Google AI Mode e AI
Overviews, Gemini, Perplexity, ChatGPT, Claude). Ela busca alguns arquivos
públicos do domínio (`/llms.txt`, `/robots.txt`, a home e alguns caminhos
conhecidos), roda checagens ponderadas e imprime um checklist PASS,
PARCIAL, FAIL ou SKIP com o motivo técnico de cada linha. É a versão de
linha de comando do motor do
[teste de visibilidade em IA](https://lucasferrazseo.com/ferramentas/teste-de-visibilidade-em-ia/)
online.

A nota é um índice próprio de prontidão técnica. Não é previsão de
citação por nenhuma IA. O relatório sai em português.

## Sumário

- [Contexto](#contexto)
- [O que a ferramenta verifica](#o-que-a-ferramenta-verifica)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Uso](#uso)
- [Perguntas frequentes](#perguntas-frequentes)
- [Limitações](#limitações)
- [Método e origem](#método-e-origem)
- [Como contribuir](#como-contribuir)
- [Autor](#autor)
- [Licença](#licença)

## Contexto

Antes de um assistente de IA citar uma empresa, os robôs dele precisam
ter acesso liberado, chegar ao servidor sem bloqueio na borda e encontrar
algo que diga quem é a empresa. Essas condições são visíveis de fora, em
arquivos que todo site já serve. O `ai-readiness-check` lê esses arquivos
de uma vez, para você auditar o próprio site, comparar vários sites ou
rodar a checagem de forma agendada sem abrir o navegador.

## O que a ferramenta verifica

**Checagens da nota.** PASS vale o peso inteiro, PARCIAL vale metade,
FAIL vale zero. A nota é a soma dividida pelo total de pesos das
checagens que se aplicam.

| Checagem | Peso | PASS quando |
|---|---|---|
| `llms.txt` graduado por qualidade | 25 | o arquivo responde 2xx, tem pelo menos 50 bytes, links absolutos e menciona a marca (tirada do `og:site_name` ou do `<title>`); arquivo curto sem links, ou sem links ou sem a marca, é PARCIAL |
| `robots.txt` e robôs de IA | 30 | pelo menos um robô de IA do `ai_bots.json` citado por nome sem `Disallow: /`; FAIL se um robô de IA citado por nome, ou `User-agent: *` sem exceção nomeada, recebe `Disallow: /`; PARCIAL se nenhum robô de IA é citado ou o arquivo não existe |
| Schema de entidade na home | 25 | um nó Organization, LocalBusiness (ou subtipo listado) com `name`, `url`, `logo`/`image`, `sameAs` e `address`/`telephone`; 3 ou 4 de 5 é PARCIAL |
| Meta description da home | 5 | uma `meta name="description"` com 20 caracteres ou mais |
| Sinal declarado para agentes de IA | 15 | `link rel="alternate" type="text/plain"`, `meta name="ai-content-declaration"`/`"ai-summary"` ou `link rel="mcp"` na home (senão, PARCIAL) |
| Paridade FAQ visível x FAQPage | 3 | toda pergunta do `FAQPage` no JSON-LD aparece também no texto visível; SKIP (fora da nota) quando não há `FAQPage` |

Faixas da nota: 75 ou mais é `alta`, de 45 a 74 é `média`, abaixo de 45
é `baixa`.

**Bloco avançado (informativo, fora da nota).** Linha de sitemap no
`robots.txt`, Content Signals (`Content-Signal:`) no `robots.txt`, `sameAs`
em qualquer nó de JSON-LD, schema de conteúdo além da entidade (FAQPage,
Article, BlogPosting, WebSite, BreadcrumbList, Product, Service),
`llms-full.txt` referenciado no `llms.txt`, MCP Server Card em
`/.well-known/mcp/server-card.json`, catálogo para agentes em
`/.well-known/ai-catalog.json`, Markdown por negociação de conteúdo
(`Accept: text/markdown`), rota `/md/` servida como texto e sondas de
borda: a home pedida com os User-Agents públicos do GPTBot, do ClaudeBot
e do PerplexityBot. Resposta 403, 429 ou 5xx a uma sonda é FAIL.

## Requisitos

Python 3.9 ou mais novo e a biblioteca `requests` (veja o
`requirements.txt`).

## Instalação

```bash
git clone https://github.com/LucasFerrazSEO/ai-readiness-check.git
cd ai-readiness-check
pip install -r requirements.txt
```

## Uso

**1. Cheque um site.** A ferramenta usa a origem (esquema e host) da URL
informada. Exemplo de saída real:

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

E um site que implementa os sinais (saída real, encurtada):

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

**2. Cheque vários sites** com intervalo maior entre as requisições:

```bash
python ai_readiness_check.py https://example.com/ https://example.org/ --delay 2
```

**3. Pule as sondas de borda** (nenhuma requisição com User-Agent de robô
de IA):

```bash
python ai_readiness_check.py https://example.com/ --no-probes
```

**4. Saída em JSON e uso em CI.**

```bash
python ai_readiness_check.py https://example.com/ --json
python ai_readiness_check.py https://example.com/ --strict   # código de saída 1 se houver FAIL na nota
```

Com `--strict`, o código de saída é 1 quando alguma checagem da nota dá
FAIL. Outras opções: `--max-urls` (padrão de 10 sites por execução) e
`--bots-json` (outra lista de robôs no mesmo formato).

## Perguntas frequentes

**O ai-readiness-check é gratuito mesmo?**
Sim. O código é aberto sob a licença MIT, sem cadastro, chave de API ou
limite de uso. A lista de robôs em `ai_bots.json` é CC BY 4.0.

**Quantas requisições ele faz?**
Cerca de dez por site: `llms.txt`, `robots.txt`, a home, quatro
requisições a caminhos conhecidos ou por negociação de conteúdo e três
sondas de borda (zero com `--no-probes`). As requisições são espaçadas
pelo `--delay` (1 segundo por padrão), usam User-Agent identificável e
timeout, e uma resposta 429 ganha uma nova tentativa depois de uma
espera.

**De onde vem a lista de robôs?**
Do `ai_bots.json`, no mesmo formato do repositório
[ai-bots-list](https://github.com/LucasFerrazSEO/ai-bots-list)
(`user_agent`, `provedor`, `produto`, `categoria`). Dá para trocar a
lista com `--bots-json`.

**Nota 100 quer dizer que os assistentes de IA vão citar meu site?**
Não. A nota é um índice de prontidão técnica montado a partir de sinais
públicos. Ela não lê a resposta de nenhum modelo e não prevê citação.

## Limitações

As checagens de HTML usam expressões regulares sobre o primeiro 1 MB da
home e não executam JavaScript, então um site que injeta JSON-LD ou meta
tags no navegador pode ter nota menor do que deveria. Alguns padrões
dependem da ordem dos atributos (por exemplo, `rel` antes de `type`). As
sondas de borda enviam o User-Agent público de cada robô a partir do seu
próprio IP: uma CDN que verifica robôs por faixa de IP pode bloquear a
sonda e ainda assim liberar o robô verdadeiro, então um FAIL ali é uma
pista para investigar, não um veredito. Só a home é analisada.

## Método e origem

Esta é uma versão em Python do motor do teste de visibilidade em IA do
[lucasferrazseo.com](https://lucasferrazseo.com/ferramentas/teste-de-visibilidade-em-ia/),
com as mesmas checagens, pesos e regra de pontuação (parcial vale metade
do peso). Tudo o que era específico do WordPress ou do site (endpoint
REST, cache, prompts por item) foi removido. Dois pontos diferem de
propósito: a paridade de FAQ ignora o texto dentro de `<script>`, para o
próprio JSON-LD nunca contar como texto visível, e a rota `/md/` só passa
quando responde como `text/markdown` ou `text/plain`.

## Como contribuir

Relatos de erro e sugestões são bem-vindos pelas [Issues do GitHub](https://github.com/LucasFerrazSEO/ai-readiness-check/issues).

## Autor

[Lucas Ferraz](https://lucasferraz.com) é especialista em SEO, criação de sites e Generative Engine Optimization e fundador da [Lucas Ferraz SEO](https://lucasferrazseo.com).

## Licença

Código: MIT. Veja o arquivo [LICENSE](LICENSE). Dados em `ai_bots.json`: CC BY 4.0, veja [DATA-LICENSE](DATA-LICENSE).
