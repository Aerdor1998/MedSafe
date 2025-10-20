# Creating an XML version of the questionnaire and saving it to /mnt/data/Questionario_de_maturidade.xml
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
import xml.dom.minidom as minidom
import os

# Build XML structure based on the questionnaire content
root = Element('questionario')
root.set('titulo', 'Questionário de maturidade - Implementação de Framework Agentic AI para Automação de Processos')

meta = SubElement(root, 'metadata')
data = SubElement(meta, 'data')
data.text = ''
entrevistados = SubElement(meta, 'entrevistado')
entrevistados.text = ''
cargo = SubElement(meta, 'cargo')
cargo.text = ''
departamento = SubElement(meta, 'departamento')
departamento.text = ''

# Helper to add sections and questions
def add_section(parent, sec_id, title):
    sec = SubElement(parent, 'secao')
    sec.set('id', sec_id)
    sec.set('titulo', title)
    return sec

def add_question(section, qid, pergunta):
    q = SubElement(section, 'pergunta')
    q.set('id', qid)
    q_text = SubElement(q, 'texto')
    q_text.text = pergunta
    resposta = SubElement(q, 'resposta')
    resposta.text = ''  # placeholder
    return q

# Section 01
s1 = add_section(root, '01', 'CONTEXTO DE NEGÓCIO E PROCESSOS')
s1_1 = add_section(s1, '1.1', 'Mapeamento de Processos Repetitivos')
add_question(s1_1, 'Q1.1', 'Quais são os processos mais repetitivos executados diariamente pela equipe de logística/operações?')
add_question(s1_1, 'Q1.2', 'Qual a frequência de execução desses processos? (diária, semanal, mensal)')
add_question(s1_1, 'Q1.3', 'Quantas pessoas da equipe executam esses processos repetitivos regularmente?')
add_question(s1_1, 'Q1.4', 'Em quais sistemas/plataformas esses processos são executados? (TMS, ERP, Gmail, planilhas, etc.)')
add_question(s1_1, 'Q1.5', 'Há processos que seguem sempre a mesma sequência de passos? Pode descrever um exemplo completo?')
add_question(s1_1, 'Q1.6', 'Existem variações nesses processos? Se sim, quais são os principais desvios do padrão?')

s1_2 = add_section(s1, '1.2', 'Dores e Desafios Operacionais')
add_question(s1_2, 'Q2.1', 'Qual a principal dor operacional que você gostaria de resolver com automação?')
add_question(s1_2, 'Q2.2', 'Quais erros humanos são mais comuns durante a execução manual desses processos?')
add_question(s1_2, 'Q2.3', 'Há gargalos de produtividade que impactam prazos ou qualidade das entregas?')
add_question(s1_2, 'Q2.4', 'Existe retrabalho frequente? Em quais etapas ele costuma acontecer?')
add_question(s1_2, 'Q2.5', 'A equipe reporta cansaço ou frustração com tarefas repetitivas específicas?')

s1_3 = add_section(s1, '1.3', 'Objetivos e Resultados Esperados')
add_question(s1_3, 'Q3.1', 'Qual o principal objetivo da implementação do sistema agentic? (ex: liberar tempo, reduzir erros, escalar operação)')
add_question(s1_3, 'Q3.2', 'Que métricas você gostaria de acompanhar para avaliar o sucesso da implementação?')
add_question(s1_3, 'Q3.3', 'Há KPIs operacionais atuais que precisam melhorar? (ex: tempo médio de processamento, taxa de erro)')
add_question(s1_3, 'Q3.4', 'Qual seria considerado um resultado de sucesso após 3 meses? E após 6 meses?')
add_question(s1_3, 'Q3.5', 'Existem processos críticos que NÃO devem ser automatizados? Por quê?')

# Section 02
s2 = add_section(root, '02', 'ARQUITETURA E TECNOLOGIA')
s2_1 = add_section(s2, '2.1', 'Infraestrutura Atual')
add_question(s2_1, 'Q4.1', 'Qual a infraestrutura de TI atual? (on-premise, cloud, híbrida)')
add_question(s2_1, 'Q4.2', 'Qual provedor de cloud é utilizado? (AWS, Azure, GCP, outro)')
add_question(s2_1, 'Q4.3', 'Há restrições de segurança ou compliance que devemos considerar? (LGPD, SOC2, ISO)')
add_question(s2_1, 'Q4.4', 'Os sistemas atuais possuem APIs disponíveis? Quais sistemas têm APIs documentadas?')
add_question(s2_1, 'Q4.5', 'Existe ambiente de desenvolvimento/staging separado da produção?')
add_question(s2_1, 'Q4.6', 'Qual o sistema de versionamento de código utilizado? (GitHub, GitLab, Bitbucket)')

