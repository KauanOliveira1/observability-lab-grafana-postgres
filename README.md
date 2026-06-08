# Grafana PostgreSQL Observability Lab

Laboratorio local de observabilidade para portfolio tecnico usando Grafana OSS,
PostgreSQL, Python e Docker Compose.

O projeto simula eventos coerentes de um marketplace, grava tudo em
`observability.app_events` e usa o Grafana para responder perguntas de
operacao e negocio com dados reais.

## Arquitetura

Fluxo principal:

```text
Python simulator -> PostgreSQL -> Grafana dashboard
```

Servicos:

- `postgres`: inicializa banco, schema e tabela automaticamente
- `simulator`: gera eventos continuamente em batch com retry de conexao
- `grafana`: provisiona datasource e dashboard por arquivos versionados

## Estrutura

```text
.
├── .env.example
├── docker-compose.yml
├── postgres/
│   └── init.sql
├── simulator/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── generate_events.py
├── grafana/
│   ├── dashboards/
│   │   └── application-observability-overview.json
│   └── provisioning/
│       ├── dashboards/
│       │   └── dashboards.yml
│       └── datasources/
│           └── postgres.yml
└── docs/
    └── screenshots/
```

## Como executar

O repositorio foi preparado para funcionar automaticamente logo apos o clone.

- Nao precisa criar banco manualmente
- Nao precisa criar schema manualmente
- Nao precisa criar datasource manualmente no Grafana
- Nao precisa importar dashboard manualmente
- Nao precisa rodar script Python fora do Docker

Os valores padrao ja permitem subir o ambiente sem criar `.env`.

Se quiser explicitar as variaveis locais, voce pode copiar `.env.example` para
`.env`, mas isso e opcional para a execucao padrao do portfolio.

```bash
cp .env.example .env
```

No Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

```bash
docker compose up -d --build
```

Para acompanhar o estado:

```bash
docker compose ps
```

Fluxo esperado apos subir os containers:

1. O PostgreSQL cria o schema `observability` e a tabela `app_events`
2. O simulator aguarda o banco ficar saudavel e inicia a ingestao continua
3. O Grafana sobe em `http://localhost:3000`
4. O datasource `PostgreSQL Observability` aparece provisionado
5. O dashboard `Application Observability Overview` aparece carregado

Tempo esperado para a primeira visualizacao util:

- em segundos: containers criados
- em ~1 minuto: banco saudavel e simulator escrevendo eventos
- em poucos minutos: dashboard com volume suficiente para leitura confortavel

## Acesso

- URL: `http://localhost:3000`
- Login padrao: `admin`
- Senha padrao: `admin`
- Dashboard principal: `http://localhost:3000/d/application-observability-overview/application-observability-overview`

## Fluxo completo para quem clonar o repo

1. Clonar o repositorio
2. Garantir que as portas `3000` e `5432` estejam livres
3. Rodar `docker compose up -d --build`
4. Confirmar com `docker compose ps` que `obs-postgres`, `obs-simulator` e
   `obs-grafana` estao ativos
5. Validar a tabela `observability.app_events`
6. Abrir `http://localhost:3000`
7. Entrar com `admin/admin`
8. Ver o datasource `PostgreSQL Observability` ja configurado
9. Abrir `Application Observability Overview`
10. Confirmar que os paineis estao sendo alimentados por dados reais

## Validacoes rapidas

Verificar schema e tabela:

```bash
docker compose exec postgres psql -U grafana -d observability -c "\dn+"
docker compose exec postgres psql -U grafana -d observability -c "\d observability.app_events"
```

Verificar ingestao:

```bash
docker compose exec postgres psql -U grafana -d observability -c "SELECT count(*) FROM observability.app_events;"
docker compose exec postgres psql -U grafana -d observability -c "SELECT event_time, event_type, endpoint, status_code, latency_ms, value, city, device FROM observability.app_events ORDER BY event_time DESC LIMIT 10;"
docker compose exec postgres psql -U grafana -d observability -c "SELECT event_type, count(*) FROM observability.app_events GROUP BY event_type ORDER BY count(*) DESC;"
```

Verificar que o Grafana respondeu:

