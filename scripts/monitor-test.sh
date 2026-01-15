#!/bin/bash
# Monitor de teste - Fenelzina + Ritalina
# Executar em terminal separado durante o teste

echo "🔍 Monitorando análise MedSafe..."
echo "=================================="
echo ""

docker logs medsafe_api -f --tail 50 | grep -E "(🔍|📊|🔴|🟡|🟢|⚠️|❌|✅|timestamps|interações|RISCO|ClinicalAgent|SafetyAgent|KeyError)" --color=always
