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
        this.apiUrl = window.location.hostname.includes('hf.space')
            ? `https://medsafe-mvp.hf.space` // Hugging Face Space
            : 'http://localhost:8000'; // Porta do backend FastAPI
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.setupFormValidation();
        this.setupImageUpload();
        this.setupMedicationSearch();
        this.updateStepIndicator();
    }

    bindEvents() {
        // Form submissions
        document.getElementById('patient-form').addEventListener('submit', (e) => this.handlePatientForm(e));
        
        // Navigation buttons
        document.getElementById('back-to-step1').addEventListener('click', () => this.goToStep(1));
        document.getElementById('analyze-medication').addEventListener('click', () => this.analyzeMedication());
        document.getElementById('new-analysis').addEventListener('click', () => this.resetApp());
        document.getElementById('download-report').addEventListener('click', () => this.downloadReport());
        document.getElementById('toggle-3d-view').addEventListener('click', () => this.toggle3DView());
        
        // Gender change for pregnancy/breastfeeding fields
        document.getElementById('gender').addEventListener('change', (e) => this.handleGenderChange(e));
    }

    setupFormValidation() {
        const requiredFields = ['age', 'gender'];
        
        requiredFields.forEach(fieldId => {
            const field = document.getElementById(fieldId);
            field.addEventListener('blur', () => this.validateField(field));
            field.addEventListener('input', () => this.clearFieldError(field));
        });
    }

    setupImageUpload() {
        const uploadArea = document.getElementById('image-upload-area');
        const uploadInput = document.getElementById('image-upload');

        // Click to upload
        uploadArea.addEventListener('click', () => uploadInput.click());

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('border-blue-500', 'bg-blue-50');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('border-blue-500', 'bg-blue-50');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('border-blue-500', 'bg-blue-50');
            
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
        const pregnancySection = document.getElementById('pregnancy-section');
        const breastfeedingSection = document.getElementById('breastfeeding-section');

        if (gender === 'feminino') {
            pregnancySection.style.display = 'block';
            breastfeedingSection.style.display = 'block';
        } else {
            pregnancySection.style.display = 'none';
            breastfeedingSection.style.display = 'none';
            document.getElementById('pregnancy').checked = false;
            document.getElementById('breastfeeding').checked = false;
        }
    }

    async handlePatientForm(event) {
        event.preventDefault();
        
        if (!this.validatePatientForm()) {
            return;
        }

        // Collect patient data
        this.patientData = {
            age: parseInt(document.getElementById('age').value),
            gender: document.getElementById('gender').value,
            weight: parseFloat(document.getElementById('weight').value) || null,
            conditions: this.parseTextareaList(document.getElementById('conditions').value),
            allergies: this.parseTextareaList(document.getElementById('allergies').value),
            current_medications: this.parseTextareaList(document.getElementById('current-medications').value),
            supplements: this.parseTextareaList(document.getElementById('supplements').value),
            alcohol_use: document.getElementById('alcohol-use').checked,
            smoking: document.getElementById('smoking').checked,
            pregnancy: document.getElementById('pregnancy').checked || null,
            breastfeeding: document.getElementById('breastfeeding').checked || null
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

            const response = await fetch(`${this.apiUrl}/api/upload-image`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Erro no upload da imagem');
            }

            const result = await response.json();
            this.displayOCRResult(result);
            
            // Auto-fill medication if identified
            if (result.medication_name) {
                document.getElementById('medication-search').value = result.medication_name;
                this.medicationData.name = result.medication_name;
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
        
        if (result.medication_name) {
            ocrResult.innerHTML = `
                <h4 class="font-semibold text-gray-800 mb-2">Medicamento Identificado:</h4>
                <p class="text-lg font-medium text-green-600 mb-2">${result.medication_name}</p>
                <details class="text-sm">
                    <summary class="cursor-pointer text-gray-600">Texto completo extraído</summary>
                    <p class="mt-2 text-gray-500">${result.extracted_text}</p>
                </details>
            `;
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
            const response = await fetch(`${this.apiUrl}/api/medications/search?q=${encodeURIComponent(query)}`);
            
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
        document.getElementById('medication-suggestions').classList.add('hidden');
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

        console.log('👤 Dados do paciente:', this.patientData);
        this.medicationData.name = medicationName;
        this.goToStep(3);

        try {
            // Prepare form data
            const formData = new FormData();
            formData.append('patient_data', JSON.stringify(this.patientData));
            formData.append('medication_text', medicationName);
            
            console.log('📦 FormData preparado');
            console.log('   - patient_data:', JSON.stringify(this.patientData));
            console.log('   - medication_text:', medicationName);

            // Add image if uploaded
            const imageInput = document.getElementById('image-upload');
            if (imageInput.files.length > 0) {
                formData.append('image', imageInput.files[0]);
            }

            // Criar AbortController com timeout de 120 segundos
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 120000);

            // Call analysis API com timeout
            console.log('🌐 Enviando requisição para:', `${this.apiUrl}/api/analyze`);
            
            const response = await fetch(`${this.apiUrl}/api/analyze`, {
                method: 'POST',
                body: formData,
                signal: controller.signal
            });

            console.log('📡 Resposta recebida:', response.status, response.statusText);
            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Erro na análise do servidor');
            }

            this.analysisResult = await response.json();
            this.sessionId = this.analysisResult.session_id;
            
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
                errorMessage = 'A análise está demorando muito (>2min). Verifique se o Ollama está rodando e tente novamente.';
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

        // Update risk overview
        this.updateRiskOverview();
        
        // Display detailed results
        this.displayContraindications();
        this.displayInteractions();
        this.displayAdverseReactions();
        this.displayRecommendations();
        this.displaySummary();
    }

    updateRiskOverview() {
        const riskCard = document.getElementById('overall-risk-card');
        const riskText = document.getElementById('risk-level-text');
        const riskDescription = document.getElementById('risk-description');
        
        // Mapear do formato do backend (analysis.risk_level)
        const risk = this.analysisResult.analysis?.risk_level || 'low';
        
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
        const contraindications = this.analysisResult.analysis?.contraindications || [];

        if (contraindications.length === 0) {
            container.innerHTML = '<p class="text-gray-500 italic">Nenhuma contraindicação identificada</p>';
            return;
        }

        container.innerHTML = contraindications.map(item => `
            <div class="p-4 bg-red-50 border-l-4 border-red-400 rounded">
                <h4 class="font-semibold text-red-800">${item.type}</h4>
                <p class="text-red-700 text-sm mt-1">${item.description}</p>
                <p class="text-xs text-red-600 mt-2"><strong>Fonte:</strong> ${item.source}</p>
                ${item.recommendation ? `<p class="text-sm text-red-700 mt-2 font-medium">${item.recommendation}</p>` : ''}
            </div>
        `).join('');
    }

    displayInteractions() {
        const container = document.getElementById('interactions-list');
        const interactions = this.analysisResult.analysis?.interactions || [];

        if (interactions.length === 0) {
            container.innerHTML = '<p class="text-gray-500 italic">Nenhuma interação identificada</p>';
            return;
        }

        container.innerHTML = interactions.map(item => `
            <div class="p-4 bg-orange-50 border-l-4 border-orange-400 rounded">
                <h4 class="font-semibold text-orange-800">Com ${item.interacting_drug}</h4>
                <p class="text-orange-700 text-sm mt-1">${item.effect}</p>
                ${item.mechanism ? `<p class="text-xs text-orange-600 mt-1"><strong>Mecanismo:</strong> ${item.mechanism}</p>` : ''}
                ${item.recommendation ? `<p class="text-sm text-orange-700 mt-2 font-medium">${item.recommendation}</p>` : ''}
            </div>
        `).join('');
    }

    displayAdverseReactions() {
        const container = document.getElementById('adverse-reactions-list');
        const reactions = this.analysisResult.analysis?.adverse_reactions || [];

        if (reactions.length === 0) {
            container.innerHTML = '<p class="text-gray-500 italic">Nenhuma reação adversa específica identificada</p>';
            return;
        }

        container.innerHTML = reactions.map(item => `
            <div class="p-4 bg-blue-50 border-l-4 border-blue-400 rounded">
                <h4 class="font-semibold text-blue-800">${item.reaction}</h4>
                <p class="text-blue-700 text-sm mt-1">${item.description}</p>
                <div class="flex justify-between items-center mt-2">
                    <span class="text-xs text-blue-600"><strong>Frequência:</strong> ${item.frequency}</span>
                    <span class="text-xs text-blue-600"><strong>Severidade:</strong> ${item.severity}</span>
                </div>
                ${item.risk_factors.length > 0 ? `
                    <p class="text-xs text-blue-600 mt-1">
                        <strong>Fatores de risco:</strong> ${item.risk_factors.join(', ')}
                    </p>
                ` : ''}
            </div>
        `).join('');
    }

    displayRecommendations() {
        const container = document.getElementById('recommendations-list');
        const recommendations = this.analysisResult.analysis?.recommendations || [];

        if (recommendations.length === 0) {
            container.innerHTML = '<p class="text-gray-500 italic">Nenhuma recomendação específica</p>';
            return;
        }

        container.innerHTML = recommendations.map(item => {
            const priorityColor = this.getPriorityColor(item.priority);
            return `
                <div class="p-4 ${priorityColor} border-l-4 rounded">
                    <h4 class="font-semibold">${item.category}</h4>
                    <p class="text-sm mt-1">${item.action}</p>
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
        const summary = this.analysisResult.analysis?.analysis_notes || 
                       this.analysisResult.analysis?.summary ||
                       'Análise concluída com sucesso. Os resultados detalhados estão disponíveis nas seções acima.';
        container.innerHTML = this.formatSummaryText(summary);
    }

    formatSummaryText(text) {
        // Convert markdown-like formatting to HTML
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold mt-4 mb-2">$1</h3>')
            .replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold mt-6 mb-3">$1</h2>')
            .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mt-8 mb-4">$1</h1>')
            .replace(/\n/g, '<br>')
            .replace(/^- (.*$)/gim, '<li class="ml-4">$1</li>')
            .replace(/(<li.*<\/li>)/s, '<ul class="list-disc">$1</ul>');
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
        const indicators = document.querySelectorAll('.step-indicator');
        
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

        // Reset forms
        document.getElementById('patient-form').reset();
        document.getElementById('medication-search').value = '';
        document.getElementById('image-upload').value = '';
        document.getElementById('image-preview').classList.add('hidden');
        document.getElementById('ocr-result').classList.add('hidden');

        // Reset gender-specific fields
        document.getElementById('pregnancy-section').style.display = 'none';
        document.getElementById('breastfeeding-section').style.display = 'none';

        this.hideMedicationSuggestions();
        this.goToStep(1);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.medSafeApp = new MedSafeApp();
});/* Cache buster: 1759932159 */
