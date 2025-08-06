---
sdk: docker
title: MedSafe Demo
emoji: 💊
colorFrom: indigo
colorTo: blue
pinned: false
app_port: 7860
hardware: cpu-upgrade
---

# MedSafe - Sistema de Contra-indicativos de Medicamentos

Este é um demo interativo do MedSafe. 
A análise pode levar alguns instantes, pois os modelos de IA estão rodando em um ambiente compartilhado.

## Funcionalidades
- ✅ Anamnese digital interativa
- ✅ Reconhecimento de medicamentos por OCR em imagens
- ✅ Análise de interações medicamentosas
- ✅ Classificação de riscos baseada em normas OMS/ANVISA
- ✅ Processamento local com Ollama (qwen3:4b + qwen2.5vl:7b)
- ✅ Sistema de auditoria para farmacovigilância

## Tecnologias
- **Backend**: FastAPI + SQLite + OpenCV + Tesseract
- **Frontend**: HTML5 + Tailwind CSS + Three.js
- **IA**: Ollama (qwen3:4b + qwen2.5vl:7b) local
- **OCR**: IA de Visão + Tesseract (fallback)
