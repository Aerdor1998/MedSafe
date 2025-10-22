# 🔐 ALERTA DE SEGURANÇA - AÇÃO IMEDIATA NECESSÁRIA

## ⚠️ CREDENCIAIS EXPOSTAS NO HISTÓRICO GIT

### Problema Identificado

Foi detectada a presença de credenciais hardcoded no arquivo `backend/scripts/import_csv_interactions.py` que foram commitadas ao repositório Git.

**Credenciais expostas:**
- Password: `medsafe123`
- Database: `medsafe`
- User: `medsafe`
- Host: `localhost`

**Commits afetados:**
- Primeiro commit: `518924f`
- Commits posteriores que modificaram o arquivo

### Status Atual

✅ **CORRIGIDO**: O arquivo foi reescrito para usar variáveis de ambiente
⚠️ **ATENÇÃO**: As credenciais ainda estão no histórico do Git

### Ações Necessárias

#### 1. ROTAÇÃO IMEDIATA DE CREDENCIAIS (OBRIGATÓRIO)

Se as credenciais expostas são usadas em ambientes de produção, desenvolvimento ou staging:

```sql
-- Conectar ao PostgreSQL como superuser
psql -U postgres

-- Alterar senha do usuário medsafe
ALTER USER medsafe WITH PASSWORD 'nova_senha_segura_aqui';

-- Verificar
\du medsafe
```

Gere uma senha segura:
```bash
# Gerar senha de 32 caracteres
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### 2. ATUALIZAR VARIÁVEIS DE AMBIENTE

Atualize todos os arquivos `.env` e configurações:

```bash
# .env (NÃO COMMITAR)
POSTGRES_USER=medsafe
POSTGRES_PASSWORD=nova_senha_segura_aqui
POSTGRES_DB=medsafe
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

#### 3. LIMPAR HISTÓRICO GIT (OPCIONAL - REQUER COORDENAÇÃO)

⚠️ **ATENÇÃO**: Isso reescreve o histórico do Git e pode causar problemas para colaboradores.

**Opção A: Usando BFG Repo-Cleaner (Recomendado)**

```bash
# Baixar BFG
wget https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar

# Clonar mirror do repositório
git clone --mirror https://github.com/Aerdor1998/MedSafe.git

# Remover credenciais do histórico
java -jar bfg-1.14.0.jar --replace-text passwords.txt MedSafe.git

# passwords.txt deve conter:
# medsafe123

# Push forçado (⚠️ CUIDADO!)
cd MedSafe.git
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push --force
```

**Opção B: Usando git-filter-repo (Alternativa)**

```bash
# Instalar git-filter-repo
pip install git-filter-repo

# Clonar repositório fresco
git clone https://github.com/Aerdor1998/MedSafe.git
cd MedSafe

# Remover arquivo do histórico
git filter-repo --path backend/scripts/import_csv_interactions.py --invert-paths

# Force push
git push origin --force --all
```

**⚠️ IMPORTANTE**: Após reescrever o histórico:
1. Todos os colaboradores devem re-clonar o repositório
2. PRs abertos precisarão ser recriados
3. Forks estarão desatualizados

#### 4. VERIFICAR LOGS DE ACESSO

Se as credenciais foram usadas em produção, verifique:

```bash
# PostgreSQL logs
tail -f /var/log/postgresql/postgresql-*.log

# Verificar conexões recentes
psql -U postgres -c "SELECT * FROM pg_stat_activity WHERE usename = 'medsafe';"

# Verificar logins suspeitos
grep "authentication failed" /var/log/postgresql/*.log
```

#### 5. IMPLEMENTAR VAULT (RECOMENDADO PARA PRODUÇÃO)

Para ambientes de produção, considere usar HashiCorp Vault:

```bash
# Instalar Vault
brew install vault  # macOS
# ou
apt install vault   # Ubuntu

# Iniciar Vault
vault server -dev

# Armazenar secrets
vault kv put secret/medsafe \
  postgres_user=medsafe \
  postgres_password=senha_super_secreta

# Acessar no código
# Usar biblioteca hvac para Python
```

### Checklist de Segurança

- [ ] Senha do banco de dados rotacionada
- [ ] Variáveis de ambiente atualizadas em todos os ambientes
- [ ] `.env` adicionado ao `.gitignore` (✅ já feito)
- [ ] Histórico do Git limpo (opcional)
- [ ] Logs de acesso verificados
- [ ] Equipe notificada sobre mudança de credenciais
- [ ] Documentação atualizada
- [ ] Secrets manager implementado (para produção)

### Prevenção Futura

✅ **Implementado**:
- Arquivo `.env.example` criado como template
- Script reescrito para usar variáveis de ambiente
- CSRF middleware implementado
- Validação de credenciais no código

🔜 **Recomendações**:
- Implementar pre-commit hooks para detectar secrets
- Usar ferramentas como `git-secrets` ou `trufflehog`
- Configurar GitHub Secret Scanning
- Implementar Vault para produção

### Ferramentas de Detecção de Secrets

```bash
# Instalar git-secrets
brew install git-secrets  # macOS
# ou
git clone https://github.com/awslabs/git-secrets
cd git-secrets && make install

# Configurar
git secrets --install
git secrets --register-aws

# Escanear repositório
git secrets --scan-history
```

### Contato

Para questões relacionadas a esta vulnerabilidade:
- Abrir issue privada no GitHub (Settings > Security > Report a vulnerability)
- Contatar mantenedores diretamente

---

**Data do alerta**: 2025-10-22
**Severidade**: 🔴 CRÍTICA
**Status**: ⚠️ Correção parcial implementada - Rotação de credenciais necessária

**Gerado automaticamente por Claude Code**
