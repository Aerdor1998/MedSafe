# MedSafe · revisão do go-live de 18/11/2026

**Decisão proposta:** avançar com homologação single-tenant e dados sintéticos. O aceite assistencial continua pendente. Base inspecionada: `0395246`. A revisão cobre a árvore Git, o checklist v2 e as referências abaixo. Configuração do cliente, contratos, hardware, plantão e evidência clínica exigem comprovação própria.

## Validação das premissas do texto

| Seção | Resultado e consequência |
|---|---|
| 1 · Produtos de referência | Bases curadas, evidência rastreável e revisão profissional são referências de desenho. Números de clientes e encontros citados não foram confirmados e não dimensionam este serviço. |
| 2 · Benchmarks clínicos | O artigo PMID 32371457 é uma revisão. Há dados primários históricos por internação e paciente-dia em Bates et al. O patamar de 85% integra a pontuação hospitalar do Leapfrog. Medir pedidos por prescritor no local. Taxas de override variam por ambiente, tipo e gravidade do alerta. Distinguir alertas apresentados, aceitos, dispensados justificadamente e perdidos pela triagem. |
| 3 · Disponibilidade e retenção | Para 30 dias de 24 h, os orçamentos de 99,9%, 99,95% e 99,99% são 43min12s, 21min36s e aproximadamente 4min19s. Definir o que conta como indisponibilidade clínica, inclusive análise sem inferência. RPO/RTO são objetivos propostos. Triagem, prontuário, laudo, auditoria e sessão precisam de políticas próprias. |
| 4 · Normas | Construir matriz de aplicabilidade por finalidade, alegação e país. Anvisa 657/751, princípios essenciais e análise de risco requerem avaliação do produto. Determinar classe de segurança IEC 62304 pela análise de perigos. ISO 13485/14971, IEC 82304-1/62366-1, ISO 27001/27799, ASVS e WCAG orientam trabalho e evidências distintas. Avaliar SBIS conforme escopo de prontuário. FDA, HIPAA, BAA e NIST SP 800-66 dependem do mercado e dos papéis. DECIDE-AI orienta relato de avaliação clínica inicial; verificar pertinência de TRIPOD+AI a modelos preditivos. |
| 5 · Dados e modelo | O CSV tem 191.541 registros, 1.701 nomes distintos e 191.135 pares ignorando ordem. A rotina de ingestão atribui a fonte “DrugBank CSV”. Falta comprovar aquisição, versão e permissão para distribuição e finalidade. DDInter e DrugBank têm condições próprias. Identificar pesos e digest do alias MedGemma local, examinar HAI-DEF, model card e validação independente. |
| 6 · Capacidade | Modelo A é hipótese candidata. 200 × 20–40 = 4.000–8.000 pedidos/dia; a 10–20%, 400–1.600 análises/dia. Se 15% chegam na hora de pico, são 60–240/h. Com média de serviço de 60s isso representa carga média de 1–4 slots ocupados, antes de folga e fila. Um p95 isolado não permite calcular a média. B e C alteram o denominador e precisam de tráfego medido. O perfil público do MedGemma informa 4B e 27B; confirmar o artefato antes de orçar “8B Q4”. Medir capacidade conjunta de LLM, VLM e embeddings. |
| 7 · Fases | Evidências e próximos marcos abaixo. |
| 8 · Gaps | Mapeamento G1–G26 abaixo. Consolidada a linha G15 duplicada. |
| 9 · Aceite | Testar 150/h sustentado e rajada de 240/h com mix representativo, registrar duração, erros, backlog e drenagem. Separar p95 de API, espera e execução. Reportar sensibilidade com intervalo de confiança por severidade, falsos negativos e denominadores. Auditar 100% de high e critical até a decisão humana, inclusive falhas e retomadas. Validar pertinência clínica dos overrides antes de adotar teto de 70%. |
| 10 · Prazos | 4–6 semanas e 6–12 meses são cenários de planejamento. Piloto assistencial com paciente real já exige avaliação de finalidade, autorização aplicável e governança antes do primeiro uso. |
| 11 · Decisão | Iniciar preparação técnica. Liberação clínica depende de evidências clínicas, direitos de uso, privacidade, restore, capacidade e responsáveis. Escala de 1.000 cadastros por si só não caracteriza piloto nem garante capacidade. |

