# Guia de Deploy - MedSafe

**Data:** 2025-11-12
**Ambiente:** Production-Ready
**Infraestrutura:** Docker + AWS/GCP/Azure

---

## 📋 Pré-requisitos

### Hardware Mínimo Recomendado

```
CPU: 4 cores (8 recomendado)
RAM: 8 GB (16 GB recomendado)
Storage: 50 GB SSD (100 GB recomendado)
Network: 100 Mbps (1 Gbps recomendado)

PostgreSQL Server:
- CPU: 2 cores
- RAM: 16 GB (pgvector é memory-intensive)
- Storage: 100 GB SSD

Ollama Server (opcional, pode usar OpenAI):
- CPU: 4 cores
- RAM: 8 GB
- GPU: NVIDIA com 8GB+ VRAM (recomendado)
```

### Software Requerido

```bash
# Sistema Operacional
Ubuntu 22.04 LTS (recomendado)
ou
Debian 11+
ou
CentOS 8+

# Docker
Docker Engine 24.0+
Docker Compose 2.20+

# Certificado SSL/TLS
Let's Encrypt (certbot) ou certificado comercial

# Firewall
UFW ou iptables configurado
```

---

## 🔧 Configuração Inicial

### 1. Clonar Repositório

```bash
# Clonar projeto
git clone https://github.com/your-org/medsafe.git
cd medsafe

# Checkout da versão estável
git checkout tags/v1.0.0 -b production
```

### 2. Configurar Variáveis de Ambiente

```bash
# Copiar template
cp env.example .env.production

# Editar arquivo
nano .env.production
```

**`.env.production` (exemplo):**

```bash
# ======================
# APLICAÇÃO
# ======================
APP_NAME=MedSafe
APP_VERSION=1.0.0
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json

# ======================
# SEGURANÇA (CRITICAL!)
# ======================
# Gerar com: python -c 'import secrets; print(secrets.token_urlsafe(32))'
SECRET_KEY=CHANGE_ME_GENERATE_WITH_SECRETS_TOKEN_URLSAFE_32
JWT_SECRET=CHANGE_ME_GENERATE_WITH_SECRETS_TOKEN_URLSAFE_32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# ======================
# DATABASE
# ======================
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=medsafe
POSTGRES_USER=medsafe
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD_HERE

# ======================
# CORS & SECURITY
# ======================
ALLOWED_ORIGINS=https://medsafe.yourdomain.com,https://app.medsafe.yourdomain.com

# ======================
# OLLAMA (ou OpenAI)
# ======================
OLLAMA_HOST=http://ollama:11434
OLLAMA_LLM=qwen2.5:7b
OLLAMA_VLM=qwen2.5vl:7b

# Ou usar OpenAI
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4

# ======================
# APIS EXTERNAS
# ======================
ENABLE_RXNORM=true
RXNORM_BASE_URL=https://rxnav.nlm.nih.gov/REST

# ======================
# UPLOAD
# ======================
MAX_UPLOAD_SIZE=10485760  # 10MB
ALLOWED_EXTENSIONS=jpg,jpeg,png,pdf

# ======================
# OCR
# ======================
TESSERACT_CMD=/usr/bin/tesseract
OCR_LANG=por+eng

# ======================
# TELEMETRY
# ======================
ENABLE_METRICS=true
METRICS_PORT=9090

# ======================
# BACKUP
# ======================
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 2 * * *"  # 2 AM daily
BACKUP_RETENTION_DAYS=30
BACKUP_S3_BUCKET=medsafe-backups
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
```

### 3. Gerar Secrets

```bash
# Gerar SECRET_KEY
python3 -c 'import secrets; print(f"SECRET_KEY={secrets.token_urlsafe(32)}")'

# Gerar JWT_SECRET
python3 -c 'import secrets; print(f"JWT_SECRET={secrets.token_urlsafe(32)}")'

# Gerar senha forte para PostgreSQL
python3 -c 'import secrets; print(f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}")'
```

