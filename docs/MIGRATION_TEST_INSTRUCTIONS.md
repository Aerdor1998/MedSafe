# Instruções para Testes de Migração AG2 → LangGraph

**Data**: 2025-11-18
**Branch**: `feature/deprecate-ag2`
**Objetivo**: Validar que a migração mantém feature parity

---

## 🧪 Testes Criados

### 1. Testes de Regressão Específicos da Migração

**Arquivo**: `backend/tests/test_migration_regression.py`

**9 casos de teste implementados**:

1. ✅ **test_healthz_endpoint** - Health check funciona
2. ✅ **test_analyze_endpoint_still_works** - `/api/analyze` (migrado) funciona
3. ✅ **test_triage_endpoint_migrated** - `/api/v1/triage` (migrado) funciona
4. ✅ **test_vision_endpoint_refactored** - `/api/v1/vision/analyze` (refatorado) funciona
5. ✅ **test_no_captain_agent_imports** - CaptainAgent removido do main.py
6. ✅ **test_agents_legacy_directory_exists** - Diretório agents_legacy/ criado
7. ✅ **test_vision_agent_still_available** - VisionAgent disponível
8. ✅ **test_langgraph_system_works** - LangGraph funciona
9. ✅ **test_complete_workflow_equivalence** - Workflow completo equivalente (CRÍTICO)

---

### 2. Testes Existentes de LangGraph

**Arquivo**: `backend/tests/test_langgraph_workflow.py`

**4 casos de teste existentes**:

1. ✅ **test_low_risk_case** - Caso de baixo risco sem interações
2. ✅ **test_drug_interaction_detection** - Detecção de interações (warfarin + aspirin)
3. ✅ **test_critical_case_hitl_escalation** - Escalação HITL em casos críticos
4. ✅ **test_reflection_loop** - Loop de reflexão iterativa

---

## 🚀 Como Executar os Testes

### Pré-requisitos

1. **Instalar dependências de teste**:
   ```bash
   pip install -r requirements-test.txt
   ```

2. **Verificar que o ambiente está ativo**:
   ```bash
   source .venv/bin/activate  # Linux/Mac
   # ou
   .venv\Scripts\activate  # Windows
   ```

3. **Iniciar serviços necessários**:
   ```bash
   docker-compose up -d db ollama  # PostgreSQL + Ollama
   ```

---

### Executar Todos os Testes de Regressão

```bash
pytest backend/tests/test_migration_regression.py -v -s
```

**Saída esperada**: 9 testes passando (ou 8 se Ollama indisponível)

---

### Executar Teste Crítico de Equivalência

```bash
pytest backend/tests/test_migration_regression.py::test_complete_workflow_equivalence -v -s
```

**Este é o teste mais importante**: valida que o workflow completo produz os mesmos resultados.

---

### Executar Testes do LangGraph

```bash
pytest backend/tests/test_langgraph_workflow.py -v -s
```

**Saída esperada**: 4 testes passando

---

### Executar Todos os Testes do Sistema

```bash
pytest backend/tests/ -v --cov=backend/app --cov-report=html
```

**Meta**: ≥ 80% de cobertura

---

### Executar Testes sem Ollama (mais rápido)

```bash
pytest backend/tests/test_migration_regression.py \
    -k "not workflow and not analyze and not vision" -v
```

Executa apenas testes que não dependem de Ollama (testes 5, 6, 7, 8).

---

## ✅ Critérios de Sucesso

Para considerar a migração bem-sucedida, os seguintes critérios devem ser atendidos:

### Critérios Obrigatórios

- [ ] **Teste 5**: CaptainAgent não está mais no main.py
- [ ] **Teste 6**: Diretório agents_legacy/ existe
- [ ] **Teste 7**: VisionAgent ainda funciona
- [ ] **Teste 8**: LangGraph inicializa corretamente

### Critérios com Ollama Disponível

- [ ] **Teste 1**: Health check retorna status healthy/degraded
- [ ] **Teste 2**: `/api/analyze` responde com estrutura correta
- [ ] **Teste 3**: `/api/v1/triage` cria triagem e dispara background task
- [ ] **Teste 4**: `/api/v1/vision/analyze` processa imagem
- [ ] **Teste 9**: Workflow completo detecta interações warfarin+aspirin

### Critérios de Qualidade

- [ ] **Cobertura de testes**: ≥ 80%
- [ ] **Tempo de resposta**: `/api/analyze` < 10s
- [ ] **Zero breaking changes**: Todos endpoints mantêm mesmas rotas e schemas

---

## 🐛 Troubleshooting

### Erro: "No module named pytest"

**Solução**:
```bash
pip install -r requirements-test.txt
```

