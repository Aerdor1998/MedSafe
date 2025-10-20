#!/bin/bash
# MedSafe - Script de Restore de Backup
# Restaura backup do PostgreSQL a partir de arquivo local ou S3

set -e

# Configurações
BACKUP_DIR="/backups"

# Variáveis de ambiente
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-medsafe}"
DB_USER="${DB_USER:-medsafe}"
DB_PASSWORD="${DB_PASSWORD}"

# Verificar argumento
if [ -z "$1" ]; then
    echo "❌ Erro: Nome do arquivo de backup não fornecido"
    echo "Uso: $0 <backup_file>"
    echo ""
    echo "Backups disponíveis:"
    ls -lh "${BACKUP_DIR}"/medsafe_backup_*.sql 2>/dev/null || echo "Nenhum backup encontrado"
    exit 1
fi

BACKUP_FILE="$1"

# Verificar se arquivo existe
if [ ! -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    echo "❌ Erro: Arquivo de backup não encontrado: ${BACKUP_DIR}/${BACKUP_FILE}"
    echo ""
    echo "Backups disponíveis:"
    ls -lh "${BACKUP_DIR}"/medsafe_backup_*.sql 2>/dev/null || echo "Nenhum backup encontrado"
    exit 1
fi

echo "⚠️  ATENÇÃO: Esta operação irá SOBRESCREVER o banco de dados atual!"
echo "📊 Banco: ${DB_NAME}@${DB_HOST}"
echo "📁 Backup: ${BACKUP_FILE}"
echo ""
read -p "Deseja continuar? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Operação cancelada pelo usuário"
    exit 0
fi

echo "🔄 Iniciando restore do banco de dados..."

# Criar backup de segurança antes do restore
SAFETY_BACKUP="medsafe_pre_restore_$(date +%Y%m%d_%H%M%S).sql"
echo "💾 Criando backup de segurança: ${SAFETY_BACKUP}"
PGPASSWORD="${DB_PASSWORD}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --format=custom \
    --compress=9 \
    --file="${BACKUP_DIR}/${SAFETY_BACKUP}"

echo "✅ Backup de segurança criado"

# Desconectar usuários ativos
echo "🔌 Desconectando usuários ativos..."
PGPASSWORD="${DB_PASSWORD}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" \
    > /dev/null 2>&1 || true

# Dropar banco de dados
echo "🗑️  Removendo banco de dados existente..."
PGPASSWORD="${DB_PASSWORD}" dropdb \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    --if-exists \
    "${DB_NAME}"

# Criar novo banco de dados
echo "🆕 Criando novo banco de dados..."
PGPASSWORD="${DB_PASSWORD}" createdb \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    "${DB_NAME}"

# Restaurar backup
echo "📥 Restaurando backup..."
PGPASSWORD="${DB_PASSWORD}" pg_restore \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-acl \
    "${BACKUP_DIR}/${BACKUP_FILE}"

# Verificar restore
echo "🔍 Verificando restore..."
TABLE_COUNT=$(PGPASSWORD="${DB_PASSWORD}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")

echo "✅ Restore concluído com sucesso!"
echo "📊 Resumo:"
echo "   - Banco: ${DB_NAME}"
echo "   - Tabelas: ${TABLE_COUNT}"
echo "   - Backup restaurado: ${BACKUP_FILE}"
echo "   - Backup de segurança: ${SAFETY_BACKUP}"


