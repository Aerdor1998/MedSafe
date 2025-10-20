#!/bin/bash
# MedSafe - Script de Backup Automático
# Executa backup do PostgreSQL e envia para S3/storage remoto

set -e

# Configurações
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="medsafe_backup_${TIMESTAMP}.sql"
RETENTION_DAYS=30

# Variáveis de ambiente
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-medsafe}"
DB_USER="${DB_USER:-medsafe}"
DB_PASSWORD="${DB_PASSWORD}"

# AWS S3 (opcional)
S3_BUCKET="${S3_BUCKET}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "🔄 Iniciando backup do banco de dados..."
echo "📅 Data: $(date)"
echo "🗄️  Banco: ${DB_NAME}@${DB_HOST}"

# Criar diretório de backup se não existir
mkdir -p "${BACKUP_DIR}"

# Executar backup
echo "💾 Executando pg_dump..."
PGPASSWORD="${DB_PASSWORD}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --format=custom \
    --compress=9 \
    --file="${BACKUP_DIR}/${BACKUP_FILE}"

# Verificar se backup foi criado
if [ -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
    echo "✅ Backup criado com sucesso: ${BACKUP_FILE} (${BACKUP_SIZE})"
else
    echo "❌ Erro ao criar backup"
    exit 1
fi

# Enviar para S3 (se configurado)
if [ -n "${S3_BUCKET}" ]; then
    echo "☁️  Enviando backup para S3..."
    aws s3 cp \
        "${BACKUP_DIR}/${BACKUP_FILE}" \
        "s3://${S3_BUCKET}/backups/${BACKUP_FILE}" \
        --region "${AWS_REGION}" \
        --storage-class GLACIER_IR
    
    if [ $? -eq 0 ]; then
        echo "✅ Backup enviado para S3 com sucesso"
    else
        echo "⚠️  Erro ao enviar backup para S3"
    fi
fi

# Limpar backups antigos
echo "🧹 Removendo backups com mais de ${RETENTION_DAYS} dias..."
find "${BACKUP_DIR}" -name "medsafe_backup_*.sql" -type f -mtime +${RETENTION_DAYS} -delete

# Listar backups existentes
echo "📋 Backups disponíveis:"
ls -lh "${BACKUP_DIR}"/medsafe_backup_*.sql 2>/dev/null | tail -5 || echo "Nenhum backup encontrado"

echo "✅ Backup concluído com sucesso!"
echo "📊 Resumo:"
echo "   - Arquivo: ${BACKUP_FILE}"
echo "   - Tamanho: ${BACKUP_SIZE}"
echo "   - Localização: ${BACKUP_DIR}"
if [ -n "${S3_BUCKET}" ]; then
    echo "   - S3: s3://${S3_BUCKET}/backups/${BACKUP_FILE}"
fi