s2_2 = add_section(s2, '2.2', 'Integrações e Sistemas')
add_question(s2_2, 'Q5.1', 'Quais sistemas precisam se integrar ao framework agentic? Liste em ordem de prioridade.')
add_question(s2_2, 'Q5.2', 'Existe documentação técnica dos sistemas existentes? Está atualizada?')
add_question(s2_2, 'Q5.3', 'Há limitações técnicas conhecidas nos sistemas legados? (ex: APIs antigas, rate limits)')
add_question(s2_2, 'Q5.4', 'Os sistemas possuem ambientes de sandbox/teste para desenvolvimento?')
add_question(s2_2, 'Q5.5', 'Existe Single Sign-On (SSO) implementado? Qual protocolo? (OAuth, SAML)')
add_question(s2_2, 'Q5.6', 'Há necessidade de processar documentos (PDFs, imagens)? Que tipo de documentos?')

s2_3 = add_section(s2, '2.3', 'Captura de Dados e Observabilidade')
add_question(s2_3, 'Q6.1', 'Como você imagina o processo de "aprendizado" do sistema? Manual ou automático?')
add_question(s2_3, 'Q6.2', 'Existe resistência da equipe em ter ações monitoradas para detecção de padrões?')
add_question(s2_3, 'Q6.3', 'Quais dados dos processos já são coletados hoje? (logs, métricas, screenshots)')
add_question(s2_3, 'Q6.4', 'Há ferramentas de observabilidade em uso? (Datadog, New Relic, ELK Stack)')
add_question(s2_3, 'Q6.5', 'A equipe de TI tem capacidade de revisar logs e eventos do sistema regularmente?')

# Section 03
s3 = add_section(root, '03', 'ABORDAGEM AGENTIC MULTI-AGENT')
s3_1 = add_section(s3, '3.1', 'Arquitetura de Agentes')
add_question(s3_1, 'Q7.1', 'Você prefere uma abordagem modular (multi-agent) ou monolítica (single-agent)? Por quê?')
add_question(s3_1, 'Q7.2', 'Para o seu caso, quais "agentes especializados" fariam mais sentido?')
add_question(s3_1, 'Q7.3', 'Há necessidade de agentes trabalharem em paralelo ou sequencialmente é suficiente?')
add_question(s3_1, 'Q7.4', 'Como você imagina a "orquestração" entre agentes? Deve haver um agente coordenador central?')

s3_2 = add_section(s3, '3.2', 'Framework e Ferramentas')
add_question(s3_2, 'Q8.1', 'Sua equipe de desenvolvimento tem experiência com Python? Qual o nível?')
add_question(s3_2, 'Q8.2', 'Já utilizaram frameworks como LangGraph, AutoGen ou CrewAI?')
add_question(s3_2, 'Q8.3', 'Há preferência por framework específico? Se sim, qual e por quê?')
add_question(s3_2, 'Q8.4', 'A equipe tem experiência com LLMs? (OpenAI, Anthropic, modelos open-source)')
add_question(s3_2, 'Q8.5', 'Existe infraestrutura para executar modelos localmente ou preferem usar APIs cloud?')
add_question(s3_2, 'Q8.6', 'Model Context Protocol (MCP) é conhecido pela equipe? Há interesse em usá-lo?')

# Section 04
s4 = add_section(root, '04', 'HUMAN-IN-THE-LOOP E GOVERNANÇA')
s4_1 = add_section(s4, '4.1', 'Aprovação e Supervisão')
add_question(s4_1, 'Q9.1', 'Quais processos devem SEMPRE ter aprovação humana antes de executar?')
add_question(s4_1, 'Q9.2', 'Qual o nível de confiança mínimo para uma automação executar sem supervisão? (ex: >90%)')
add_question(s4_1, 'Q9.3', 'Como você imagina a interface de aprovação? (web app, Slack, email)')
add_question(s4_1, 'Q9.4', 'Quem serão os aprovadores? Haverá hierarquia de aprovação?')
add_question(s4_1, 'Q9.5', 'Deve haver auditoria completa de todas as ações executadas? Por quanto tempo?')

s4_2 = add_section(s4, '4.2', 'Tratamento de Erros e Rollback')
add_question(s4_2, 'Q10.1', 'O que deve acontecer quando uma automação falha? Deve notificar alguém imediatamente?')
add_question(s4_2, 'Q10.2', 'Há necessidade de rollback automático em caso de erro?')
add_question(s4_2, 'Q10.3', 'Qual o tempo máximo aceitável para resolução de um erro crítico?')
add_question(s4_2, 'Q10.4', 'Deve haver fallback para execução manual quando a automação falha?')

# Section 05
s5 = add_section(root, '05', 'EQUIPE E IMPLEMENTAÇÃO')
s5_1 = add_section(s5, '5.1', 'Recursos Humanos')
add_question(s5_1, 'Q11.1', 'Quantos desenvolvedores estarão alocados no projeto?')
add_question(s5_1, 'Q11.2', 'Qual a composição ideal do time? (backend, frontend, DevOps, ML engineers)')
add_question(s5_1, 'Q11.3', 'Há alguém com papel de Product Owner/Manager para priorizar features?')
add_question(s5_1, 'Q11.4', 'A equipe de operações estará envolvida no desenvolvimento? Em que nível?')
add_question(s5_1, 'Q11.5', 'Há necessidade de treinamento específico para a equipe?')

