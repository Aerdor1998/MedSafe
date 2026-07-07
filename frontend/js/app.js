/**
 * MedSafe Frontend Application
 * Sistema de Contra-indicativos de Medicamentos
 */

class MedSafeApp {
    constructor() {
        this.currentStep = 1;
        this.patientData = {};
        this.medicationData = {};
        this.analysisResult = null;
        this.sessionId = null;
        
        // Define a URL da API baseada no ambiente
        // SKILL: debugging-strategies
        // FIX: Porta mudada 8000 → 9000 → 9001 devido a conflitos
        // Ver PORT_CONFLICT_FIX.md para detalhes
        this.apiUrl = window.location.hostname.includes('hf.space')
            ? `https://medsafe-mvp.hf.space` // Hugging Face Space
            : 'http://localhost:9001'; // Porta do backend FastAPI (Docker)
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.setupFormValidation();
        this.setupImageUpload();
        this.setupMedicationSearch();
        this.updateStepIndicator();
        this.checkSystemStatus();
    }

    // =========================================================================
    // SECURITY FIX: Métodos de sanitização para prevenir XSS
    // =========================================================================

    /**
     * Sanitiza texto puro escapando caracteres HTML
     * @param {string} text - Texto a ser sanitizado
     * @returns {string} - Texto com caracteres HTML escapados
     */
    sanitizeText(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Sanitiza HTML usando DOMPurify
     * @param {string} html - HTML a ser sanitizado
     * @returns {string} - HTML sanitizado
     */
    sanitizeHtml(html) {
        if (!html) return '';

        // Configuração de whitelist de tags e atributos
        const purifyConfig = {
            ALLOWED_TAGS: [
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'p', 'span', 'div', 'br',
                'strong', 'em', 'b', 'i', 'u',
                'ul', 'ol', 'li',
                'details', 'summary',
                'table', 'tr', 'td', 'th', 'thead', 'tbody',
            ],
            ALLOWED_ATTR: ['class'],
            ALLOW_DATA_ATTR: false,
        };

        // Usar DOMPurify se disponível
        if (typeof DOMPurify !== 'undefined') {
            return DOMPurify.sanitize(html, purifyConfig);
        }

        // Fallback: escapar tudo se DOMPurify não estiver disponível
        console.warn('DOMPurify not available, escaping all HTML');
        return this.sanitizeText(html);
    }

    bindEvents() {
        // Form submissions
        const patientForm = document.getElementById('patient-form');
        if (patientForm) {
            patientForm.addEventListener('submit', (e) => this.handlePatientForm(e));
        }

        // Navigation buttons - use optional chaining para evitar erros
        const backBtn = document.getElementById('back-to-step1');
        if (backBtn) backBtn.addEventListener('click', () => this.goToStep(1));

        const analyzeBtn = document.getElementById('analyze-medication');
        if (analyzeBtn) analyzeBtn.addEventListener('click', () => this.analyzeMedication());

        const newAnalysisBtn = document.getElementById('new-analysis');
        if (newAnalysisBtn) newAnalysisBtn.addEventListener('click', () => this.resetApp());

        const downloadBtn = document.getElementById('download-report');
        if (downloadBtn) downloadBtn.addEventListener('click', () => this.downloadReport());

        // 3D view toggle (opcional - pode não existir no novo layout)
        const toggle3DBtn = document.getElementById('toggle-3d-view');
        if (toggle3DBtn) toggle3DBtn.addEventListener('click', () => this.toggle3DView());

        // Gender change for pregnancy/breastfeeding fields
        const genderSelect = document.getElementById('gender');
        if (genderSelect) {
            genderSelect.addEventListener('change', (e) => this.handleGenderChange(e));
        }

        // System status refresh
        const refreshStatusBtn = document.getElementById('refresh-status');
        if (refreshStatusBtn) {
            refreshStatusBtn.addEventListener('click', () => this.checkSystemStatus());
        }
    }

    setupFormValidation() {
        const requiredFields = ['age', 'gender'];

        requiredFields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            if (field) {
                field.addEventListener('blur', () => this.validateField(field));
                field.addEventListener('input', () => this.clearFieldError(field));
            }
        });
    }

    setupImageUpload() {
        const uploadArea = document.getElementById('image-upload-area');
        const uploadInput = document.getElementById('image-upload');

        if (!uploadArea || !uploadInput) return;

        // Click to upload
        uploadArea.addEventListener('click', () => uploadInput.click());

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('border-accent-orange', 'bg-white/5');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('border-accent-orange', 'bg-white/5');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('border-accent-orange', 'bg-white/5');

            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.handleImageUpload(files[0]);
            }
        });

        // File input change
        uploadInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleImageUpload(e.target.files[0]);
            }
        });
    }

    setupMedicationSearch() {
        const searchInput = document.getElementById('medication-search');
        if (!searchInput) return;

        let searchTimeout;

        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            const query = e.target.value.trim();

            if (query.length >= 2) {
                searchTimeout = setTimeout(() => this.searchMedications(query), 300);
            } else {
                this.hideMedicationSuggestions();
            }
        });
    }

    handleGenderChange(event) {
        const gender = event.target.value;

        // Se não for feminino, desmarcar checkboxes de gravidez/amamentação
        if (gender !== 'feminino') {
            const pregnancy = document.getElementById('pregnancy');
            const breastfeeding = document.getElementById('breastfeeding');
            if (pregnancy) pregnancy.checked = false;
            if (breastfeeding) breastfeeding.checked = false;
        }
    }

    async handlePatientForm(event) {
        event.preventDefault();

        if (!this.validatePatientForm()) {
            return;
        }

        // Collect patient data with null-safe access
        const getValue = (id) => document.getElementById(id)?.value || '';
        const getChecked = (id) => document.getElementById(id)?.checked || false;

        this.patientData = {
            age: parseInt(getValue('age')) || 0,
            gender: getValue('gender'),
            weight: parseFloat(getValue('weight')) || null,
            conditions: this.parseTextareaList(getValue('conditions')),
            allergies: this.parseTextareaList(getValue('allergies')),
            current_medications: this.parseTextareaList(getValue('current-medications')),
            alcohol_use: getChecked('alcohol-use'),
            smoking: getChecked('smoking'),
            pregnancy: getChecked('pregnancy') || null,
            breastfeeding: getChecked('breastfeeding') || null
        };

        console.log('Patient data collected:', this.patientData);
        this.goToStep(2);
    }

    validatePatientForm() {
        const age = document.getElementById('age').value;
        const gender = document.getElementById('gender').value;

        if (!age || age < 0 || age > 120) {
            this.showFieldError('age', 'Idade deve estar entre 0 e 120 anos');
            return false;
        }

        if (!gender) {
            this.showFieldError('gender', 'Gênero é obrigatório');
            return false;
        }

        return true;
    }

    validateField(field) {
        if (field.hasAttribute('required') && !field.value.trim()) {
            this.showFieldError(field.id, 'Este campo é obrigatório');
            return false;
        }
        
        this.clearFieldError(field);
        return true;
    }

    showFieldError(fieldId, message) {
        const field = document.getElementById(fieldId);
        this.clearFieldError(field);
        
        field.classList.add('border-red-500');
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'text-red-500 text-sm mt-1 field-error';
        errorDiv.textContent = message;
        field.parentNode.appendChild(errorDiv);
    }

    clearFieldError(field) {
        field.classList.remove('border-red-500');
        const errorDiv = field.parentNode.querySelector('.field-error');
        if (errorDiv) {
            errorDiv.remove();
        }
    }

    parseTextareaList(text) {
        if (!text || !text.trim()) return [];
        
        return text.split(/[,\n]/)
                  .map(item => item.trim())
                  .filter(item => item.length > 0);
    }

    async handleImageUpload(file) {
        if (!this.validateImageFile(file)) {
            return;
        }

        // Show preview
        const previewContainer = document.getElementById('image-preview');
        const previewImg = document.getElementById('preview-img');
        
        previewImg.src = URL.createObjectURL(file);
        previewContainer.classList.remove('hidden');

        // Upload and process image
        try {
            this.showOCRLoading();
            
            const formData = new FormData();
            formData.append('file', file);

            // v2 OCR endpoint
            const response = await fetch(`${this.apiUrl}/api/v2/vision/analyze`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Erro no upload da imagem');
            }

            const result = await response.json();
            this.displayOCRResult(result);
            
            // Auto-fill medication if identified
            if (result.drug_name) {
                document.getElementById('medication-search').value = result.drug_name;
                this.medicationData.name = result.drug_name;
            }

        } catch (error) {
            console.error('Erro no OCR:', error);
            this.showOCRError('Erro ao processar imagem. Tente novamente.');
        }
    }

    validateImageFile(file) {
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png'];
        const maxSize = 10 * 1024 * 1024; // 10MB

        if (!allowedTypes.includes(file.type)) {
            alert('Tipo de arquivo não suportado. Use JPG ou PNG.');
            return false;
        }

        if (file.size > maxSize) {
            alert('Arquivo muito grande. Máximo 10MB.');
            return false;
        }

        return true;
    }

    showOCRLoading() {
        const ocrResult = document.getElementById('ocr-result');
        ocrResult.classList.remove('hidden');
        ocrResult.innerHTML = `
            <div class="flex items-center space-x-3">
                <i class="fas fa-spinner fa-spin text-blue-500"></i>
                <span class="text-gray-600">Processando imagem...</span>
            </div>
        `;
    }

    displayOCRResult(result) {
        const ocrResult = document.getElementById('ocr-result');
        const ocrText = document.getElementById('ocr-text');

        ocrResult.classList.remove('hidden');
        ocrText.textContent = result.extracted_text || 'Nenhum texto identificado';

        if (result.drug_name) {
            // SECURITY FIX: Sanitizar dados da API antes de exibir
            const safeMedName = this.sanitizeText(result.drug_name);
            const safeExtractedText = this.sanitizeText(result.extracted_text);

            ocrResult.innerHTML = this.sanitizeHtml(`
                <h4 class="font-semibold text-gray-800 mb-2">Medicamento Identificado:</h4>
                <p class="text-lg font-medium text-green-600 mb-2">${safeMedName}</p>
                <details class="text-sm">
                    <summary class="cursor-pointer text-gray-600">Texto completo extraído</summary>
                    <p class="mt-2 text-gray-500">${safeExtractedText}</p>
                </details>
            `);
        }
    }

    showOCRError(message) {
        const ocrResult = document.getElementById('ocr-result');
        ocrResult.classList.remove('hidden');
        ocrResult.innerHTML = `
            <div class="text-red-600">
                <i class="fas fa-exclamation-triangle mr-2"></i>
                ${message}
            </div>
        `;
    }

    async searchMedications(query) {
        try {
            // NOTE: medication suggestions endpoint is v2 now (if enabled)
            const response = await fetch(`${this.apiUrl}/api/v2/medications/search?q=${encodeURIComponent(query)}`);

            if (!response.ok) {
                throw new Error('Erro na busca');
            }

            const data = await response.json();
            this.displayMedicationSuggestions(data.results);

        } catch (error) {
            console.error('Erro na busca de medicamentos:', error);
        }
    }

    displayMedicationSuggestions(medications) {
        const suggestionsContainer = document.getElementById('medication-suggestions');
        
        if (medications.length === 0) {
            suggestionsContainer.classList.add('hidden');
            return;
        }

        suggestionsContainer.innerHTML = medications.map(med => `
            <div class="medication-suggestion p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-blue-50 transition-colors"
                 data-name="${med.name}" data-active="${med.active_ingredient}">
                <div class="font-medium text-gray-800">${med.name}</div>
                <div class="text-sm text-gray-600">${med.active_ingredient}</div>
                ${med.therapeutic_class ? `<div class="text-xs text-gray-500">${med.therapeutic_class}</div>` : ''}
            </div>
        `).join('');

        // Add click events to suggestions
        suggestionsContainer.querySelectorAll('.medication-suggestion').forEach(suggestion => {
            suggestion.addEventListener('click', () => {
                const name = suggestion.dataset.name;
                const active = suggestion.dataset.active;
                
                document.getElementById('medication-search').value = name;
                this.medicationData = { name, active_ingredient: active };
                this.hideMedicationSuggestions();
            });
        });

        suggestionsContainer.classList.remove('hidden');
    }

    hideMedicationSuggestions() {
        const suggestions = document.getElementById('medication-suggestions');
        if (suggestions) suggestions.classList.add('hidden');
    }

    async checkSystemStatus() {
        const statusContainer = document.getElementById('system-status');
        if (!statusContainer) return;

        statusContainer.innerHTML = `
            <div class="flex items-center text-gray-600">
                <i class="fas fa-spinner fa-spin text-blue-500 mr-2 text-xs"></i>
                <span>Verificando conexão...</span>
            </div>
        `;

        try {
            const response = await fetch(`${this.apiUrl}/healthz`, { 
                method: 'GET',
                timeout: 5000 
            });

            if (response.ok) {
                const health = await response.json();
                
                // Try to get more detailed status from v2 health
                let modelInfo = 'Modelo padrão';
                try {
                    const v2Response = await fetch(`${this.apiUrl}/api/v2/health`);
                    if (v2Response.ok) {
                        const v2Health = await v2Response.json();
                        modelInfo = v2Health.model || 'Desconhecido';
                    }
                } catch (e) {
                    console.log('v2 health não disponível');
                }

                statusContainer.innerHTML = `
                    <div class="space-y-1">
                        <div class="flex items-center text-green-600">
                            <i class="fas fa-circle text-green-500 mr-2 text-xs"></i>
                            <span>API Online</span>
                        </div>
                        <div class="flex items-center text-gray-500 text-xs">
                            <i class="fas fa-robot mr-2"></i>
                            <span>Modelo: ${modelInfo}</span>
                        </div>
                    </div>
                `;
            } else {
                throw new Error('API não respondeu corretamente');
            }
        } catch (error) {
            console.error('Erro ao verificar status:', error);
            statusContainer.innerHTML = `
                <div class="flex items-center text-red-600">
                    <i class="fas fa-exclamation-circle mr-2 text-xs"></i>
                    <span>API Offline ou inacessível</span>
                </div>
                <p class="text-xs text-gray-500 mt-1">Verifique se o backend está rodando</p>
            `;
        }
    }

    async analyzeMedication() {
        console.log('🚀 analyzeMedication iniciado');
        
        const medicationName = document.getElementById('medication-search').value.trim();
        console.log('💊 Medicamento:', medicationName);
        
        if (!medicationName) {
            alert('Por favor, identifique um medicamento antes de continuar.');
            return;
        }

        // Verificar se patientData foi preenchido
        if (!this.patientData || Object.keys(this.patientData).length === 0) {
            console.error('❌ patientData está vazio!', this.patientData);
            alert('Erro: Dados do paciente não foram coletados. Por favor, preencha o formulário inicial.');
            this.goToStep(1);
            return;
        }

        // LGPD: avoid logging full patient data in console
        this.medicationData.name = medicationName;
        this.goToStep(3);

        try {
            // Get selected model (if any)
            const modelSelect = document.getElementById('ollama-model');
            const selectedModel = modelSelect ? modelSelect.value : '';
            
            // Prepare form data
            const formData = new FormData();
            formData.append('patient_data', JSON.stringify(this.patientData));
            formData.append('medication_text', medicationName);
            
            // Add model selection if specified
            if (selectedModel) {
                formData.append('model', selectedModel);
                console.log('🤖 Modelo selecionado:', selectedModel);
            }
            
            console.log('📦 FormData preparado (dados sensíveis omitidos do log)');

            // Add image if uploaded
            const imageInput = document.getElementById('image-upload');
            if (imageInput.files.length > 0) {
                formData.append('image', imageInput.files[0]);
            }

            // Criar AbortController com timeout de 10 minutos (600 segundos)
            // Análises complexas com LLM podem demorar, especialmente com múltiplos agentes
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 600000);

            // v2 async analysis: start job then poll status
            const payload = {
                medication: medicationName,
                patient_data: {
                    age: this.patientData.age || 0,
                    weight: this.patientData.weight || null,
                    // backend expects "M" or "F"
                    sex: (this.patientData.gender === 'masculino') ? 'M' : (this.patientData.gender === 'feminino' ? 'F' : null),
                    conditions: this.patientData.conditions || [],
                    current_medications: this.patientData.current_medications || [],
                    allergies: this.patientData.allergies || [],
                    pregnant: !!this.patientData.pregnancy,
                    hepatic_function: this.patientData.hepatic_function || null,
                    renal_function: this.patientData.renal_function || null
                },
                save_to_db: true
            };

            const response = await fetch(`${this.apiUrl}/api/v2/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify(payload),
                signal: controller.signal
            });

            console.log('📡 Resposta recebida:', response.status, response.statusText);
            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Erro na análise do servidor');
            }

            const started = await response.json();
            this.sessionId = started.session_id;
            if (!this.sessionId) {
                throw new Error('Servidor não retornou session_id');
            }

            // Poll status until terminal state
            this.analysisResult = await this.pollV2Status(this.sessionId, 600000, 2000);
            
            // Debug: Log full result
            console.log('📊 Resultado da análise recebido (detalhes omitidos do log).');
            
            setTimeout(() => {
                this.displayAnalysisResult();
                this.goToStep(4);
            }, 1500);

        } catch (error) {
            console.error('❌ ERRO NA ANÁLISE:', error);
            console.error('   Tipo:', error.name);
            console.error('   Mensagem:', error.message);
            console.error('   Stack:', error.stack);
            
            let errorMessage = 'Erro ao analisar medicamento. Tente novamente.';
            
            if (error.name === 'AbortError') {
                errorMessage = 'A análise está demorando muito (>10min). Verifique se o Ollama está rodando com GPU habilitada e tente novamente.';
            } else if (error.message && error.message !== 'Failed to fetch') {
                errorMessage = error.message;
            } else if (error.message === 'Failed to fetch') {
                errorMessage = 'Erro de conexão com o servidor. Verifique se o backend está rodando em ' + this.apiUrl;
            }
            
            alert(errorMessage);
            this.goToStep(2);
        }
    }

    displayAnalysisResult() {
        if (!this.analysisResult) return;

        console.log('📊 Displaying analysis result:', this.analysisResult);

        // Update risk overview
        this.updateRiskOverview();
        
        // Display detailed results
        this.displayContraindications();
        this.displayInteractions();
        this.displayAdverseReactions();
        this.displayRecommendations();
        this.displaySummary();
        this.displayMetaInfo();
    }

    async pollV2Status(sessionId, timeoutMs = 600000, intervalMs = 2000) {
        const start = Date.now();
        while (true) {
            if (Date.now() - start > timeoutMs) {
                throw new Error('Análise excedeu o tempo limite.');
            }
            const resp = await fetch(`${this.apiUrl}/api/v2/status/${encodeURIComponent(sessionId)}`);
            if (!resp.ok) {
                const errorData = await resp.json().catch(() => ({}));
                throw new Error(errorData.detail || `Erro ao consultar status (${resp.status})`);
            }
            const data = await resp.json();
            const status = String(data.status || '').toLowerCase();
            if (['completed', 'failed', 'rejected', 'awaiting_review'].includes(status)) {
                return data;
            }
            await new Promise(r => setTimeout(r, intervalMs));
        }
    }
    
    displayMetaInfo() {
        // Add model and confidence info to the summary section
        const summaryContainer = document.getElementById('summary-text');
        const confidence = this.analysisResult.confidence_score;
        const model = this.analysisResult.model_used || 'Desconhecido';
        const requiresReview = this.analysisResult.requires_human_review;
        const escalationReasons = this.analysisResult.escalation_reasons || [];

        // SECURITY FIX: Sanitizar dados da API
        const safeModel = this.sanitizeText(model);
        const safeReasons = escalationReasons.map(r => this.sanitizeText(r)).join(', ');

        let metaHtml = '<div class="mt-4 pt-4 border-t border-gray-200">';
        metaHtml += '<h4 class="font-semibold text-gray-700 mb-2">Informações da Análise</h4>';
        metaHtml += `<p class="text-sm text-gray-600"><strong>Modelo:</strong> ${safeModel}</p>`;

        if (confidence !== undefined) {
            const confidencePercent = (confidence * 100).toFixed(1);
            const confidenceColor = confidence >= 0.7 ? 'text-green-600' : confidence >= 0.5 ? 'text-yellow-600' : 'text-red-600';
            metaHtml += `<p class="text-sm ${confidenceColor}"><strong>Confiança:</strong> ${confidencePercent}%</p>`;
        }

        if (requiresReview) {
            metaHtml += '<p class="text-sm text-orange-600 mt-2"><i class="fas fa-exclamation-triangle mr-1"></i> <strong>Requer revisão humana</strong></p>';
            if (escalationReasons.length > 0) {
                metaHtml += `<p class="text-xs text-gray-500">Razões: ${safeReasons}</p>`;
            }
        }

        metaHtml += '</div>';
        summaryContainer.innerHTML += this.sanitizeHtml(metaHtml);
    }

    updateRiskOverview() {
        const riskCard = document.getElementById('overall-risk-card');
        const riskText = document.getElementById('risk-level-text');
        const riskDescription = document.getElementById('risk-description');
        
        // Mapear do formato do backend - aceita ambos formatos (direto ou nested)
        const risk = this.analysisResult.risk_level || this.analysisResult.analysis?.risk_level || 'low';
        
        console.log('🎯 updateRiskOverview - risk:', risk);
        
        // Remove all risk classes
        riskCard.classList.remove('risk-low', 'risk-medium', 'risk-high', 'risk-critical');
        
        // Add appropriate class and content (backend retorna em inglês)
        switch(risk) {
            case 'low':
                riskCard.classList.add('risk-low');
                riskText.textContent = 'RISCO BAIXO';
                riskDescription.textContent = 'Medicamento seguro para suas condições';
                break;
            case 'medium':
                riskCard.classList.add('risk-medium');
                riskText.textContent = 'RISCO MÉDIO';
                riskDescription.textContent = 'Usar com cautela e monitoramento';
                break;
            case 'high':
                riskCard.classList.add('risk-high');
                riskText.textContent = 'RISCO ALTO';
                riskDescription.textContent = 'Requer supervisão médica rigorosa';
                break;
            case 'critical':
                riskCard.classList.add('risk-critical');
                riskText.textContent = 'RISCO CRÍTICO';
                riskDescription.textContent = 'CONTRAINDICADO - Não usar';
                break;
            default:
                riskCard.classList.add('risk-low');
                riskText.textContent = 'RISCO BAIXO';
                riskDescription.textContent = 'Análise concluída';
        }
    }

    displayContraindications() {
        const container = document.getElementById('contraindications-list');
        const contraindications = this.analysisResult.contraindications || this.analysisResult.analysis?.contraindications || [];

        if (contraindications.length === 0) {
            container.innerHTML = '<p class="text-gray-500 italic">Nenhuma contraindicação identificada</p>';
            return;
        }

        container.innerHTML = contraindications.map(item => {
            const type = item.type || item.condition || 'Contraindicação';
            const description = item.description || item.reason || '';
            const source = item.source || '';
            const severity = item.severity || 'high';
            
            return `
                <div class="p-4 bg-red-50 border-l-4 border-red-400 rounded">
                    <h4 class="font-semibold text-red-800">${type}</h4>
                    <p class="text-red-700 text-sm mt-1">${description}</p>
                    ${source ? `<p class="text-xs text-red-600 mt-2"><strong>Fonte:</strong> ${source}</p>` : ''}
                    ${item.recommendation ? `<p class="text-sm text-red-700 mt-2 font-medium">${item.recommendation}</p>` : ''}
                </div>
            `;
        }).join('');
    }

    displayInteractions() {
        const container = document.getElementById('interactions-list');
        const interactions = this.analysisResult.interactions || this.analysisResult.analysis?.interactions || [];

        console.log('🔄 displayInteractions - data:', interactions);

        if (!interactions || interactions.length === 0) {
            container.innerHTML = '<p class="text-gray-500 italic">Nenhuma interação identificada</p>';
            return;
        }

        container.innerHTML = interactions.map(item => {
            // Handle both API formats: {drug1, drug2, description} and {interacting_drug, effect}
            const drug1 = item.drug1 || '';
            const drug2 = item.drug2 || item.interacting_drug || '';
            const description = item.description || item.effect || '';
            const severity = item.severity || 'medium';
            const severityClass = severity === 'high' || severity === 'critical' ? 'bg-red-50 border-red-400' : 
                                  severity === 'medium' ? 'bg-orange-50 border-orange-400' : 
                                  'bg-yellow-50 border-yellow-400';
            const textClass = severity === 'high' || severity === 'critical' ? 'text-red-800' : 
                              severity === 'medium' ? 'text-orange-800' : 'text-yellow-800';
            
            return `
                <div class="p-4 ${severityClass} border-l-4 rounded">
                    <h4 class="font-semibold ${textClass}">${drug1} + ${drug2}</h4>
                    <p class="${textClass.replace('800', '700')} text-sm mt-1">${description}</p>
                    ${item.mechanism ? `<p class="text-xs ${textClass.replace('800', '600')} mt-1"><strong>Mecanismo:</strong> ${item.mechanism}</p>` : ''}
                    ${item.category ? `<p class="text-xs ${textClass.replace('800', '600')} mt-1"><strong>Categoria:</strong> ${item.category}</p>` : ''}
                    <span class="inline-block mt-2 px-2 py-1 text-xs rounded ${severity === 'high' || severity === 'critical' ? 'bg-red-200 text-red-800' : severity === 'medium' ? 'bg-orange-200 text-orange-800' : 'bg-yellow-200 text-yellow-800'}">
                        Severidade: ${severity.toUpperCase()}
                    </span>
                    ${item.recommendation ? `<p class="text-sm ${textClass.replace('800', '700')} mt-2 font-medium">${item.recommendation}</p>` : ''}
                </div>
            `;
        }).join('');
    }

    displayAdverseReactions() {
        const container = document.getElementById('adverse-reactions-list');
        const reactions = this.analysisResult.adverse_reactions || this.analysisResult.analysis?.adverse_reactions || [];

        if (reactions.length === 0) {
            container.innerHTML = '<p class="text-gray-500 italic">Nenhuma reação adversa específica identificada</p>';
            return;
        }

        container.innerHTML = reactions.map(item => {
            // Handle both API formats
            const reaction = item.reaction || item.type || 'Reação Adversa';
            const description = item.description || '';
            const frequency = item.frequency || 'Não especificada';
            const severity = item.severity || 'medium';
            const source = item.source || '';
            const riskFactors = item.risk_factors || [];
            
            return `
                <div class="p-4 bg-blue-50 border-l-4 border-blue-400 rounded">
                    <h4 class="font-semibold text-blue-800">${reaction}</h4>
                    <p class="text-blue-700 text-sm mt-1">${description}</p>
                    ${frequency !== 'Não especificada' || severity ? `
                        <div class="flex justify-between items-center mt-2">
                            ${frequency !== 'Não especificada' ? `<span class="text-xs text-blue-600"><strong>Frequência:</strong> ${frequency}</span>` : ''}
                            ${severity ? `<span class="text-xs text-blue-600"><strong>Severidade:</strong> ${severity}</span>` : ''}
                        </div>
                    ` : ''}
                    ${source ? `<p class="text-xs text-blue-500 mt-1"><strong>Fonte:</strong> ${source}</p>` : ''}
                    ${riskFactors && riskFactors.length > 0 ? `
                        <p class="text-xs text-blue-600 mt-1">
                            <strong>Fatores de risco:</strong> ${riskFactors.join(', ')}
                        </p>
                    ` : ''}
                </div>
            `;
        }).join('');
    }

    displayRecommendations() {
        const container = document.getElementById('recommendations-list');
        const recommendations = this.analysisResult.recommendations || this.analysisResult.analysis?.recommendations || [];

        if (recommendations.length === 0) {
            container.innerHTML = '<p class="text-gray-500 italic">Nenhuma recomendação específica</p>';
            return;
        }

        container.innerHTML = recommendations.map(item => {
            const priority = item.priority || 'medio';
            const priorityColor = this.getPriorityColor(priority);
            const category = item.category || item.type || 'Recomendação';
            const action = item.action || item.description || item.recommendation || '';
            
            return `
                <div class="p-4 ${priorityColor} border-l-4 rounded">
                    <h4 class="font-semibold">${category}</h4>
                    <p class="text-sm mt-1">${action}</p>
                    ${item.rationale ? `<p class="text-xs mt-2 opacity-80">${item.rationale}</p>` : ''}
                </div>
            `;
        }).join('');
    }

    getPriorityColor(priority) {
        switch(priority) {
            case 'critico': return 'bg-red-50 border-red-400 text-red-800';
            case 'alto': return 'bg-orange-50 border-orange-400 text-orange-800';
            case 'medio': return 'bg-yellow-50 border-yellow-400 text-yellow-800';
            default: return 'bg-green-50 border-green-400 text-green-800';
        }
    }

    displaySummary() {
        const container = document.getElementById('summary-text');
        const summary = this.analysisResult.analysis_notes || 
                       this.analysisResult.summary ||
                       this.analysisResult.analysis?.analysis_notes || 
                       this.analysisResult.analysis?.summary ||
                       'Análise concluída com sucesso. Os resultados detalhados estão disponíveis nas seções acima.';
        container.innerHTML = this.formatSummaryText(summary);
    }

    formatSummaryText(text) {
        // SECURITY FIX: Sanitizar HTML antes de renderizar (prevenir XSS)
        // Primeiro, escapar caracteres especiais do input
        const escapeHtml = (str) => {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        };

        // Escapar o texto primeiro
        let safeText = escapeHtml(text);

        // Convert markdown-like formatting to HTML (usando texto já escapado)
        let html = safeText
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold mt-4 mb-2">$1</h3>')
            .replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold mt-6 mb-3">$1</h2>')
            .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mt-8 mb-4">$1</h1>')
            .replace(/\n/g, '<br>')
            .replace(/^- (.*$)/gim, '<li class="ml-4">$1</li>')
            .replace(/(<li.*<\/li>)/s, '<ul class="list-disc">$1</ul>');

        // SECURITY FIX: Usar DOMPurify para sanitização final
        // Whitelist apenas tags e atributos seguros
        const purifyConfig = {
            ALLOWED_TAGS: ['strong', 'em', 'h1', 'h2', 'h3', 'br', 'ul', 'li', 'p', 'span'],
            ALLOWED_ATTR: ['class'],
            ALLOW_DATA_ATTR: false,
        };

        // Se DOMPurify estiver disponível, usar para sanitização
        if (typeof DOMPurify !== 'undefined') {
            return DOMPurify.sanitize(html, purifyConfig);
        }

        // Fallback: retornar texto escapado se DOMPurify não estiver disponível
        console.warn('DOMPurify not available, using escaped text');
        return safeText;
    }

    goToStep(step) {
        // Hide all steps
        document.querySelectorAll('.step-content').forEach(el => {
            el.classList.add('hidden');
        });

        // Show target step
        document.getElementById(`step-${step}`).classList.remove('hidden');
        document.getElementById(`step-${step}`).classList.add('fade-in');

        this.currentStep = step;
        this.updateStepIndicator();
    }

    updateStepIndicator() {
        const indicators = document.querySelectorAll('.step-dot');

        indicators.forEach((indicator, index) => {
            const stepNumber = index + 1;

            indicator.classList.remove('active', 'completed');

            if (stepNumber < this.currentStep) {
                indicator.classList.add('completed');
                indicator.innerHTML = '<i class="fas fa-check"></i>';
            } else if (stepNumber === this.currentStep) {
                indicator.classList.add('active');
                indicator.textContent = stepNumber;
            } else {
                indicator.textContent = stepNumber;
            }
        });
    }

    toggle3DView() {
        const container = document.getElementById('three-container');
        const button = document.getElementById('toggle-3d-view');
        
        if (window.threeVisualization) {
            if (window.threeVisualization.isShowingGraph) {
                window.threeVisualization.showMedication();
                button.innerHTML = '<i class="fas fa-cube mr-2"></i>Mostrar Grafo de Interações';
            } else {
                window.threeVisualization.showInteractionGraph(this.analysisResult);
                button.innerHTML = '<i class="fas fa-pills mr-2"></i>Mostrar Medicamento 3D';
            }
        } else {
            // Initialize 3D visualization
            window.threeVisualization = new ThreeVisualization('three-container');
            window.threeVisualization.showMedication();
        }
    }

    downloadReport() {
        if (!this.analysisResult) return;

        const reportData = {
            timestamp: new Date().toISOString(),
            session_id: this.sessionId,
            patient: {
                age: this.patientData.age,
                gender: this.patientData.gender
                // Omit sensitive data in report
            },
            medication: this.analysisResult.medication,
            overall_risk: this.analysisResult.overall_risk,
            summary: this.analysisResult.summary,
            disclaimer: this.analysisResult.disclaimer
        };

        const blob = new Blob([JSON.stringify(reportData, null, 2)], {
            type: 'application/json'
        });

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `medsafe-report-${this.sessionId || Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    resetApp() {
        this.currentStep = 1;
        this.patientData = {};
        this.medicationData = {};
        this.analysisResult = null;
        this.sessionId = null;

        // Reset forms with null-safe access
        const patientForm = document.getElementById('patient-form');
        if (patientForm) patientForm.reset();

        const medSearch = document.getElementById('medication-search');
        if (medSearch) medSearch.value = '';

        const imageUpload = document.getElementById('image-upload');
        if (imageUpload) imageUpload.value = '';

        const imagePreview = document.getElementById('image-preview');
        if (imagePreview) imagePreview.classList.add('hidden');

        const ocrResult = document.getElementById('ocr-result');
        if (ocrResult) ocrResult.classList.add('hidden');

        this.hideMedicationSuggestions();
        this.goToStep(1);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.medSafeApp = new MedSafeApp();
});/* Cache buster: 1759932159 */