### 4. Configurar Docker Compose para Produção

**`docker-compose.prod.yml`:**

```yaml
version: '3.8'

services:
  # PostgreSQL com pgvector
  db:
    image: ankane/pgvector:latest
    container_name: medsafe_db_prod
    restart: always
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups  # Para backups
    ports:
      - "127.0.0.1:5432:5432"  # Não expor publicamente
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - medsafe_network

  # API Backend
  api:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        - ENVIRONMENT=production
    container_name: medsafe_api_prod
    restart: always
    env_file:
      - .env.production
    volumes:
      - ./data:/app/data:ro  # Read-only para segurança
      - ./logs:/app/logs
      - ./uploads:/app/uploads
    ports:
      - "127.0.0.1:9000:9000"  # Expor apenas localmente (nginx na frente)
    depends_on:
      db:
        condition: service_healthy
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - medsafe_network
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

  # Ollama (LLMs)
  ollama:
    image: ollama/ollama:latest
    container_name: medsafe_ollama_prod
    restart: always
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "127.0.0.1:11434:11434"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - medsafe_network
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
    # Se tiver GPU
    # runtime: nvidia
    # environment:
    #   - NVIDIA_VISIBLE_DEVICES=all

  # Nginx (Reverse Proxy)
  nginx:
    image: nginx:alpine
    container_name: medsafe_nginx_prod
    restart: always
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./frontend:/usr/share/nginx/html:ro
      - ./logs/nginx:/var/log/nginx
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
    networks:
      - medsafe_network

  # Prometheus (Monitoring)
  prometheus:
    image: prom/prometheus:latest
    container_name: medsafe_prometheus_prod
    restart: always
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "127.0.0.1:9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    networks:
      - medsafe_network

  # Grafana (Dashboards)
  grafana:
    image: grafana/grafana:latest
    container_name: medsafe_grafana_prod
    restart: always
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_SERVER_ROOT_URL=https://monitoring.yourdomain.com
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./grafana/datasources:/etc/grafana/provisioning/datasources:ro
    ports:
      - "127.0.0.1:3000:3000"
    depends_on:
      - prometheus
    networks:
      - medsafe_network

volumes:
  postgres_data:
    driver: local
  ollama_data:
    driver: local
  prometheus_data:
    driver: local
  grafana_data:
    driver: local

networks:
  medsafe_network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

---

## 🚀 Deploy

### 1. Build das Imagens

```bash
# Build da imagem de produção
docker-compose -f docker-compose.prod.yml build --no-cache

# Verificar imagens
docker images | grep medsafe
```

### 2. Iniciar Serviços

```bash
# Iniciar todos os serviços
docker-compose -f docker-compose.prod.yml up -d

# Verificar status
docker-compose -f docker-compose.prod.yml ps

# Ver logs
docker-compose -f docker-compose.prod.yml logs -f api
```

### 3. Inicializar Banco de Dados

```bash
# Executar migrações
docker-compose -f docker-compose.prod.yml exec api python -m alembic upgrade head

# Verificar conexão
docker-compose -f docker-compose.prod.yml exec api python -c "from backend.app.db.database import check_db_health; print(check_db_health())"
```

### 4. Baixar Modelos Ollama

```bash
# Entrar no container Ollama
docker-compose -f docker-compose.prod.yml exec ollama bash

# Baixar modelos
ollama pull qwen2.5:7b
ollama pull qwen2.5vl:7b

# Verificar
ollama list

