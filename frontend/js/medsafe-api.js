/**
 * MedSafe API Client
 * Conecta o frontend ao backend real
 *
 * Endpoints utilizados:
 * - POST /api/v2/analyze - Inicia análise (async)
 * - GET /api/v2/status/{session_id} - Polling de status/resultado
 * - GET /healthz - Health check
 * - GET /api/v2/health - Status detalhado
 */

class MedSafeAPI {
    constructor() {
        // Detectar URL da API baseada no ambiente
        this.apiUrl = this.detectApiUrl();
        this.sessionId = null;
        this.analysisResult = null;

        console.log('MedSafeAPI initialized with URL:', this.apiUrl);
    }

    detectApiUrl() {
        // Hugging Face Space
        if (window.location.hostname.includes('hf.space')) {
            return 'https://medsafe-mvp.hf.space';
        }
        // Produção com Nginx
        if (window.location.protocol === 'https:') {
            return window.location.origin;
        }
        // Desenvolvimento local
        return 'http://localhost:9001';
    }

    /**
     * Verifica se a API está online
     */
    async checkHealth() {
        try {
            const response = await fetch(`${this.apiUrl}/healthz`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            });

            if (!response.ok) throw new Error('API offline');

            const data = await response.json();

            // Tentar obter info detalhada do v2
            try {
                const v2Response = await fetch(`${this.apiUrl}/api/v2/health`);
                if (v2Response.ok) {
                    const v2Data = await v2Response.json();
                    return {
                        online: true,
                        model: v2Data.model || 'Desconhecido',
                        features: v2Data.features || {},
                        version: data.version || '2.0.0'
                    };
                }
            } catch (e) {
                console.log('v2 health não disponível');
            }

            return {
                online: true,
                model: data.ollama_model || 'Desconhecido',
                version: data.version || '2.0.0'
            };
        } catch (error) {
            console.error('Health check failed:', error);
            return { online: false, error: error.message };
        }
    }

    /**
     * Analisa medicamentos usando a API
     * @param {Object} patientData - Dados do paciente
     * @param {string} medicationText - Nome do medicamento
     * @param {File} imageFile - Arquivo de imagem (opcional)
     * @returns {Promise<Object>} - Resultado da análise
     */
    async analyzeMedication(patientData, medicationText, imageFile = null) {
        console.log('Initiating analysis...');
        // LGPD: avoid logging raw patient data / medication text in browser console
        if (imageFile) {
            // v2 analysis no longer accepts image here; run OCR separately via /api/v2/vision/analyze.
            console.warn('imageFile ignored in v2 analyzeMedication; use /api/v2/vision/analyze');
        }

        // Converter dados do paciente para o formato esperado pela API v2
        const apiPatientData = {
            age: patientData.age || 0,
            weight: patientData.weight || null,
            sex: patientData.sex || null, // should be "M" or "F"
            conditions: patientData.conditions || [],
            current_medications: patientData.current_medications || [],
            allergies: patientData.allergies || [],
            pregnant: patientData.pregnant || false,
            renal_function: patientData.renal_function || null,
            hepatic_function: patientData.hepatic_function || null
        };

        const started = await this.startV2Analysis(apiPatientData, medicationText);
        this.sessionId = started.session_id;
        this.analysisResult = await this.pollV2Status(this.sessionId);
        return this.analysisResult;
    }

    async startV2Analysis(patientData, medicationText) {
        const payload = {
            medication: medicationText,
            patient_data: patientData,
            save_to_db: true
        };

        const response = await fetch(`${this.apiUrl}/api/v2/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Erro ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    }

    async pollV2Status(sessionId, timeoutMs = 600000, intervalMs = 2000) {
        const start = Date.now();
        while (true) {
            if (Date.now() - start > timeoutMs) {
                throw new Error('Análise excedeu o tempo limite.');
            }

            const response = await fetch(`${this.apiUrl}/api/v2/status/${encodeURIComponent(sessionId)}`, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Erro ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            const status = String(data.status || '').toLowerCase();
            if (['completed', 'failed', 'rejected', 'awaiting_review'].includes(status)) {
                return data;
            }

            await new Promise(r => setTimeout(r, intervalMs));
        }
    }

    /**
     * Formata o nível de risco para exibição
     */
    formatRiskLevel(risk) {
        const riskMap = {
            'low': { label: 'BAIXO', color: 'green', icon: 'check-circle' },
            'medium': { label: 'MODERADO', color: 'yellow', icon: 'exclamation-triangle' },
            'high': { label: 'ALTO', color: 'orange', icon: 'exclamation-circle' },
            'critical': { label: 'CRÍTICO', color: 'red', icon: 'times-circle' }
        };
        return riskMap[risk] || riskMap['low'];
    }

    /**
     * Sanitiza texto para prevenir XSS
     */
    sanitizeText(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Obtém o último resultado de análise
     */
    getLastResult() {
        return this.analysisResult;
    }

    /**
     * Obtém o session ID atual
     */
    getSessionId() {
        return this.sessionId;
    }

    /**
     * Limpa os dados de análise
     */
    reset() {
        this.analysisResult = null;
        this.sessionId = null;
    }
}

// Instância global
window.medsafeAPI = new MedSafeAPI();
