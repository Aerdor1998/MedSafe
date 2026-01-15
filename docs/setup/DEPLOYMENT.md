# MedSafe - Guia de Deploy em Produção

## 📋 Checklist Pré-Deploy

### Segurança
- [ ] Alterar SECRET_KEY
- [ ] Configurar senha forte do PostgreSQL
- [ ] Ativar HTTPS/TLS
- [ ] Configurar CORS específico
- [ ] Remover DEBUG=True
- [ ] Configurar rate limiting
- [ ] Revisar logs sensíveis

### Infraestrutura
- [ ] PostgreSQL 15+ configurado
- [ ] Backup automático do banco
- [ ] Redis para cache (opcional)
- [ ] Nginx como reverse proxy
- [ ] Certificado SSL/TLS
- [ ] Monitoramento (Prometheus + Grafana)

### Aplicação
- [ ] Todos os testes passando
- [ ] Coverage > 80%
- [ ] Migrações do banco aplicadas
- [ ] Variáveis de ambiente configuradas
- [ ] Logs centralizados
- [ ] Health checks funcionando

## 🚀 Deploy Docker Compose

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: medsafe
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    restart: always

  api:
    build: .
    environment:
      PORT: 8050
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/medsafe
      OLLAMA_BASE_URL: http://ollama:11434/v1
      SECRET_KEY: ${SECRET_KEY}
      DEBUG: false
    depends_on:
      - db
      - ollama
    restart: always

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - /etc/letsencrypt:/etc/letsencrypt
    depends_on:
      - api
    restart: always

volumes:
  postgres_data:
  ollama_data:
```

## 🔧 Configuração Nginx

```nginx
# nginx.conf
upstream medsafe_backend {
    server api:8050;
}

server {
    listen 80;
    server_name medsafe.app www.medsafe.app;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name medsafe.app www.medsafe.app;

    ssl_certificate /etc/letsencrypt/live/medsafe.app/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/medsafe.app/privkey.pem;

    client_max_body_size 10M;

    location /api {
        proxy_pass http://medsafe_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
}
```

## ☁️ Deploy em Cloud

### AWS (EC2 + RDS)

```bash
# 1. Criar instância EC2
# t3.medium (2 vCPU, 4GB RAM) ou superior

# 2. Criar RDS PostgreSQL
# db.t3.micro (desenvolvimento) ou db.t3.small (produção)

# 3. Configurar Security Groups
# - 8050 (API)
# - 5432 (PostgreSQL - apenas VPC)
# - 80, 443 (HTTP/HTTPS)

# 4. Deploy
ssh ec2-user@your-instance
git clone https://github.com/Aerdor1998/MedSafe.git
cd MedSafe
docker-compose -f docker-compose.prod.yml up -d
```

### Hugging Face Spaces

```python
# app.py
import os
from backend.main import app

# Spaces automático usa porta 7860
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

### DigitalOcean App Platform

```yaml
# .do/app.yaml
name: medsafe
services:
  - name: api
    github:
      repo: Aerdor1998/MedSafe
      branch: main
    build_command: pip install -r requirements.txt
    run_command: uvicorn backend.main:app --host 0.0.0.0 --port 8050
    envs:
      - key: DATABASE_URL
        value: ${db.DATABASE_URL}
      - key: SECRET_KEY
        type: SECRET
    http_port: 8050

databases:
  - name: db
    engine: PG
    version: "15"
```

## 📊 Monitoramento

### Prometheus Metrics

```python
# backend/monitoring.py
from prometheus_client import Counter, Histogram, Gauge

# Contadores
analyses_total = Counter('medsafe_analyses_total', 'Total de análises')
contraindications_detected = Counter(
    'medsafe_contraindications_detected',
    'Contraindicações detectadas',
    ['severity']
)

# Histogramas (latência)
analysis_duration = Histogram(
    'medsafe_analysis_duration_seconds',
    'Duração da análise'
)

# Gauges (estado)
active_sessions = Gauge('medsafe_active_sessions', 'Sessões ativas')
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "MedSafe Monitoring",
    "panels": [
      {
        "title": "Análises por Hora",
        "targets": [
          {
            "expr": "rate(medsafe_analyses_total[1h])"
          }
        ]
      },
      {
        "title": "Tempo Médio de Análise",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, medsafe_analysis_duration_seconds)"
          }
        ]
      }
    ]
  }
}
```

## 🔄 CI/CD GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest backend/tests/ -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: |
          docker-compose -f docker-compose.prod.yml build
          docker-compose -f docker-compose.prod.yml up -d
```

## 🔐 Secrets Management

```bash
# Usar ferramentas como:
# - AWS Secrets Manager
# - HashiCorp Vault
# - GitHub Secrets (CI/CD)

# Nunca commitar:
# - .env
# - secrets.yaml
# - credentials.json
```

## 📈 Scaling

### Horizontal Scaling

```yaml
# docker-compose.scale.yml
services:
  api:
    deploy:
      replicas: 3
    scale: 3
```

### Load Balancer

```nginx
upstream medsafe_backend {
    least_conn;
    server api1:8050;
    server api2:8050;
    server api3:8050;
}
```

## 🆘 Troubleshooting

### Logs

```bash
# Ver logs da API
docker-compose logs -f api

# Ver logs do PostgreSQL
docker-compose logs -f db

# Logs do Nginx
docker-compose logs -f nginx
```

### Health Checks

```bash
# API Health
curl https://medsafe.app/api/health

# Database Health
docker exec medsafe-db pg_isready

# Ollama Health
curl http://localhost:11434/api/tags
```

## 📞 Suporte

Em caso de problemas:
1. Verificar logs
2. Testar health checks
3. Revisar variáveis de ambiente
4. Consultar documentação
5. Abrir issue no GitHub

---

**Mantido por**: Equipe MedSafe  
**Última atualização**: 01/10/2025
