> 🇧🇷 Português | 🇺🇸 [English](README.md)
> **Nota:** este documento é uma tradução do README.md. Em caso de divergência, a versão em inglês é a fonte de verdade.

# agent-replay-harness

Agentes baseados em LLM são difíceis de depurar: o mesmo prompt pode produzir chamadas de ferramentas diferentes em execuções posteriores. Os traces de observabilidade mostram o que aconteceu, mas registrar um trace não significa conseguir reproduzir a falha de maneira determinística. Este harness registra as interações de um único agente simulado, reproduz respostas gravadas de LLM e ferramentas e substitui uma resposta de ferramenta para testar uma política fixa de recuperação.

![CI configurado; status remoto não verificado](.github/assets/ci-badge.svg)

O badge informa que existe um workflow de CI, **não** que o GitHub Actions remoto já passou. Os testes locais e resultados medidos são apresentados abaixo. Não é necessário usar chave de API, banco de dados, API externa ou dependência paga.

## Início rápido (dois comandos)

A partir de um clone limpo do repositório, na pasta principal (requer Python 3.11+ e GNU Make):

```bash
python -m venv .venv
make setup && make demo
```

O setup instala as dependências de desenvolvimento, podendo acessar o repositório de pacotes. `make demo` e `make test` **não fazem chamadas de rede**. Não é necessário configurar variáveis de ambiente. No Windows, utilize WSL ou um shell POSIX com GNU Make para executar os comandos documentados.

A demonstração grava um trace, reproduz de maneira estrita o trace de referência, injeta falhas de retry/fallback/fail-fast, informa a primeira decisão divergente em cada cenário e mostra um resumo na CLI. Todos os dados são sintéticos e locais.

```text
record: outcome=success
replay: outcome=success; decisions_identical=True
inject retry: outcome=success; decisions_identical=False
inject fallback: outcome=success; decisions_identical=False
inject fail_fast: outcome=failure; decisions_identical=False
Local trace dashboard: 5 traces; 4 successes; 1 failure; 3 divergences
```

As linhas acima resumem o comportamento esperado da demonstração, não uma execução de serviço real. Execute `make demo` para reproduzir a saída efetiva.

## Comandos

```bash
make test
make lint
make bench

.venv/bin/python -m src.cli record --output runs/recorded.json
.venv/bin/python -m src.cli replay examples/traces/success.json --output runs/replayed.json
.venv/bin/python -m src.cli inject examples/traces/success.json \
  --fault examples/faults/retry.json --output runs/retry.json
.venv/bin/python -m src.cli report runs/
```

`make bench` gera [RESULTS.md](RESULTS.md) automaticamente. O script executa 100 gravações diretas de um agente simulado, 100 replays estritos e 100 replays com falhas injetadas. Apenas o script de benchmark escreve os resultados numéricos em `RESULTS.md`.

## Arquitetura

```text
                    CLI (record / replay / inject / report)
                                  |
                             DemoAgent
                                  |
                         LLM + Tool gateway
                                  |
                   +--------------+-------------+
                   |                            |
                Recorder                    Replayer
                   |                            |
               Trace JSON               Recorded responses
                   |                            |
                   |                     FaultInjector? ----> Local tool fixtures
                   |                            |
                   +------------ Comparator ---+
                                   |
                          Decision diff / CLI
                                   |
                      Benchmark -> RESULTS.md
```

O trace é um JSON versionado com `schema_version`, `run_id`, `agent_version`, `started_at`, `input`, `mode` e um array ordenado `events`. Os eventos são `llm.call`, `tool.call` ou `agent.decision`, cada um com `seq` e `timestamp`. Eventos de LLM e ferramenta contêm pedido e resposta; decisões contêm a ação e, opcionalmente, ferramenta ou resultado. O trace de referência é [success.json](examples/traces/success.json), produzido por uma execução do agente simulado, não pela escrita manual dos eventos.

**Replay estrito:** verifica a ordem e os argumentos das chamadas conforme as interações gravadas. Chamadas inesperadas ou decisões alteradas provocam falha explícita; o sistema não invoca LLM ou serviço real. **Replay com injeção:** substitui uma resposta gravada de `tool.call` e usa fixtures locais determinísticas no novo caminho de recuperação. Novas chamadas ao LLM após a injeção não são suportadas e geram erro, em vez de uma resposta inventada.

### Contrato do arquivo de falha

```json
{
  "target_seq": 3,
  "event_type": "tool.call",
  "replacement_response": {
    "status": "error",
    "error": {
      "code": "SERVICE_UNAVAILABLE",
      "message": "Simulated HTTP 503",
      "retryable": true
    }
  }
}
```

`target_seq` deve ser um inteiro positivo e existir no trace original. O alvo precisa corresponder a um evento `tool.call`. Um alvo, tipo de evento ou objeto de resposta inválido causa um erro claro e um código de saída diferente de zero. A ferramenta do trace de exemplo está na sequência **3**. `retry.json`, `fallback.json` e `fail_fast.json` abrangem nova tentativa após HTTP 503, alternativa após timeout e falha segura diante de uma resposta inválida. As decisões de recuperação vêm de regras Python, não de uma nova amostragem de LLM.

## Definição de pronto do MVP

Um critério passa somente com evidência de execução. Caso contrário, recebe FAIL ou NOT RUN; o benchmark mede os critérios 3 e 4. O status da CI remota é independente da execução local.