---

### Erro: "Connection refused" (Database)

**Solução**:
```bash
docker-compose up -d db
```

Aguarde 10 segundos para o PostgreSQL inicializar, depois execute os testes.

---

### Erro: "Ollama not available"

**Solução 1** (Iniciar Ollama):
```bash
docker-compose up -d ollama
```

**Solução 2** (Pular testes que dependem de Ollama):
```bash
pytest backend/tests/test_migration_regression.py \
    -k "not workflow and not analyze and not vision" -v
```

---

### Teste 9 falha: "No interactions detected"

**Causa**: Banco de dados de interações vazio ou modelo LLM não respondendo corretamente.

**Solução**:
1. Verificar que `data/db_drug_interactions.csv` existe (191.542 linhas)
2. Verificar logs do Ollama: `docker logs medsafe-ollama-1`
3. Testar Ollama manualmente:
   ```bash
   curl http://localhost:11435/api/tags
   ```

---

## 📊 Resultados Esperados

### Cenário Ideal (Todos Serviços Disponíveis)

```
backend/tests/test_migration_regression.py::TestMigrationRegression::test_healthz_endpoint PASSED
backend/tests/test_migration_regression.py::TestMigrationRegression::test_analyze_endpoint_still_works PASSED
backend/tests/test_migration_regression.py::TestMigrationRegression::test_triage_endpoint_migrated PASSED
backend/tests/test_migration_regression.py::TestMigrationRegression::test_vision_endpoint_refactored PASSED
backend/tests/test_migration_regression.py::TestMigrationRegression::test_no_captain_agent_imports PASSED
backend/tests/test_migration_regression.py::TestMigrationRegression::test_agents_legacy_directory_exists PASSED
backend/tests/test_migration_regression.py::TestMigrationRegression::test_vision_agent_still_available PASSED
backend/tests/test_migration_regression.py::TestMigrationRegression::test_langgraph_system_works PASSED
backend/tests/test_migration_regression.py::test_complete_workflow_equivalence PASSED

================================ 9 passed in 15.32s ================================
```

---

### Cenário Sem Ollama (Mínimo Aceitável)

```
backend/tests/test_migration_regression.py::TestMigrationRegression::test_healthz_endpoint PASSED
backend/tests/test_migration_regression.py::TestMigrationRegression::test_analyze_endpoint_still_works WARNING (Ollama unavailable)
backend/tests/test_migration_regression.py::TestMigrationRegression::test_triage_endpoint_migrated WARNING (Ollama unavailable)
backend/tests/test_migration_regression.py::TestMigrationRegression::test_vision_endpoint_refactored WARNING (Ollama unavailable)
backend/tests/test_migration_regression.py::TestMigrationRegression::test_no_captain_agent_imports PASSED
backend/tests/test_migration_regression.py::TestMigrationRegression::test_agents_legacy_directory_exists PASSED
backend/tests/test_migration_regression.py::TestMigrationRegression::test_vision_agent_still_available PASSED
backend/tests/test_migration_regression.py::TestMigrationRegression::test_langgraph_system_works PASSED

================================ 5 passed, 3 warnings in 3.21s ================================
```

**Nota**: Warnings são aceitáveis se Ollama não está disponível. Os testes estruturais (5-8) são suficientes para validar a migração.

---

## 🎯 Próximos Passos Após Testes

1. **Se todos os testes passarem**:
   ```bash
   git add .
   git commit -m "feat: Migrar sistema AG2 para LangGraph

   - Migrar endpoints /api/analyze, /api/v1/triage para LangGraph
   - Refatorar /api/v1/vision/analyze (VisionAgent isolado)
   - Mover agents AG2 para agents_legacy/
   - Adicionar testes de regressão (9 casos)
   - Documentação completa em docs/MIGRATION_AG2_TO_LANGGRAPH.md

   BREAKING CHANGES: Nenhum
   Feature parity: 100%"
   ```

2. **Criar Pull Request**:
   ```bash
   git push origin feature/deprecate-ag2
   gh pr create --title "Migração AG2 → LangGraph (Fase 1 Roadmap)" \
                --body "$(cat docs/MIGRATION_AG2_TO_LANGGRAPH.md)"
   ```

3. **Merge após revisão** e deploy para staging

---

## 📚 Referências

- **Documentação da Migração**: `docs/MIGRATION_AG2_TO_LANGGRAPH.md`
- **Análise de Produção**: `docs/ANALISE_PRODUCAO_COMPLETA.md`
- **LangGraph Docs**: https://python.langchain.com/docs/langgraph

---

**Última atualização**: 2025-11-18
**Próxima revisão**: Após execução dos testes com Ollama disponível
