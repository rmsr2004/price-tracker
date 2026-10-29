# Price Tracker — Plano de Desenvolvimento (v3)

> Documento destinado a uma LLM/programador. Objetivo: construir um tracker de preços pessoal, gratuito, que envia email quando o preço de um produto desce. Idioma do código e comentários: inglês. Idioma dos emails: inglês (EN).

## 0. Regras para quem implementa

- Implementa **por fases** (secção 9). No fim de cada fase, pára e pergunta ao utilizador se podes avançar.
- Não adiciones funcionalidades não pedidas (UI web, multi-utilizador, etc.).
- Nunca guardes segredos no repositório. O repositório é **público**.
- Cada fase tem de trazer testes e critérios de aceitação cumpridos.
- Se surgir uma decisão não coberta por este documento, pergunta ao utilizador em vez de assumir.

## 1. Decisões tomadas

| Tema | Decisão |
|---|---|
| Linguagem | Python 3.12 |
| Manager | uv |
| Execução | GitHub Actions (workflow agendado) |
| Frequência | **A cada 3 horas** (`cron: "0 */3 * * *"`, UTC). Parâmetro fácil de mudar para 2 h (`0 */2 * * *`). |
| Repositório | Público (aceite pelo utilizador) |
| Base de dados | Supabase (Postgres gerido, plano grátis) |
| ORM / migrações | SQLAlchemy 2.x + Alembic |
| Email | SMTP externo — Brevo |
| Extração de preço | Preço presente no HTML (sem JavaScript) → `requests` + `BeautifulSoup` |
| Gestão de produtos | CLI local a gravar na tabela `products` do Supabase |
| Comandos de gestão | `add`, `list`, `remove`, `set-target` |
| Seletor CSS por produto | Suportado, opcional (`--css-selector`) |
| Termos de uso / `robots.txt` | **Não bloqueiam** o `add` (decisão do utilizador). Ver secção 13. |

## 2. Decisões em aberto

Nenhuma de produto. Apenas configuração a fazer pelo utilizador durante a implementação:
- Escolher o endereço remetente do email e criar os registos SPF/DKIM do domínio no Brevo.
- Escolher e configurar o serviço de heartbeat externo, se se optar por essa mitigação (secção 10).

## 3. Arquitetura

```
 [Máquina do utilizador]                    [GitHub Actions, cron 3 em 3 h]
  python -m tracker add/list/remove/...      python -m tracker run
          │                                           │
          └──────────►  Supabase Postgres  ◄──────────┤
                        (products,                     ├── fetch HTML
                         price_history,                ├── extract price
                         alerts_sent)                  ├── grava histórico
                                                       ├── decide alerta
                                                       └── envia email (Brevo SMTP)
```

- Sem servidor permanente. O `run` acorda, verifica e termina.
- Todo o estado vive no Postgres. Os produtos são adicionados pela CLI local e lidos pelo `run` na execução seguinte; não é preciso commit.
- A CLI local usa `DATABASE_URL` do `.env` do utilizador (no `.gitignore`).

## 4. Estrutura do repositório

```
price-tracker/
├── .github/workflows/
│   ├── track.yml            # cron + workflow_dispatch
│   ├── ci.yml               # testes em cada push/PR
│   └── keepalive.yml        # evita desativação por inatividade (ver 10)
├── src/tracker/
│   ├── __main__.py          # CLI (typer ou argparse)
│   ├── config.py            # variáveis de ambiente (pydantic-settings)
│   ├── fetcher.py           # HTTP
│   ├── extractors/
│   │   ├── base.py
│   │   ├── jsonld.py
│   │   ├── meta.py
│   │   └── css.py
│   ├── models.py            # SQLAlchemy
│   ├── repository.py        # acesso a dados
│   ├── products.py          # lógica de add/list/remove/set-target
│   ├── alerts.py            # regras de alerta (função pura)
│   ├── notifier.py          # SMTP
│   └── runner.py            # orquestração
├── alembic/
├── tests/
│   ├── fixtures/html/
│   ├── unit/
│   └── integration/
├── pyproject.toml
├── .env.example
├── .gitignore               # inclui .env
└── README.md
```

## 5. Modelo de dados

