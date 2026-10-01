# ReviewLens

Ferramenta de NLP/LLM para uma editora explorar avaliações de livros sem análise manual:
performance de autores e gêneros, sumarização de reviews, perguntas em linguagem natural (Q&A)
e busca de usuários para entrevista.

## Onde começar
- [`AGENTS.md`](AGENTS.md) — fonte única de instruções de como trabalhar neste repositório.
- [`specs/README.md`](specs/README.md) — índice de todas as specs, status e ADRs.
- [`specs/00-overview.md`](specs/00-overview.md) — problema, hipóteses e roadmap.

## Comandos
```bash
make setup   # instala dependências e hooks
make check   # lint + tipos + testes
```
Os demais comandos (`make data`, `make enrich`, `make index`, `make eval`, `make app`) ainda
não estão implementados — cada um chega junto com a spec correspondente.

## Status
Fase F0 (fundação): estrutura do repositório criada, ingestão e EDA ainda não implementadas.
Veja o roadmap completo em `specs/00-overview.md`.