| # | Critério binário de aceitação | Medido por |
|---|---|---|
| 1 | Em um clone Git limpo, criar uma `.venv` nova com `python -m venv .venv`; executar `make setup && make demo` sem variáveis de ambiente previamente configuradas, sem chamadas de rede além da instalação, e obter exit code 0 da demo. | Log dos comandos no clone limpo |
| 2 | `make test` passa com pelo menos 12 testes, incluindo retry, fallback e fail-fast. | Saída do pytest |
| 3 | Replay estrito de `success.json` reproduz 100% das decisões normalizadas, por medição e não por suposição. | **#5**, resultado do benchmark |
| 4 | A injeção de `retry.json` gera divergência proposital detectada e relatada pelo comparador. | **#5**, resultado do benchmark + demonstração da CLI |
| 5 | `benchmarks/run_benchmarks.py` mede replay, tempo e injeções e escreve `RESULTS.md` automaticamente. | Saída do benchmark e arquivo gerado |

Consulte [RESULTS.md](RESULTS.md) para as medições locais e o relatório de implementação entregue junto com o repositório para verificar o resultado dos critérios. Qualquer falha em algum critério deve ser declarada na seção de limitações abaixo.

## Decisões de engenharia

1. **JSON em vez de SQLite.** Um trace é legível, comparável e fácil de anexar ao relato de um bug. Em contrapartida, há leitura e escrita de arquivo completo, sem consultas indexadas, concorrência ou suporte a grandes traces.
2. **Replay síncrono em vez de distribuído.** A ordem de interação fica explícita e testável sem um agendador. Concorrência, temporizadores e condições de corrida ficam fora da alegação de reprodutibilidade.
3. **Respostas gravadas de LLM em vez de novas amostras.** O replay reproduz a decisão registrada. Não prevê a resposta de um LLM real a um novo erro; por isso, os caminhos injetados usam uma política fixa de recuperação em Python e fixtures locais.
4. **Adaptador executável em vez de integração direta com OpenTelemetry.** Spans descrevem a execução; o MVP precisa conferir pedidos e substituir respostas na fronteira das chamadas. A exportação para OpenTelemetry poderá ser adicionada depois sem substituir o motor de replay.

Especificação completa em [SPEC.md](SPEC.md). Mais detalhes em [DECISIONS.md](DECISIONS.md). O plano de implementação por dia está em [PLAN.md](PLAN.md); as perguntas de entrevista estão em [INTERVIEW.md](INTERVIEW.md).

## Limitações e o que eu faria diferente

- **Este harness não prova que um agente é confiável em produção.** Apenas demonstra reprodutibilidade para uma execução capturada dentro do escopo suportado e comportamento determinístico da política definida de recuperação sob falhas controladas.
- O projeto suporta um agente, uma decisão inicial do LLM envolvendo ferramenta, uma chamada sequencial de ferramenta e três condições fixas de recuperação. Não cobre frameworks genéricos de agentes, recuperação por LLM em vários turnos, ferramentas paralelas ou serviços externos reais.
- Uma nova decisão de LLM após uma falha não tem resposta gravada; o harness a rejeita. Uma próxima versão poderia incluir caminhos alternativos registrados explicitamente, ainda diferenciando-os da amostragem estocástica de um LLM real.
- O gravador mascara **nomes de campos** comuns de segredos, mas não consegue remover de forma confiável segredos inseridos em texto livre de prompts. Use somente entradas sintéticas neste MVP; não forneça traces de produção contendo dados pessoais.
- O primeiro rascunho da especificação apontava para a sequência 2 em uma falha de exemplo. O trace real colocou uma decisão do agente na sequência 2 e a resposta da ferramenta na sequência 3. As fixtures foram corrigidas para a sequência 3, e a validação rejeita alvos incorretos em vez de aplicá-los silenciosamente.
- A medição de tempo compara execuções locais simuladas, não um LLM real. O replay pode ser mais lento que a gravação simples de um agente simulado por causa da validação e comparação. Esses tempos não devem ser generalizados para a latência de modelos hospedados.
- JSON não oferece concorrência, streaming, índices, compressão nem migração formal entre versões de trace. O trabalho adicional deveria priorizar compatibilidade de formato e mais cenários de falha, não um dashboard.
- A primeira validação de setup em clone limpo neste ambiente **falhou**: `make setup` não conseguiu baixar o requisito isolado `setuptools>=68` porque a resolução de DNS para o índice de pacotes falhou (restrição de rede). Portanto, o critério #1 é **FAIL neste ambiente**, embora `make demo` tenha sido executado separadamente e com sucesso no clone limpo, sem dependências adicionais. Isso não valida a instalação completa em outra máquina com acesso à internet.
- O lint com Ruff **NÃO FOI EXECUTADO** aqui porque Ruff não estava instalado e o índice de pacotes não estava acessível. A compilação sintática e o pytest passaram, mas não substituem uma verificação com Ruff.
- Nenhuma execução de CI remota foi verificada aqui. O badge informa intencionalmente apenas que o workflow está configurado; deverá ser substituído por um badge dinâmico após a publicação do repositório.

## Escopo e licença

Este é um **MVP de 14 dias**, com mocks locais e relatórios na CLI. Integração com produção, autenticação e interface elaborada estão fora do escopo de propósito. Licenciado sob MIT; consulte [LICENSE](LICENSE).