### `products`
| Coluna | Tipo | Notas |
|---|---|---|
| id | serial PK | |
| name | text | extraído da página no `add` (JSON-LD `name`, `og:title` ou `<title>`); editável com `--name` |
| store | text | derivado do domínio do URL |
| url | text UNIQUE | URL normalizado (sem parâmetros de tracking) |
| css_selector | text NULL | usado só se JSON-LD e meta tags falharem |
| target_price | numeric(10,2) NULL | alerta se preço ≤ alvo |
| currency | char(3) | default `EUR` |
| active | bool | default true |
| created_at | timestamptz | |

### `price_history`
| Coluna | Tipo | Notas |
|---|---|---|
| id | bigserial PK | |
| product_id | FK → products (ON DELETE CASCADE) | index (product_id, checked_at desc) |
| price | numeric(10,2) NULL | NULL se falhou |
| in_stock | bool NULL | |
| status | text | `ok`, `fetch_error`, `parse_error` |
| checked_at | timestamptz | |

### `alerts_sent`
| Coluna | Tipo | Notas |
|---|---|---|
| id | bigserial PK | |
| product_id | FK (ON DELETE CASCADE) | |
| price | numeric(10,2) | preço que gerou o alerta |
| reason | text | `price_drop`, `below_target`, `test` |
| sent_at | timestamptz | |

Segurança: ativar RLS nas tabelas do Supabase e ligar com credencial de servidor (string de ligação Postgres) guardada em segredo.

## 6. Regras de alerta (função pura em `alerts.py`)

Entrada: preço atual, histórico recente, `target_price`, último alerta enviado. Saída: lista de razões (pode ser vazia).

1. **Descida:** preço atual < último preço `ok` anterior → `price_drop`.
2. **Abaixo do alvo:** preço atual ≤ `target_price` → `below_target`.
3. **Anti-spam:** não reenviar alerta se já foi enviado para o mesmo produto com preço igual ou inferior ao atual nas últimas 24 h.
4. **Falhas:** preço `NULL` nunca gera alerta de preço. 3 falhas consecutivas num produto (cerca de 9 h com o cron de 3 h) → um único email de aviso "extração a falhar".
5. **Sanidade:** se o preço novo for < 30 % do anterior, tratar como possível erro de parsing; registar e enviar alerta marcado "verificar" (limiar configurável).

## 7. Gestão de produtos (CLI)

Todos os comandos correm localmente e usam `DATABASE_URL`. Invocação: `python -m tracker <comando>`.

### `add <URL> [--target PREÇO] [--css-selector SEL] [--name NOME] [--yes]`
1. Normaliza o URL; se já existir na tabela, termina com mensagem clara.
2. Faz o pedido e tenta extrair: JSON-LD → meta tags → `--css-selector` (se fornecido). **Não verifica `robots.txt`** (decisão do utilizador).
3. Se **não** encontrar preço: não grava; explica que a loja não expõe preço de forma automática e sugere `--css-selector`.
4. Se encontrar: mostra nome, loja, preço e stock encontrados e pede confirmação (`[s/N]`, ou `--yes` para saltar).
5. Grava em `products` e regista a primeira linha em `price_history`.

### `list [--all]`
Tabela: id, nome, loja, último preço, preço-alvo, último check, estado (ativo/inativo/falhas). Por defeito mostra só os ativos; `--all` inclui os desativados.

### `remove <ID|URL> [--deactivate] [--yes]`
- Aceita o `id` ou o URL do produto. Se o identificador não existir, termina com erro claro (sem apagar nada).
- Mostra o nome, a loja e quantas linhas de histórico serão apagadas, e pede confirmação (`[s/N]`, ou `--yes`).
- Por defeito **apaga** o produto e, por cascade, o histórico e os alertas associados.
- Com `--deactivate`, só põe `active=false`: deixa de ser verificado, mas o histórico mantém-se. Reativar com `reactivate <ID>` (comando adicional, simples).
- O `run` ignora produtos inativos.

### `set-target <ID> <PREÇO|none>`
Altera ou remove o preço-alvo.

## 8. Estratégia de testes (requisito central)

O utilizador perguntou: **"como vou saber se funciona antes do preço descer?"** O sistema tem de poder ser validado de ponta a ponta sem esperar por uma descida real.