s5_2 = add_section(s5, '5.2', 'Cronograma e Priorização')
add_question(s5_2, 'Q12.1', 'Qual o prazo desejado para um MVP funcional? (1 mês, 3 meses, 6 meses)')
add_question(s5_2, 'Q12.2', 'Quais os 3 primeiros processos que devem ser automatizados? Por ordem de prioridade.')
add_question(s5_2, 'Q12.3', 'Existe deadline crítico de negócio que precisamos considerar?')
add_question(s5_2, 'Q12.4', 'Prefere uma implementação incremental (processo por processo) ou big bang?')
add_question(s5_2, 'Q12.5', 'Com que frequência gostaria de revisar o progresso? (weekly, bi-weekly, monthly)')

s5_3 = add_section(s5, '5.3', 'Critérios de Sucesso do MVP')
add_question(s5_3, 'Q13.1', 'O que deve estar funcionando no MVP para considerá-lo bem-sucedido?')
add_question(s5_3, 'Q13.2', 'Quantos usuários devem testar o MVP antes do rollout completo?')
add_question(s5_3, 'Q13.3', 'Qual a taxa de erro aceitável durante a fase de MVP? (ex: <5%)')
add_question(s5_3, 'Q13.4', 'O MVP deve cobrir um processo completo ou pode ser parcial?')

# Section 06
s6 = add_section(root, '06', 'SEGURANÇA E COMPLIANCE')
s6_1 = add_section(s6, '6.1', 'Segurança de Dados')
add_question(s6_1, 'Q14.1', 'Quais dados sensíveis o sistema irá manipular? (PII, financeiro, senhas)')
add_question(s6_1, 'Q14.2', 'Existe política de classificação de dados na empresa? (público, interno, confidencial)')
add_question(s6_1, 'Q14.3', 'Como devem ser armazenadas credenciais de sistemas integrados?')
add_question(s6_1, 'Q14.4', 'Há requisitos de criptografia específicos? (em trânsito, em repouso)')
add_question(s6_1, 'Q14.5', 'Quem terá acesso aos logs de auditoria?')

s6_2 = add_section(s6, '6.2', 'Compliance e Regulamentação')
add_question(s6_2, 'Q15.1', 'Há requisitos de LGPD que impactam a captura de dados de usuários?')
add_question(s6_2, 'Q15.2', 'Existe necessidade de certificações específicas? (ISO 27001, SOC2)')
add_question(s6_2, 'Q15.3', 'Há políticas de retenção de dados que devemos considerar?')
add_question(s6_2, 'Q15.4', 'A área de compliance/jurídico precisa revisar a solução antes do deploy?')

# Section 07
s7 = add_section(root, '07', 'EVOLUÇÃO E MANUTENÇÃO')
s7_1 = add_section(s7, '7.1', 'Escalabilidade')
add_question(s7_1, 'Q16.1', 'Quantos usuários simultâneos o sistema deve suportar inicialmente?')
add_question(s7_1, 'Q16.2', 'Qual o crescimento esperado de usuários nos próximos 12 meses?')
add_question(s7_1, 'Q16.3', 'Há expectativa de expandir para outras áreas/departamentos?')
add_question(s7_1, 'Q16.4', 'O sistema precisa operar 24/7 ou apenas em horário comercial?')

s7_2 = add_section(s7, '7.2', 'Manutenção e Melhoria Contínua')
add_question(s7_2, 'Q17.1', 'Como você imagina o processo de adicionar novos workflows/automações?')
add_question(s7_2, 'Q17.2', 'Haverá equipe dedicada à manutenção após o go-live?')
add_question(s7_2, 'Q17.3', 'Com que frequência os padrões detectados devem ser revisados/melhorados?')
add_question(s7_2, 'Q17.4', 'Deve haver mecanismo de feedback dos usuários sobre as automações?')
add_question(s7_2, 'Q17.5', 'Como lidar com mudanças nos sistemas integrados (novos releases, APIs depreciadas)?')

# Section 08 Observações
s8 = add_section(root, '08', 'OBSERVAÇÕES ADICIONAIS')
add_question(s8, 'Q18.1', 'Há algum aspecto crítico que não foi abordado neste questionário?')
add_question(s8, 'Q18.2', 'Existem stakeholders adicionais que devem ser consultados?')
add_question(s8, 'Q18.3', 'Há alguma restrição política ou cultural que devemos conhecer?')
add_question(s8, 'Q18.4', 'Qual sua maior preocupação sobre a implementação deste projeto?')
add_question(s8, 'Q18.5', 'Existe algum projeto similar já tentado anteriormente? Qual foi o resultado?')

# Pretty print and save to file
xml_str = minidom.parseString(tostring(root)).toprettyxml(indent="  ", encoding='utf-8')

out_path = '/mnt/data/Questionario_de_maturidade.xml'
with open(out_path, 'wb') as f:
    f.write(xml_str)

out_path

