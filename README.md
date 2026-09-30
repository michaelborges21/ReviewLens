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

## Como rodar o sistema com Docker (Instalação do zero)

Se você está em uma máquina nova e quer subir o sistema sem instalar Python/dependências locais:

### 1. Subindo os serviços (App + Ollama)
No terminal, execute:
```bash
docker compose up -d --build
```
Isso vai criar e iniciar a aplicação web na porta `8000` e o container do Ollama.

### 2. Baixando o Modelo de IA
O container do Ollama é iniciado vazio para otimizar o processo. Você precisa baixar o modelo designado (`gemma4:12b` de acordo com a documentação) dentro do container do Ollama:
```bash
docker exec -it reviewlens_ollama ollama pull gemma4:12b
```
*(Nota: dependendo da sua máquina, você pode substituir `gemma4:12b` por `gemma2` ou `llama3` caso prefira testes locais mais leves).*

### 3. Acessando a aplicação
Abra no seu navegador: [http://localhost:8000](http://localhost:8000)

### 4. Derrubando o sistema
Quando terminar, para parar os containers sem perder os dados (os volumes salvam os bancos e o modelo):
```bash
docker compose down
```
Se quiser apagar tudo, incluindo os volumes (apagando o modelo baixado e o banco):
```bash
docker compose down -v
```