### 8.1 Testes unitários (pytest, offline, sem rede)
- **Extratores:** para cada loja, guardar em `tests/fixtures/html/` um HTML real. Incluir fixtures de página sem preço, produto sem stock e formatos `1.299,00 €` vs `1,299.00`.
- **Normalização de preço:** parametrizar formatos PT/EN (`199,00 €`, `€199.00`, `1 299,00€`).
- **Regras de alerta:** tabela parametrizada (preço anterior, preço atual, alvo, último alerta → alertas esperados). Cobrir: descida, igual, subida, abaixo do alvo, anti-spam, `NULL`, queda suspeita.
- **Notifier:** mock de `smtplib.SMTP`; verificar assunto, destinatário, corpo, link.
- **Gestão de produtos:** URL inválido, duplicado, recusa sem preço, aceitação com `--css-selector`, confirmação interativa (`--yes` e resposta `n`). Para o `remove`: por id, por URL, id inexistente, cascade do histórico e alertas, `--deactivate` mantém o histórico, e o `run` ignora inativos.

### 8.2 Testes de integração
- Postgres real em contentor (`testcontainers` ou serviço do GitHub Actions). Aplicar migrações Alembic desde zero e testar `repository.py` e os comandos de gestão.
- Servidor HTTP local (`pytest-httpserver`) que serve as fixtures HTML. Teste ponta a ponta: `add` do URL local (199,00) → `run` → alterar a fixture para 179,00 → `run` → verificar `price_history`, `alerts_sent` e email enviado (SMTP falso, ex.: `aiosmtpd`). Depois `remove` e confirmar que o `run` seguinte não o verifica.

### 8.3 Ferramentas de verificação manual (CLI)

| Comando | Para quê |
|---|---|
| `check-url <URL> [--css-selector SEL]` | Extrai e imprime o preço de um URL sem gravar nada. |
| `run --dry-run` | Corre tudo, mas não grava nem envia emails; imprime o que faria. |
| `send-test-email` | Envia um email de teste real via Brevo. Valida credenciais, SPF/DKIM e se cai em spam. |
| `simulate --product-id N --price 150.00` | Simula que o produto passou a custar X: executa a lógica de alerta e **envia o email real**, marcado `[TESTE]`, com `reason='test'`. Prova o fluxo completo antes de existir descida real. |
| `status` | Produtos, último preço, última verificação e falhas recentes. |

### 8.4 Testes no GitHub Actions
- `ci.yml` corre unitários + integração em cada push/PR.
- `track.yml` tem `workflow_dispatch` com input `dry_run` (boolean) para disparar manualmente sem esperar pelo cron.
- Teste de aceitação em produção (checklist, secção 11).

### 8.5 Deteção de quebra silenciosa
- Falha de extração grava `status='parse_error'` (nunca ignorar silenciosamente).
- Regra 4 da secção 6 avisa por email após 3 falhas seguidas.
- Opcional: teste "canário" semanal contra os URLs reais que falha o workflow se algum extrator devolver `NULL`.

## 9. Fases de implementação

Cada fase termina com a pergunta ao utilizador: "Posso avançar para a fase seguinte?"

**Fase 1 — Esqueleto e configuração.** `pyproject.toml`, pastas, `config.py`, `.env.example`, `.gitignore`. Aceitação: `python -m tracker --help` funciona; env var em falta dá erro claro.

**Fase 2 — Extração de preço.** `fetcher.py` (timeout 15 s, 3 retries com backoff, User-Agent identificável), extratores JSON-LD → meta → CSS, comando `check-url`. Aceitação: testes com fixtures a passar; `check-url` devolve o preço de um site real do utilizador.

**Fase 3 — Base de dados.** Modelos, migrações Alembic, `repository.py`, ligação ao Supabase. Aceitação: migrações aplicam-se de zero; testes de integração a passar.

**Fase 4 — Gestão de produtos.** `add`, `list`, `remove` (incl. `--deactivate`, `reactivate`), `set-target`. Aceitação: `add` de um URL real grava produto e primeira linha de histórico; casos de recusa testados; `remove` com cascade e por URL testado.

**Fase 5 — Alertas e email.** `alerts.py`, `notifier.py` (Brevo SMTP), `send-test-email`, `simulate`. Aceitação: tabela de alertas a 100 %; email de teste na caixa de entrada (não em spam).

