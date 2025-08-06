# Manual de Uso - MedSafe

## 🏥 Sobre o Sistema

O MedSafe é um sistema de análise de contra-indicativos de medicamentos baseado nas diretrizes oficiais da **OMS (Organização Mundial da Saúde)** e **ANVISA (Agência Nacional de Vigilância Sanitária)**.

### ⚖️ Base Legal e Regulatória
- **RDC ANVISA 47/2009**: Regras de rotulagem de medicamentos
- **RDC ANVISA 94/2008**: Diretrizes para bulas de medicamentos
- **RDC ANVISA 96/2008**: Regulamentação de propagandas de medicamentos
- **Diretrizes OMS**: Padrões internacionais de farmacovigilância

## 🚀 Como Usar

### Passo 1: Anamnese Digital
1. **Dados Básicos**
   - Informe idade (obrigatório)
   - Selecione gênero (obrigatório)
   - Peso aproximado (opcional, mas recomendado)

2. **Condições Especiais**
   - Marque se está grávida ou amamentando (apenas para mulheres)
   - Indique uso de álcool ou tabaco

3. **Histórico Médico**
   - Liste condições médicas existentes (ex: hipertensão, diabetes)
   - Informe alergias conhecidas (ex: penicilina, lactose)
   - Liste medicamentos em uso atual
   - Mencione suplementos ou fitoterápicos

### Passo 2: Identificação do Medicamento

#### Opção A: Busca por Nome
- Digite o nome do medicamento no campo de busca
- Selecione da lista de sugestões que aparece
- Funciona com nomes comerciais e princípios ativos

#### Opção B: Upload de Imagem
- Clique na área de upload ou arraste uma imagem
- Formatos suportados: JPG, PNG (até 10MB)
- O sistema usa OCR para identificar o medicamento
- Tipos de imagem aceitos:
  - Foto da caixa do medicamento
  - Foto dos comprimidos/cápsulas
  - Foto da bula (páginas com nome do medicamento)

### Passo 3: Análise Automática
O sistema processa automaticamente:
- ✅ Verificação de contraindicações
- 🔄 Análise de interações medicamentosas
- 📊 Consulta à base OMS/ANVISA
- 🤖 Geração de recomendações via IA (AG2/Ollama)

### Passo 4: Resultados

#### Indicador de Risco Geral
- 🟢 **RISCO BAIXO**: Medicamento seguro para suas condições
- 🟡 **RISCO MÉDIO**: Usar com cautela e monitoramento
- 🟠 **RISCO ALTO**: Requer supervisão médica rigorosa
- 🔴 **RISCO CRÍTICO**: CONTRAINDICADO - Não usar

#### Informações Detalhadas

1. **Contraindicações**
   - Condições que impedem o uso do medicamento
   - Classificadas por gravidade (absoluta/relativa)
   - Com recomendações específicas

2. **Interações Medicamentosas**
   - Com medicamentos que você já usa
   - Tipo de interação (farmacocinética/farmacodinâmica)
   - Efeitos esperados e recomendações

3. **Reações Adversas**
   - Possíveis efeitos colaterais
   - Frequência esperada (comum, rara, etc.)
   - Fatores de risco específicos para você

4. **Recomendações Médicas**
   - Ações prioritárias
   - Monitoramento necessário
   - Alternativas terapêuticas se aplicável

#### Visualização 3D
- **Vista do Medicamento**: Representação 3D interativa
- **Grafo de Interações**: Rede visual mostrando interações entre medicamentos
- Use o mouse para rotacionar e explorar

## 🔒 Privacidade e Segurança

### Processamento Local
- ✅ Seus dados **NÃO são enviados** para servidores externos
- ✅ Processamento de IA via AG2/Ollama **local**
- ✅ OCR executado **localmente** no seu computador
- ✅ Banco de dados **local** (SQLite)

### Auditoria para Farmacovigilância
- Sessões são registradas com **ID anonimizado**
- Logs para **conformidade regulatória**
- **Anonimização automática** de dados antigos (90 dias)
- Compatível com **LGPD** e boas práticas de privacidade

## ⚠️ Avisos Importantes

### Limitações do Sistema
1. **Não substitui consulta médica**
   - Este é um sistema de **apoio informativo**
   - Sempre consulte seu médico antes de usar medicamentos
   - Em casos de emergência, procure atendimento médico imediato

2. **Base de Dados**
   - Contém medicamentos mais comuns no Brasil
   - Pode não incluir todos os medicamentos disponíveis
   - Dados baseados em bulas e literatura científica oficial

3. **OCR (Reconhecimento de Imagem)**
   - Precisão depende da qualidade da imagem
   - Confirme sempre o medicamento identificado
   - Em caso de dúvida, digite o nome manualmente

### Situações que Requerem Atenção Especial
- 🚨 **Gravidez e amamentação**
- 🚨 **Crianças e idosos**
- 🚨 **Múltiplas condições médicas**
- 🚨 **Uso de vários medicamentos**
- 🚨 **Insuficiência renal ou hepática**

## 🆘 Suporte e Problemas

### Problemas Comuns

**OCR não identifica o medicamento:**
- Verifique se a imagem está nítida
- Certifique-se de que o nome está visível
- Tente diferentes ângulos de foto
- Use a busca manual como alternativa

**Medicamento não encontrado:**
- Tente usar o princípio ativo em vez do nome comercial
- Verifique a grafia
- Consulte a bula para o nome correto

**Erro de conexão com IA:**
- Verifique se o Ollama está instalado e rodando
- A funcionalidade básica funciona mesmo sem IA
- Consulte as instruções de instalação do Ollama

### Relatórios e Downloads
- Use o botão "Baixar Relatório" para salvar os resultados
- Formato JSON com dados anonimizados
- Pode ser compartilhado com seu médico

## 📞 Contato e Feedback

Este sistema foi desenvolvido para auxiliar profissionais de saúde e pacientes com informações baseadas em evidências científicas e regulamentações oficiais.

Para dúvidas técnicas ou sugestões de melhorias, consulte a documentação técnica ou entre em contato através dos canais de suporte.

---

**Lembre-se:** Este sistema segue as melhores práticas de farmacovigilância e as diretrizes da OMS e ANVISA, mas **não substitui a consulta médica profissional**.