**Carga humana e armazenamento.** No A, 40–320 revisões/dia a 2–5 min correspondem a 1h20–26h40 de trabalho líquido/dia. No extremo superior são 3,33 jornadas de oito horas antes de pausas, plantão ou picos. No B são 13h20–133h20/dia e no C, 6h40–66h40/dia. A seleção do LLM deve proteger casos desconhecidos e de alto risco mesmo acima de 20%. Medir sensibilidade também na população que o filtro dispensaria. Os 7,3–14,6 milhões em cinco anos são pedidos; medir bytes por pedido, índices, laudos, embeddings, WAL e backups antes de definir disco e particionamento.

## Fases e evidências para aceite

| Fase | Evidência disponível | Evidência pendente / responsável sugerido |
|---|---|---|
| 0 · Escopo | COMMERCIAL_READINESS.md define isolamento single-tenant | Produto e clínico registram unidade, público, local, finalidade, contingência, SLO e cobertura de revisão. |
| 1 · Regulatório e qualidade | Limitações comerciais documentadas | Responsável regulatório define enquadramento, requisitos aplicáveis, rastreabilidade, gestão de mudanças, riscos e evidência clínica. Privacidade confirma controlador, operadores e retenção por classe. |
| 2 · Segurança clínica | Grafo, agente HITL, testes de aprovação e golden sets | Farmácia valida fontes, severidades, cenários de falso negativo, caso sem cobertura e regras de encaminhamento. Exercitar interrupção, autorização de revisor, rejeição e retomada no ambiente-alvo. |
| 3 · Dados e terminologia | CSV versionado, metadado de origem no importador, campo RxNorm | Dono de dados comprova direitos de uso/distribuição, data de corte, atualização e aprovação clínica. Registrar hash de pesos, base e prompts. Testar FHIR e terminologias exigidos pelo cliente. |
| 4 · Segurança e privacidade | RBAC, preflight, rotação de senha, varredura e SBOM | Revisão privada do histórico Git relatado em COMMERCIAL_READINESS.md. Determinar se houve exposição real; avaliar obrigações e rotação com o controlador. Testar MFA, sessão, proxy, CSP, trilha de auditoria, criptografia, resposta a incidentes e contratos. |
| 5 · Continuidade | Gate Alembic, backup local, scripts de restore e runbook | Infra restaura cópia externa em banco isolado, mede perda/tempo de recuperação e ensaia falha de dependências e rollback. |
| 6 · Performance | Fila PostgreSQL com claim atômico e workers independentes | Medir espera, tokens/s, recursos e latência ponta a ponta em GPU-alvo; verificar jobs duplicados/órfãos com duas réplicas, restart e shutdown. Benchmark com OCR e solicitações curtas/longas. |
| 7 · Observabilidade | Prometheus, Grafana, dashboard HITL e smoke externo | SRE testa entrega de alerta, correlação sem dados clínicos em logs, espera por gravidade, saturação e SLO de 30 dias. |
| 8 · UX | Frontend, suíte Playwright e troca autenticada de senha | Produto testa tarefas com profissionais, acessibilidade e uso mobile. Validar justificativa de override, notificação e recuperação de acesso. |
| 9 · Release | CI, build, Trivy, SBOM e E2E condicionado a staging | Vincular imagem e modelo testados à release; exigir E2E, avaliação clínica, migração e restore no mesmo candidato. Assinatura e cobertura crítica exigem evidência. |
| 10 · Suporte | Cadastro administrativo e runbook | Operação comprova onboarding em lote, desligamento, recuperação de conta, responsáveis e tempos de resposta. |
| 11 · Ativação | Smoke verifica saúde, prontidão e autenticação | Operador e responsável clínico registram decisão e rollback. Acompanhar fila, erros, latência e casos sem revisor durante hypercare. |

## Gaps verificados na árvore