**Fase 6 — Orquestração.** `runner.py`, `run`, `run --dry-run`, `status`. Aceitação: teste ponta a ponta (secção 8.2).

**Fase 7 — GitHub Actions e produção.** `track.yml`, `ci.yml`, `keepalive.yml`, GitHub Secrets, README. Aceitação: checklist da secção 11.

## 10. GitHub Actions — pormenores

- Cron `0 */3 * * *` em **UTC**; mínimo permitido 5 min; execuções podem atrasar ou ser saltadas em alturas de carga. Aceitável para este caso.
- Num repositório público, os workflows agendados são **desativados após 60 dias sem atividade no repositório**, sem aviso fiável. Mitigação em `keepalive.yml` (workflow mensal que mantém o agendamento ativo) **e/ou** heartbeat externo (ping no fim de cada execução a um serviço que avisa se o ping falhar). **[Verificar a solução na documentação oficial do GitHub antes de implementar.]**
- Usar `concurrency` para impedir execuções sobrepostas.
- Segredos (GitHub Secrets) para o `track.yml`: `DATABASE_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_TO`.
- Os URLs dos produtos não ficam no repositório (estão no Supabase).
- Uma escrita na base de dados a cada 3 h deve evitar a pausa do Supabase por inatividade (7 dias no plano grátis). Confirmar com um teste de uma semana.
- Ligação ao Supabase a partir do GitHub Actions: verificar na documentação do Supabase qual a string de ligação adequada (direta vs pooler, IPv4/IPv6) para os runners.

## 11. Checklist de aceitação em produção

- [ ] `ci.yml` verde.
- [ ] `check-url` devolve o preço correto em cada loja que o utilizador quer seguir.
- [ ] `add` de um produto real grava produto e primeira linha de histórico; `list` mostra-o.
- [ ] `remove` de um produto de teste funciona e o `run` seguinte já não o verifica.
- [ ] `send-test-email` chega à caixa de entrada (SPF/DKIM: pass).
- [ ] `simulate` com preço inferior gera email `[TESTE]` real e linha em `alerts_sent`.
- [ ] `workflow_dispatch` com `dry_run=true` corre sem erros.
- [ ] Primeira execução agendada real grava linhas em `price_history` para o produto adicionado via CLI.
- [ ] Ao fim de 7 dias, o projeto Supabase continua ativo.
- [ ] Forçar falha (URL inválido) → erro registado e aviso após 3 falhas.

## 12. Email — Brevo

- SMTP com STARTTLS (porta 587 é o padrão para submissão; **confirmar host, porta e credenciais na documentação oficial do Brevo**).
- Configurar o domínio do utilizador no Brevo e criar registos **SPF e DKIM** (e DMARC, recomendado).
- O plano grátis do Brevo foi indicado como 300 emails/dia numa fonte não oficial; **confirmar na página de preços do Brevo**. O volume esperado é de poucos emails por dia.
- Conteúdo do email (PT): nome do produto, loja, preço anterior, preço novo, diferença em € e %, link direto, data/hora da verificação.

## 13. Notas de scraping

- O utilizador decidiu não condicionar o tracker aos termos de uso nem ao `robots.txt` dos sites. O código **não** deve fazer essa verificação.
- Boa prática técnica (para reduzir o risco de bloqueio de IP, não por questões de termos): User-Agent razoável, ≥ 2 s entre pedidos à mesma loja, sem paralelismo agressivo. Com poucos URLs a cada 3 h, o volume é baixo.
- Não implementar contornos de proteções anti-bot (rotação de proxies, CAPTCHAs). Se uma loja bloquear, o produto fica com `fetch_error` e o utilizador é avisado (regra 4).

## 14. Fora de âmbito

UI web, app móvel, multi-utilizador, scraping com browser (Playwright), notificações push, outros canais além de email.

## 15. Fontes a consultar (a LLM deve verificar, não assumir)

- GitHub Docs — Actions: evento `schedule`, desativação de workflows, limites.
- Supabase Docs — Project pausing; ligação ao Postgres (pooler); RLS.
- Brevo Docs — SMTP relay, autenticação de domínio.
- SQLAlchemy 2.x e Alembic — documentação oficial.
- schema.org/Product e `Offer` — para JSON-LD.
