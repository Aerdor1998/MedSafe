# 🚀 Como Usar o MedSafe - Guia Rápido

## ⚡ Início Rápido (Recomendado)

### Iniciar Tudo Automaticamente
```bash
cd /home/lucasmsilva/Documentos/Cursor/MedSafe
./start.sh
```

Isso vai:
- ✅ Iniciar PostgreSQL
- ✅ Ativar ambiente Python
- ✅ Iniciar servidor FastAPI
- ✅ Verificar que tudo está funcionando

### Parar Tudo
```bash
./stop.sh
```

### Ver Status
```bash
./status.sh
```

---

## 🎯 Acessar a Aplicação

Após rodar `./start.sh`, acesse:

- **Interface Principal:** http://localhost:8000
- **Documentação API:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## 🧪 Testar Análise de Medicamento

1. Acesse http://localhost:8000
2. Preencha os dados:
   - **Idade:** 45
   - **Gênero:** Masculino
   - **Peso:** 70 kg (opcional)
3. Digite um medicamento: "Metformina"
4. Clique em **"Analisar Medicamento"**
5. Aguarde ~2 segundos
6. ✅ Resultado aparece!

---

## 📊 Comandos Úteis

### Ver Logs em Tempo Real
```bash
tail -f /tmp/medsafe.log
```

### Reiniciar Apenas o Backend
```bash
pkill -f uvicorn
cd /home/lucasmsilva/Documentos/Cursor/MedSafe
source .venv/bin/activate
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Acessar Banco de Dados
```bash
docker exec -it medsafe-postgres psql -U medsafe -d medsafe
```

Comandos SQL úteis:
```sql
\dt                          -- Listar tabelas
SELECT COUNT(*) FROM triage; -- Contar triagens
SELECT * FROM triage LIMIT 5; -- Ver últimas triagens
\q                           -- Sair
```

### Ver Logs do PostgreSQL
```bash
docker logs medsafe-postgres --tail 50
```

---

## 🛠️ Resolução de Problemas

### Problema: "Port 8000 already in use"
```bash
# Matar processo na porta 8000
kill -9 $(lsof -ti:8000)

# Reiniciar
./start.sh
```

### Problema: "Cannot connect to PostgreSQL"
```bash
# Reiniciar PostgreSQL
docker restart medsafe-postgres

# Aguardar 5 segundos
sleep 5

# Reiniciar aplicação
./start.sh
```

### Problema: Página em branco ao acessar localhost:8000
```bash
# Limpar cache do navegador
Ctrl + Shift + R (no navegador)

# Ou verificar logs
tail -f /tmp/medsafe.log
```

### Problema: "Erro ao analisar medicamento"
```bash
# Verificar se API está respondendo
curl http://localhost:8000/healthz

# Verificar logs
tail -50 /tmp/medsafe.log

# Reiniciar se necessário
./stop.sh
./start.sh
```

---

## 📁 Estrutura de Arquivos

```
MedSafe/
├── start.sh          ← Iniciar tudo automaticamente
├── stop.sh           ← Parar tudo
├── status.sh         ← Ver status dos serviços
├── COMO_USAR.md      ← Este arquivo
├── START_MEDSAFE.md  ← Guia detalhado
├── backend/          ← Código do backend
├── frontend/         ← Interface web
└── .env              ← Configurações (não commitar!)
```

---

## 🔒 Segurança

**⚠️ IMPORTANTE:** Não compartilhe o arquivo `.env` - ele contém senhas!

---

## 📞 Suporte

Se nada funcionar:

1. **Ver logs:** `tail -100 /tmp/medsafe.log`
2. **Limpar tudo e reiniciar:**
   ```bash
   ./stop.sh
   docker restart medsafe-postgres
   sleep 5
   ./start.sh
   ```
3. **Verificar status:** `./status.sh`

---

## ✅ Checklist de Funcionamento

Ao rodar `./status.sh`, você deve ver:

- ✅ PostgreSQL: Rodando
- ✅ FastAPI: Rodando  
- ✅ Frontend: Acessível
- ✅ API Docs: Disponível

Se todos estiverem ✅, está tudo funcionando!

---

## 🎉 Pronto!

A aplicação está pronta para uso. Bons testes! 🚀

