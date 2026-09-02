# MedSafe — pacote comercial e limites de lançamento

## Oferta suportada agora

O formato seguro para comercializar esta versão é **single-tenant**: uma stack e um
banco isolados por cliente, operados pelo fornecedor como serviço gerenciado ou
entregues como appliance self-hosted. O frontend e a API podem ser publicados sob a
marca do cliente, com domínio, identidade visual e termos próprios.

Não vender esta versão como SaaS multi-tenant compartilhado. As tabelas clínicas não
têm `tenant_id`, isolamento por linha ou administração por organização. Compartilhar a
mesma instância entre empresas criaria risco de acesso cruzado. Multi-tenancy exige uma
fase arquitetural própria, migração de dados e testes de isolamento.

## O que o pacote entrega

- API e frontend no mesmo artefato Docker, com execução não-root e dependências
  congeladas em `requirements.lock`.
- PostgreSQL/pgvector, Redis, workers duráveis, migrações Alembic como gate de startup,
  backup local, retenção, métricas, dashboards e alertas.
- Autenticação JWT, RBAC, criação de usuários com papéis clínicos e rotação autenticada
  da senha bootstrap.
- Revisão humana: `pharmacist`, `physician` e `admin` podem aprovar ou rejeitar HITL.
- Métricas protegidas por Docker secret, portas de infraestrutura em loopback e
  verificações de segurança bloqueantes no CI.
- Runbook de deploy, restore, rollback, health checks e gate clínico.

## O que ainda depende do comprador/operador

Código pronto não equivale a lançamento autorizado. Antes de usar dados reais, cada
implantação precisa fornecer e validar:

- domínio, DNS/TLS, secrets, webhook de alerta, Sentry/GlitchTip e cópia de backup
  off-site;
- responsável por privacidade, base legal, avisos/termos, processo de incidente,
  atendimento a titulares e contrato de tratamento de dados;
- avaliação jurídica e regulatória da classificação e das alegações comerciais no
  país e no caso de uso escolhidos;
- validação clínica independente, critérios de aceitação, supervisão profissional e
  procedimento para falha/indisponibilidade do modelo;
- licenças e termos dos modelos, bases de dados, imagens e demais ativos distribuídos
  com a oferta; a licença do repositório não substitui a licença de cada dependência;
- SLO, plantão, suporte, capacidade/GPU, teste de carga, RPO/RTO e restore documentado.

Um SQLite de desenvolvimento que continha uma triagem e um relatório foi removido da
árvore atual. Antes de tornar o repositório público ou entregá-lo a terceiros, saneie
também o **histórico Git** em um clone controlado e revise os commits antigos com uma
ferramenta de detecção de secrets/dados. Reescrever histórico é uma operação coordenada
e não faz parte do build automático.

## Posicionamento comercial permitido

Apresentar o MedSafe como ferramenta de **apoio à triagem e revisão de segurança de
medicamentos**, com evidências, regras determinísticas e decisão humana. Não prometer
diagnóstico, prescrição autônoma, ausência de erro, conformidade automática ou
certificação regulatória que não tenha sido formalmente obtida.

## Sequência de onboarding por cliente

1. Criar uma implantação e banco exclusivos para o cliente.
2. Preencher `.env`, criar os dois secrets em arquivo e executar
   `python scripts/preflight_prod.py --first-deploy --vercel`.
3. Executar `docker compose -f docker-compose.prod.yml up -d`; confirmar `migrate`
   concluído, `/readyz` e `/healthz`.
4. Rotacionar o admin bootstrap, criar usuários e atribuir o menor papel necessário.
5. Rodar gate clínico e fluxo ponta a ponta com dados sintéticos.
6. Executar e registrar restore drill; configurar cópia off-site e alerta testado.
7. Assinar aceite técnico/clínico e só então habilitar dados reais.

## Critério de aceite da build

Uma release comercial deve ter, no mesmo commit:

- CI verde, `pip-audit` e Bandit sem achados bloqueantes;
- suíte unitária/integrada, Playwright contra staging e gate clínico aprovados;
- imagem construída e examinada pelo Trivy;
- migração de um banco vazio e de uma cópia representativa testadas;
- placeholders removidos, preflight verde e rollback ensaiado.

O runbook operacional canônico é `docs/RUNBOOK.md`.