# Sair
exit
```

### 5. Configurar Nginx

**`nginx/nginx.conf`:**

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript
               application/json application/javascript application/xml+rss;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=general_limit:10m rate=100r/m;

    # Upstream API
    upstream api_backend {
        server api:9000;
    }

    # HTTP -> HTTPS redirect
    server {
        listen 80;
        server_name medsafe.yourdomain.com;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$host$request_uri;
        }
    }

    # HTTPS Server
    server {
        listen 443 ssl http2;
        server_name medsafe.yourdomain.com;

        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Security Headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # Max upload size
        client_max_body_size 10M;

        # Frontend (Static)
        location / {
            root /usr/share/nginx/html;
            index index.html;
            try_files $uri $uri/ /index.html;
        }

        # API Endpoints
        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;

            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 120s;
        }

        # Health Check
        location /healthz {
            proxy_pass http://api_backend;
            access_log off;
        }

        # Metrics (protegido por IP)
        location /metrics {
            allow 10.0.0.0/8;
            deny all;
            proxy_pass http://api_backend;
        }
    }
}
```

### 6. Configurar SSL com Let's Encrypt

```bash
# Instalar certbot
sudo apt-get install certbot python3-certbot-nginx

# Obter certificado
sudo certbot --nginx -d medsafe.yourdomain.com

# Renovação automática (crontab)
sudo crontab -e
# Adicionar linha:
0 3 * * * certbot renew --quiet --post-hook "docker-compose -f /path/to/docker-compose.prod.yml restart nginx"
```

---

## 📊 Monitoramento

### Prometheus Configuration

**`prometheus/prometheus.yml`:**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'medsafe-api'
    static_configs:
      - targets: ['api:9000']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['db:5432']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Grafana Dashboards

1. **Acessar Grafana:** https://monitoring.yourdomain.com
2. **Login:** admin / [senha configurada]
3. **Importar Dashboard:**
   - Dashboard ID: 1860 (Node Exporter)
   - Dashboard ID: 9628 (PostgreSQL)
   - Custom: Criar dashboard para métricas MedSafe

---

## 🔄 Backup Automatizado

### Script de Backup

**`scripts/backup.sh`:**

```bash
#!/bin/bash

# Configuração
BACKUP_DIR="/backups"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="medsafe"
S3_BUCKET="medsafe-backups"

# Criar diretório de backup
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
echo "[$(date)] Iniciando backup do banco de dados..."
docker-compose -f docker-compose.prod.yml exec -T db \
    pg_dump -U medsafe medsafe | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Upload para S3
echo "[$(date)] Enviando para S3..."
aws s3 cp $BACKUP_DIR/db_backup_$DATE.sql.gz s3://$S3_BUCKET/

# Limpar backups antigos (local)
echo "[$(date)] Limpando backups antigos..."
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Limpar backups antigos (S3)
aws s3 ls s3://$S3_BUCKET/ | while read -r line; do
    createDate=$(echo $line | awk '{print $1" "$2}')
    createDate=$(date -d "$createDate" +%s)
    olderThan=$(date -d "$RETENTION_DAYS days ago" +%s)
    if [[ $createDate -lt $olderThan ]]; then
        fileName=$(echo $line | awk '{print $4}')
        aws s3 rm s3://$S3_BUCKET/$fileName
    fi
done

echo "[$(date)] Backup concluído!"
```

### Cron para Backup Diário

```bash
# Editar crontab
crontab -e

# Adicionar linha (2 AM todos os dias)
0 2 * * * /path/to/medsafe/scripts/backup.sh >> /var/log/medsafe-backup.log 2>&1
```

---

## 🔒 Hardening de Segurança

### 1. Firewall (UFW)

```bash
# Resetar UFW
sudo ufw --force reset

# Regras básicas
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Permitir SSH (ajustar porta se necessário)
sudo ufw allow 22/tcp

# Permitir HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Ativar
sudo ufw --force enable

# Status
sudo ufw status verbose
```

### 2. Fail2Ban

```bash
# Instalar
sudo apt-get install fail2ban

# Configurar
sudo nano /etc/fail2ban/jail.local
```

**`/etc/fail2ban/jail.local`:**

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true