```bash
curl http://localhost:3000/api/health
```

Resposta esperada aproximada:

```json
{"database":"ok","version":"..."}
```

Validar datasource e dashboard provisionados via API:

```bash
curl -u admin:admin http://localhost:3000/api/datasources/uid/postgres_app
curl -u admin:admin http://localhost:3000/api/dashboards/uid/application-observability-overview
```

## Modelo de dados

Tabela principal: `observability.app_events`

Campos:

- `event_time`
- `service_name`
- `endpoint`
- `status_code`
- `latency_ms`
- `event_type`
- `user_id`
- `value`
- `city`
- `device`

Indices:

- `event_time`
- `endpoint, event_time`
- `event_type, event_time`

## Eventos simulados

Tipos gerados:

- `page_view`
- `search`
- `listing_view`
- `contact_click`
- `listing_created`
- `payment_attempt`

Regras de coerencia:

- `search` e `listing_view` aparecem com volume alto
- `contact_click` e `listing_created` aparecem menos e sugerem avancos no funil
- `/payment/checkout` concentra a maior chance de erros 5xx
- eventos 5xx recebem latencia maior para evidenciar degradacao operacional
- eventos com valor monetario aparecem principalmente em criacao de anuncio e tentativa de pagamento

## Dashboard principal

Arquivo versionado:

- `grafana/dashboards/application-observability-overview.json`

Paineis:

1. Eventos por minuto
2. Taxa de erro 5xx
3. Latencia media
4. Latencia p95 por minuto
5. Eventos por tipo
6. Search x Contact Click
7. Top endpoints mais lentos
8. Taxa de erro por endpoint

Todas as queries do dashboard usam macros do Grafana para PostgreSQL,
especialmente `$__timeFilter(event_time)` e `$__timeGroupAlias(event_time, '1m')`.

## Como interpretar as metricas

- **Eventos por minuto**: mostra o ritmo geral da aplicacao simulada
- **Taxa de erro 5xx**: destaca degradacao tecnica, principalmente em pagamento
- **Latencia media**: mostra a saude geral das respostas
- **Latencia p95**: ajuda a ver caudas de lentidao que a media esconde
- **Eventos por tipo**: mostra frequencia relativa do comportamento do usuario
- **Search x Contact Click**: compara interesse com intencao de contato
- **Top endpoints mais lentos**: prioriza gargalos tecnicos
- **Taxa de erro por endpoint**: ajuda a localizar onde falhas se concentram

## O que prova que esta automatico

Ao fazer `docker compose down -v` e depois `docker compose up -d --build`, o
fluxo volta inteiro automaticamente:

- o container `postgres` recria banco e objetos a partir de `postgres/init.sql`
- o container `simulator` espera o healthcheck do banco e volta a inserir eventos
- o container `grafana` reaplica provisioning do datasource e do dashboard
- o dashboard volta a apontar para o PostgreSQL sem cliques manuais

Em outras palavras: tabelas, fluxo de dados e observabilidade sobem juntos a
partir dos arquivos versionados do repositorio.

## Reset do ambiente

```bash
docker compose down -v
```

Esse comando remove containers e volumes nomeados para recomecar do zero.

Depois disso, basta subir de novo:

```bash
docker compose up -d --build
```

## Troubleshooting

- **Porta 3000 ocupada**: pare o processo local que estiver usando a porta
  antes de subir o Grafana
- **Porta 5432 ocupada**: pare outro PostgreSQL local ou altere `POSTGRES_PORT`
- **Grafana abriu mas sem dados**: aguarde 1-3 minutos e rode a query de contagem
  no PostgreSQL para confirmar que o simulator ja esta escrevendo
- **Mudou credenciais do banco**: se usar `.env`, o provisioning do Grafana usa
  as mesmas variaveis do Compose, entao o datasource continua alinhado
- **Quero recomecar do zero**: use `docker compose down -v`

## Versionamento obrigatorio

- Datasource do Grafana via provisioning
- Dashboard salvo como JSON no repositorio
- Schema SQL versionado
- Gerador Python versionado
- Documentacao atualizada junto com mudancas de arquitetura e metricas