| ID | Evidência encontrada e decisão |
|---|---|
| G1 | Worker consome um job por vez. Claim PostgreSQL usa FOR UPDATE SKIP LOCKED; testar duas réplicas em banco real. |
| G2 | Nome fixo confirmado em Compose base e de produção. Removido nesta proposta. |
| G3 | env.prod.example exemplifica paralelismo 2. Conferir configuração efetiva no servidor Ollama e medir antes de alterar. |
| G4 | Dockerfile inicia Uvicorn sem workers explícitos. Dois processos no mesmo host ainda compartilham domínio de falha. |
| G5 | routers/vision.py aguarda leitura e análise na requisição. Medir e isolar trabalho pesado. |
| G6 | Claim ordenado por created_at. Definir risco disponível antes da inferência, desempate e limite de espera de baixa prioridade. |
| G7 | Cadastro admin a 5/h/IP confirmado. Criar via administrativa em lote auditada preservando proteção do endpoint. |
| G8 | Existe change-password autenticado. Recuperação de senha perdida e convite não demonstrados. |
| G9 | Prod usa pgvector v0.5.1 (PG15.4 segundo Compose); CI usa pg16. Testar major de produção e upgrade com dump/restore. |
| G10 | Compose referencia medgemma:latest. Registrar digest do modelo efetivamente servido. |
| G11 | frontend/index.html usa Tailwind CDN e persiste medsafe-auth em localStorage. A migração da sessão deve testar CSRF, CORS, logout e renovação. |
| G12 | E2E e smoke existem. Sua execução depende de evento e URL configurada. O smoke antigo aceitava estado degradado. Esta proposta o reprova. |
| G13 | Golden sets e runner já existem. Reter relatório por build com denominadores, versão e aprovação do responsável clínico. |
| G14 | Compose grava backups locais. Cópia externa e restore do operador carecem de comprovação. |
| G15 | nginx.conf limita por endereço remoto. Medir qual IP chega pelo caminho real; só confiar em cabeçalhos de proxies conhecidos. |
| G16 | Compose descreve Ollama nativo em WSL; perfil alternativo de GPU disponível. Host efetivo não inspecionado. |
| G17 | Topologia Compose de um host. Redundância externa e failover não demonstrados. |
| G18 | CSV rotulado DrugBank pelo importador. Comprovar licença inclusive para o arquivo já distribuído. SHA-256: 95d8399aa9c7479001f90400fbd91c6260cbfe517b22d5153a2b031f39b11328. |
| G19 | HAI-DEF e model card exigem análise de uso pretendido e verificação independente. Alias local não identifica suficientemente o modelo. |
| G20 | config.py especifica cinco anos para triagens e laudos; worker prevê anonimização/soft delete conforme a tabela. Classificar registros e origem do prazo antes de ativar retenção sobre dados reais. |
| G21 | Testes técnicos e golden set presentes. Estudo clínico independente no público-alvo e aprovação documentada não demonstrados. |
| G22 | Há configuração RxNorm e campo rxnorm_cui. Integração FHIR e mapeamento terminológico ponta a ponta não demonstrados. |
| G23 | Há registro de auditoria e revisões. Verificar proteção contra alteração, assinatura e requisitos da finalidade contratada. |
| G24 | Projeto reconhece pendências operacionais. Solicitar documentação do controlador, processo de incidentes, base legal e análise de impacto aplicável. Prazo geral da ANPD para incidentes com risco ou dano relevante: três dias úteis, consideradas as regras aplicáveis. |
| G25 | E2E automatizado cobre fluxos técnicos. Teste de usabilidade com profissionais e registro de erros críticos pendentes. |
| G26 | Build gera SBOM. Verificar divulgação coordenada, triagem de relatos e pós-mercado conforme jurisdição. |

## Próximo ensaio de homologação

Usar instalação isolada, modelo identificado e casos sintéticos. Executar o preflight e o procedimento em [RUNBOOK.md](RUNBOOK.md). Subir duas réplicas pelo nome de serviço do Compose. Registrar versão da imagem, estado final de migrate, workers, /readyz, /healthz, duração do job e auditoria de decisão HITL. Repetir com falha de inferência, reinício de worker e restore. Resultado ainda pendente em ambiente real.

## Referências de decisão

- [Anvisa · Manual de regularização de equipamentos](https://www.gov.br/anvisa/pt-br/centraisdeconteudo/publicacoes/produtos-para-a-saude/manuais/manual-regularizacao-gquip)
- [ANPD · Comunicação de incidente](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis)
- [Lei 13.787/2018, art. 6º](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13787.htm)
- [DrugBank · termos de acesso a datasets](https://go.drugbank.com/datasets) e [DDInter · termos](https://ddinter2.scbdd.com/terms/)
- [Google · MedGemma model card](https://developers.google.com/health-ai-developer-foundations/medgemma/model-card)
- [Bates et al. · CPOE](https://pmc.ncbi.nlm.nih.gov/articles/PMC61372/) e [Leapfrog · pontuação 2026](https://www.leapfroggroup.org/sites/default/files/Files/2026%20HospitalSurveyScoringAlgorithm%20Final.pdf)
- [DECIDE-AI](https://www.bmj.com/content/377/bmj-2022-070904) e [estudo de overrides em internação](https://pubmed.ncbi.nlm.nih.gov/29092059/)