[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled = true
logpath = /path/to/medsafe/logs/nginx/error.log
```

### 3. Audit Logging

```bash
# Instalar auditd
sudo apt-get install auditd

# Configurar regras
sudo nano /etc/audit/rules.d/medsafe.rules
```

**Regras:**

```bash
# Monitorar acesso a arquivos sensíveis
-w /path/to/medsafe/.env.production -p wa -k medsafe_config
-w /path/to/medsafe/data/ -p wa -k medsafe_data

# Monitorar execução de containers
-w /usr/bin/docker -p x -k docker_execution
```

---

## 📈 Escalabilidade

### Horizontal Scaling (Load Balancer)

```yaml
# docker-compose.prod.yml (com múltiplas APIs)
services:
  api_1:
    <<: *api-config
    container_name: medsafe_api_1

  api_2:
    <<: *api-config
    container_name: medsafe_api_2

  api_3:
    <<: *api-config
    container_name: medsafe_api_3

  nginx:
    # ...
    # Atualizar upstream no nginx.conf:
    # upstream api_backend {
    #     server api_1:9000;
    #     server api_2:9000;
    #     server api_3:9000;
    # }
```

### Kubernetes (Futuro)

```bash
# TODO: Criar Helm charts para deploy em Kubernetes
# - Deployments
# - Services
# - Ingress
# - ConfigMaps
# - Secrets
# - PersistentVolumeClaims
```

---

## 🚨 Troubleshooting

### Logs

```bash
# Logs da API
docker-compose -f docker-compose.prod.yml logs -f api

# Logs do Banco
docker-compose -f docker-compose.prod.yml logs -f db

# Logs do Nginx
tail -f logs/nginx/access.log
tail -f logs/nginx/error.log
```

### Problemas Comuns

#### 1. API não inicia

```bash
# Verificar variáveis de ambiente
docker-compose -f docker-compose.prod.yml exec api env | grep -E "SECRET|POSTGRES"

# Verificar conexão com banco
docker-compose -f docker-compose.prod.yml exec api python -c "from backend.app.db.database import check_db_health; print(check_db_health())"
```

#### 2. Banco de dados lento

```bash
# Entrar no PostgreSQL
docker-compose -f docker-compose.prod.yml exec db psql -U medsafe -d medsafe

# Verificar queries lentas
SELECT * FROM pg_stat_activity WHERE state = 'active';

# Criar índices se necessário
CREATE INDEX idx_triage_user_id ON triages(user_id);
CREATE INDEX idx_report_triage_id ON reports(triage_id);
```

#### 3. Memória insuficiente

```bash
# Verificar uso de memória
docker stats

# Ajustar limites no docker-compose.prod.yml
# deploy.resources.limits.memory
```

---

## ✅ Checklist de Deploy

### Pré-Deploy

- [ ] Todas as variáveis de ambiente configuradas
- [ ] Secrets gerados (SECRET_KEY, JWT_SECRET, passwords)
- [ ] Certificado SSL obtido
- [ ] Firewall configurado
- [ ] Backup automatizado configurado
- [ ] Monitoramento configurado (Prometheus/Grafana)
- [ ] Logs centralizados configurados
- [ ] Testes executados em staging
- [ ] Testes de carga executados
- [ ] Documentação atualizada

### Deploy

- [ ] Build das imagens
- [ ] Deploy dos containers
- [ ] Migrações de banco executadas
- [ ] Modelos Ollama baixados
- [ ] Health checks OK
- [ ] Nginx configurado e funcionando
- [ ] SSL/TLS funcionando
- [ ] Verificar logs (sem erros)

### Pós-Deploy

- [ ] Testar endpoints principais
- [ ] Verificar métricas (Prometheus)
- [ ] Configurar alertas
- [ ] Documentar runbooks
- [ ] Treinar equipe de suporte
- [ ] Comunicar stakeholders
- [ ] Monitorar por 24h

---

**Documento preparado por:** Claude Code (Anthropic)
**Data:** 2025-11-12
