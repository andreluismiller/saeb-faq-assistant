# Assistente de FAQ do SAEB/INEP

Um sistema de **Retrieval-Augmented Generation (RAG)** que responde, em linguagem natural, perguntas sobre as pesquisas e avaliações educacionais do INEP (Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira) — como o Saeb — com base na base oficial de Perguntas Frequentes (FAQ) do órgão.

> Projeto desenvolvido como projeto final do [LLM Zoomcamp](https://github.com/DataTalksClub/llm-zoomcamp) (DataTalks.Club).

---

## Índice

- [O problema](#o-problema)
- [Os dados](#os-dados)
- [Como o sistema funciona (arquitetura)](#como-o-sistema-funciona-arquitetura)
- [Critérios de avaliação do projeto](#critérios-de-avaliação-do-projeto)
- [Tecnologias utilizadas](#tecnologias-utilizadas)
- [Como rodar o projeto](#como-rodar-o-projeto)
- [Exemplo de uso](#exemplo-de-uso)
- [Avaliação de recuperação e de respostas (retrieval e LLM evaluation)](#avaliação-de-recuperação-e-de-respostas-retrieval-e-llm-evaluation)
- [Monitoramento](#monitoramento)
- [Screenshots](#screenshots)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Limitações e próximos passos](#limitações-e-próximos-passos)

---

## O problema

O INEP publica, em suas páginas oficiais, extensas seções de Perguntas Frequentes sobre suas pesquisas e avaliações (Saeb, Censo Escolar, Enade, entre outras). Essas FAQs concentram informações importantes — prazos, forma de adesão, metodologia, uso dos resultados — mas estão espalhadas em dezenas de perguntas e respostas em texto corrido, o que torna a busca manual lenta, especialmente para quem não conhece a terminologia do órgão.

Este projeto resolve esse problema construindo um **assistente conversacional** que:

1. Recebe uma pergunta em linguagem natural (ex.: *"Como faço para aderir ao Saeb?"*);
2. Busca, na base de FAQs, os pares pergunta/resposta oficiais mais relevantes para aquela pergunta;
3. Usa um modelo de linguagem (LLM) para redigir uma resposta direta a partir **apenas** desse conteúdo recuperado (evitando que o modelo "invente" informações que não constam na FAQ oficial);
4. Registra a interação e a avaliação do usuário (👍/👎) para possibilitar monitoramento contínuo da qualidade das respostas.

O público-alvo são pessoas que buscam informações sobre as pesquisas do INEP — gestores escolares, pesquisadores, estudantes ou responsáveis — sem precisar garimpar manualmente o site do órgão.

## Os dados

A base de conhecimento está em [`data/faq_saeb.json`](data/faq_saeb.json): uma coleção de perguntas e respostas oficiais extraídas das páginas de FAQ do INEP, organizadas por:

- `survey`: o programa/pesquisa a que a pergunta se refere (ex.: "SAEB");
- `section`: a seção da FAQ de origem;
- `question`: a pergunta original, como publicada pelo INEP;
- `answer`: a resposta oficial correspondente.

Cada par pergunta/resposta é indexado como um documento no banco vetorial (Qdrant), preservando esses metadados no *payload* para permitir tanto a busca semântica quanto filtros por programa.

Também há um [`data/ground_truth.json`](data/ground_truth.json), usado para avaliar a qualidade da recuperação (veja a seção [Avaliação](#avaliação-de-recuperação-e-de-respostas-retrieval-e-llm-evaluation)): para cada pergunta original da FAQ, foram geradas variações de perguntas de usuário (reformulações) que **deveriam** recuperar aquele mesmo documento — permitindo medir se a busca está de fato encontrando o conteúdo correto.

## Como o sistema funciona (arquitetura)

```
                 ┌─────────────────────┐
                 │  data/faq_saeb.json │
                 └──────────┬──────────┘
                            │  ingest.py (embeddings densos + esparsos)
                            ▼
                 ┌─────────────────────┐
                 │       Qdrant        │  (busca híbrida: vetor denso + BM25 esparso,
                 │  (banco vetorial)   │   combinados via Reciprocal Rank Fusion)
                 └──────────┬──────────┘
                            │  contexto recuperado
                            ▼
        pergunta ──▶ ┌─────────────────────┐
       do usuário    │   rag.py (RAG)      │──▶ LLM (Groq, Llama 3.3 70B)
                      └──────────┬──────────┘
                            │  resposta + telemetria
                            ▼
                 ┌─────────────────────┐        ┌──────────────┐
                 │   app.py (Streamlit)│──────▶ │  PostgreSQL   │
                 │  interface de chat  │        │ (histórico e  │
                 └─────────────────────┘        │  feedback)    │
                                                  └───────┬──────┘
                                                          │
                                                          ▼
                                                  ┌──────────────┐
                                                  │    Grafana    │
                                                  │ (monitoramento)│
                                                  └──────────────┘
```

Fluxo passo a passo:

1. **Ingestão** (`src/saeb_faq_assistant/ingest.py`): lê `data/faq_saeb.json`, gera *embeddings* densos (modelo multilíngue `paraphrase-multilingual-mpnet-base-v2`) e esparsos (BM25) para cada pergunta/resposta, e os indexa no Qdrant.
2. **Busca híbrida** (`src/saeb_faq_assistant/rag.py`, método `hybrid_search`): dada uma pergunta do usuário, o sistema busca simultaneamente por similaridade vetorial (semântica) e por BM25 (léxica), combinando os dois rankings com *Reciprocal Rank Fusion* — isso captura tanto sinônimos/paráfrases quanto termos técnicos exatos. Opcionalmente, a busca pode ser restrita a um programa específico (ex.: só "SAEB").
3. **Geração da resposta** (`build_prompt` + `generate_response`): os documentos recuperados são inseridos em um prompt que instrui o LLM a responder **somente** com base nesse conteúdo, em português, e em Markdown.
4. **Interface** (`app.py`): uma aplicação Streamlit permite digitar a pergunta, opcionalmente escolher um programa, ver a resposta e avaliá-la com 👍/👎.
5. **Persistência** (`src/saeb_faq_assistant/db.py`): cada interação (pergunta, resposta, modelo usado, tokens, custo, tempo de resposta) é gravada na tabela `conversations` do PostgreSQL; cada avaliação do usuário é gravada em `feedback`.
6. **Monitoramento** (Grafana): um dashboard provisionado automaticamente lê diretamente do PostgreSQL e exibe tempo de resposta, uso de tokens, uso por modelo, feedback dos usuários e as conversas mais recentes.

## Critérios de avaliação do projeto

Esta seção mapeia os critérios de avaliação usados no LLM Zoomcamp para os componentes deste repositório, facilitando a revisão:

| Critério | Onde encontrar |
|---|---|
| **Descrição do problema** | Seção [O problema](#o-problema) acima |
| **Fluxo de recuperação (retrieval flow)** | Base vetorial (Qdrant) + LLM (Groq) integrados em `src/saeb_faq_assistant/rag.py` |
| **Avaliação da recuperação** | `src/saeb_faq_assistant/eval/retrieval_eval.py` — compara diferentes abordagens de busca (densa, esparsa e híbrida) contra `data/ground_truth.json`; resultados em `src/saeb_faq_assistant/eval/search_results.csv` |
| **Avaliação do LLM** | `src/saeb_faq_assistant/eval/generate_answers.py` e `rag_evals.py` — geram e avaliam respostas de diferentes configurações de prompt/modelo |
| **Interface** | `app.py` — interface web via Streamlit |
| **Pipeline de ingestão** | `src/saeb_faq_assistant/ingest.py` — script Python automatizado (`python -m saeb_faq_assistant.ingest`) |
| **Monitoramento** | Feedback do usuário (👍/👎) persistido em `feedback` + dashboard Grafana com 6 painéis (ver [Monitoramento](#monitoramento)) |
| **Containerização** | `docker-compose.yaml` sobe toda a stack (app, Qdrant, PostgreSQL, Grafana) com um único comando |
| **Reprodutibilidade** | Seção [Como rodar o projeto](#como-rodar-o-projeto); dependências travadas em `uv.lock` |

## Tecnologias utilizadas

- **Linguagem**: Python 3.12
- **Banco vetorial**: [Qdrant](https://qdrant.tech/) (busca híbrida densa + esparsa)
- **Embeddings**: [FastEmbed](https://github.com/qdrant/fastembed) (`paraphrase-multilingual-mpnet-base-v2` para vetores densos, `Qdrant/bm25` para vetores esparsos)
- **LLM**: [Groq API](https://groq.com/) (`llama-3.3-70b-versatile`), via SDK compatível com OpenAI
- **Interface**: [Streamlit](https://streamlit.io/)
- **Persistência**: PostgreSQL
- **Monitoramento**: [Grafana](https://grafana.com/) (open source), provisionado automaticamente
- **Empacotamento/dependências**: [uv](https://docs.astral.sh/uv/)
- **Containerização**: Docker + Docker Compose

## Como rodar o projeto

### Pré-requisitos

- Docker e Docker Compose (já disponíveis por padrão em GitHub Codespaces)
- Uma chave de API da [Groq](https://console.groq.com/keys) (gratuita)

### 1. Clonar o repositório

```bash
git clone https://github.com/<seu-usuario>/saeb-faq-assistant.git
cd saeb-faq-assistant
```

### 2. Configurar as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` e preencha:

| Variável | Descrição | Valor padrão |
|---|---|---|
| `GROQ_API_KEY` | Chave de API da Groq (obrigatória) | — |
| `QDRANT_URL` | Endereço do Qdrant | `http://localhost:6333` (sobrescrito automaticamente para `http://qdrant:6333` dentro do Docker Compose) |
| `POSTGRES_HOST` | Host do PostgreSQL | `localhost` (sobrescrito para `postgres` dentro do Docker Compose) |
| `POSTGRES_PORT` | Porta do PostgreSQL | `5432` |
| `POSTGRES_DB` | Nome do banco | `saeb_faq` |
| `POSTGRES_USER` | Usuário do banco | `saeb_user` |
| `POSTGRES_PASSWORD` | Senha do banco | `saeb_password` |
| `GRAFANA_ADMIN_USER` | Usuário administrador do Grafana | `admin` |
| `GRAFANA_ADMIN_PASSWORD` | Senha do administrador do Grafana | `admin` |

### 3. Subir toda a stack com um único comando

```bash
docker compose up --build
```

Isso inicializa, nesta ordem, os seguintes serviços:

1. **Qdrant** — banco vetorial (dados persistidos em `qdrant_storage/`);
2. **PostgreSQL** — na primeira execução, cria automaticamente as tabelas `conversations` e `feedback` a partir de `db/init.sql`;
3. **Grafana** — sobe já com a fonte de dados do Postgres e o dashboard de monitoramento provisionados;
4. **App** — build da imagem Streamlit e inicialização do assistente, aguardando o PostgreSQL ficar saudável.

### 4. Ingerir os dados (apenas se o Qdrant ainda estiver vazio)

Se você estiver clonando o repositório do zero, sem a pasta `qdrant_storage/` já populada, rode a ingestão antes ou depois de subir a stack:

```bash
uv run python -m saeb_faq_assistant.ingest
```

### 5. Acessar

| Serviço | Endereço | Observação |
|---|---|---|
| Assistente (Streamlit) | http://localhost:8501 | No Codespaces, use a aba **Ports** para abrir a porta 8501 publicamente |
| Grafana | http://localhost:3000 | login com `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` |
| Qdrant (painel web) | http://localhost:6333/dashboard | opcional, para inspecionar a coleção |

### Rodando sem Docker (desenvolvimento local)

```bash
uv sync
docker run -p 6333:6333 -p 6334:6334 -v "$(pwd)/qdrant_storage:/qdrant/storage:z" qdrant/qdrant
uv run python -m saeb_faq_assistant.db      # cria as tabelas no Postgres (requer um Postgres já rodando)
uv run streamlit run app.py
```

## Exemplo de uso

1. Abra o assistente em http://localhost:8501.
2. Digite uma pergunta, por exemplo: *"Como faço para aderir ao Saeb?"*
3. (Opcional) Selecione um programa específico no seletor, para restringir a busca àquele conjunto de perguntas — por padrão, a busca considera todos os programas ("None").
4. Clique em **Perguntar**. O assistente exibirá:
   - A resposta gerada, em Markdown, baseada exclusivamente nas FAQs oficiais recuperadas;
   - Um painel de "Detalhes técnicos" com o modelo usado, tempo de resposta, tokens consumidos e custo estimado;
   - Botões 👍/👎 para avaliar a utilidade da resposta.
5. Cada pergunta feita fica registrada no PostgreSQL e alimenta o dashboard do Grafana em tempo real.

> Adicione aqui um exemplo real de pergunta e resposta capturado do seu ambiente, junto com uma captura de tela (veja a seção [Screenshots](#screenshots)).

## Avaliação de recuperação e de respostas (retrieval e LLM evaluation)

A pasta `src/saeb_faq_assistant/eval/` contém os scripts usados para validar as escolhas técnicas do projeto:

- **`retrieval_eval.py`**: usa `data/ground_truth.json` (perguntas de usuário sintéticas geradas a partir de cada pergunta original da FAQ) para comparar diferentes estratégias de busca — apenas vetor denso, apenas BM25 esparso, e a busca híbrida com RRF — medindo métricas como *Hit Rate* e *MRR*. Os resultados brutos ficam em `search_results.csv`.
- **`generate_answers.py`** e **`rag_evals.py`**: geram respostas do pipeline RAG completo para um conjunto de perguntas de teste e avaliam a qualidade dessas respostas (por exemplo, comparando diferentes prompts ou configurações do LLM).


| Abordagem de busca | Hit Rate | MRR |
|---|---|---|
| Apenas densa (vetorial) | _0.8125_ | _0.7119_ |
| Apenas esparsa (BM25) | _0.8625_ | _0.6369_ |
| Híbrida (RRF) — **usada em produção** | _0.925_ | _0.7815_ |

## Monitoramento

O dashboard do Grafana (`grafana/dashboards/saeb_faq_monitoring.json`) é provisionado automaticamente ao subir a stack e contém os seguintes painéis:

1. **Tempo de resposta** (média por hora)
2. **Uso de tokens** (prompt vs. conclusão, ao longo do tempo)
3. **Uso por modelo** (distribuição de interações por modelo de LLM)
4. **Feedback dos usuários** (contagem de avaliações positivas vs. negativas)
5. **Custo estimado** (em USD, por dia)
6. **Conversas recentes** (tabela com as últimas interações)

Todos os painéis consultam diretamente as tabelas `conversations` e `feedback` do PostgreSQL.

## Screenshots

> Substitua os itens abaixo por capturas de tela reais do seu ambiente (salve as imagens em `docs/img/` e ajuste os caminhos).

- Interface do assistente (pergunta + resposta):
  `![Interface do assistente](docs/img/app-screenshot.png)`
- Dashboard de monitoramento no Grafana:
  `![Dashboard do Grafana](docs/img/grafana-dashboard.png)`
- Exemplo de resposta com detalhes técnicos expandidos:
  `![Detalhes técnicos da resposta](docs/img/app-details.png)`

## Estrutura do repositório

```
saeb-faq-assistant/
├── app.py                     # Interface Streamlit (ponto de entrada)
├── Dockerfile                 # Imagem do serviço "app"
├── docker-compose.yaml        # Orquestra app, Qdrant, PostgreSQL e Grafana
├── .env.example                # Modelo de variáveis de ambiente
├── data/
│   ├── faq_saeb.json           # Base de conhecimento (perguntas e respostas oficiais)
│   └── ground_truth.json       # Perguntas sintéticas para avaliação de recuperação
├── db/
│   └── init.sql                # Schema das tabelas conversations e feedback
├── grafana/
│   ├── dashboards/             # Definição do dashboard (JSON)
│   └── provisioning/           # Datasource e provider provisionados automaticamente
├── qdrant_storage/              # Dados persistidos do Qdrant
└── src/saeb_faq_assistant/
    ├── ingest.py                # Pipeline de ingestão (embeddings + indexação no Qdrant)
    ├── search.py                # Utilitários de busca
    ├── rag.py                   # Orquestração do pipeline RAG (busca híbrida + LLM)
    ├── db.py                    # Acesso ao PostgreSQL (conversas e feedback)
    ├── extract.py                # Extração/preparação dos dados originais
    └── eval/
        ├── retrieval_eval.py     # Avaliação das estratégias de busca
        ├── generate_answers.py   # Geração de respostas para avaliação
        └── rag_evals.py          # Avaliação da qualidade das respostas do LLM
```

## Limitações e próximos passos

- O assistente responde apenas com base no conteúdo indexado das FAQs; perguntas fora desse escopo são recusadas ou respondidas como "informação não encontrada".
- A lista de programas disponível no seletor da interface é obtida dinamicamente do Qdrant (`RAGSystem.list_programs`), portanto reflete sempre os dados efetivamente ingeridos.
- Possíveis melhorias futuras: reranking dos documentos recuperados, reescrita automática da pergunta do usuário antes da busca, e testes A/B de diferentes prompts diretamente pelo dashboard de monitoramento.
