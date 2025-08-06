"""
Configuração e modelos do banco de dados SQLite
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import json

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///../data/medsafe.db")
IS_POSTGRES = DATABASE_URL.startswith("postgres")

def get_db_connection():
    """Obter conexão com o banco de dados"""
    if IS_POSTGRES:
        conn = sqlite3.connect(DATABASE_URL) # Placeholder, a conexão real seria com psycopg2
    else:
        conn = sqlite3.connect(DATABASE_URL.replace("sqlite:///", ""))
    
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializar banco de dados com tabelas necessárias"""
    
    # Se for SQLite, garantir que o diretório exista
    if not IS_POSTGRES:
        os.makedirs("../data", exist_ok=True)
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela de medicamentos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active_ingredient TEXT NOT NULL,
            therapeutic_class TEXT,
            anvisa_registry TEXT,
            contraindications TEXT, -- JSON
            interactions TEXT, -- JSON
            adverse_reactions TEXT, -- JSON
            dosage_forms TEXT, -- JSON
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabela de sessões para auditoria
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            patient_data TEXT, -- JSON
            medication_name TEXT,
            analysis_result TEXT, -- JSON
            risk_level TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT
        )
    """)
    
    # Tabela de logs de eventos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            event_type TEXT NOT NULL,
            event_data TEXT, -- JSON
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT
        )
    """)
    
    # Tabela de interações medicamentosas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drug_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_a TEXT NOT NULL,
            drug_b TEXT NOT NULL,
            interaction_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            mechanism TEXT,
            clinical_effect TEXT,
            recommendation TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabela de contraindicações por condição
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contraindications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication TEXT NOT NULL,
            condition_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT,
            recommendation TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    
    # Popular com dados iniciais
    populate_initial_data()

def get_db_connection():
    """Obter conexão com o banco de dados"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Para acessar colunas por nome
    return conn

def populate_initial_data():
    """Popular banco com dados iniciais de medicamentos comuns"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verificar se já tem dados
    cursor.execute("SELECT COUNT(*) FROM medications")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return
    
    # Dados de medicamentos comuns baseados em diretrizes ANVISA
    medications_data = [
        {
            "name": "Dipirona Sódica",
            "active_ingredient": "dipirona sódica",
            "therapeutic_class": "Analgésico/Antipirético",
            "anvisa_registry": "1234567890",
            "contraindications": json.dumps([
                "Hipersensibilidade ao princípio ativo",
                "Deficiência da glicose-6-fosfato desidrogenase",
                "Porfiria aguda intermitente",
                "Gravidez (3º trimestre)"
            ]),
            "interactions": json.dumps([
                {"drug": "varfarina", "effect": "potencialização anticoagulante"},
                {"drug": "ciclosporina", "effect": "redução dos níveis séricos"}
            ]),
            "adverse_reactions": json.dumps([
                {"reaction": "agranulocitose", "frequency": "rara"},
                {"reaction": "reações alérgicas", "frequency": "ocasional"}
            ])
        },
        {
            "name": "Paracetamol",
            "active_ingredient": "paracetamol",
            "therapeutic_class": "Analgésico/Antipirético",
            "anvisa_registry": "1234567891",
            "contraindications": json.dumps([
                "Hipersensibilidade ao paracetamol",
                "Insuficiência hepática grave"
            ]),
            "interactions": json.dumps([
                {"drug": "varfarina", "effect": "potencialização anticoagulante"},
                {"drug": "álcool", "effect": "hepatotoxicidade"}
            ]),
            "adverse_reactions": json.dumps([
                {"reaction": "hepatotoxicidade", "frequency": "rara em doses terapêuticas"},
                {"reaction": "reações cutâneas", "frequency": "rara"}
            ])
        },
        {
            "name": "Ibuprofeno",
            "active_ingredient": "ibuprofeno",
            "therapeutic_class": "Anti-inflamatório não esteroidal",
            "anvisa_registry": "1234567892",
            "contraindications": json.dumps([
                "Hipersensibilidade a AINEs",
                "Úlcera péptica ativa",
                "Insuficiência cardíaca grave",
                "Gravidez (3º trimestre)"
            ]),
            "interactions": json.dumps([
                {"drug": "varfarina", "effect": "aumento risco sangramento"},
                {"drug": "lítio", "effect": "aumento dos níveis de lítio"},
                {"drug": "metotrexato", "effect": "toxicidade do metotrexato"}
            ]),
            "adverse_reactions": json.dumps([
                {"reaction": "distúrbios gastrointestinais", "frequency": "comum"},
                {"reaction": "retenção de líquidos", "frequency": "ocasional"}
            ])
        }
    ]
    
    for med_data in medications_data:
        cursor.execute("""
            INSERT INTO medications 
            (name, active_ingredient, therapeutic_class, anvisa_registry, 
             contraindications, interactions, adverse_reactions)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            med_data["name"],
            med_data["active_ingredient"],
            med_data["therapeutic_class"],
            med_data["anvisa_registry"],
            med_data["contraindications"],
            med_data["interactions"],
            med_data["adverse_reactions"]
        ))
    
    # Dados de interações comuns
    interactions_data = [
        {
            "drug_a": "varfarina",
            "drug_b": "paracetamol",
            "interaction_type": "farmacodinâmica",
            "severity": "moderada",
            "mechanism": "potencialização do efeito anticoagulante",
            "clinical_effect": "aumento do risco de sangramento",
            "recommendation": "monitorar INR, ajustar dose se necessário",
            "source": "ANVISA RDC 47/2009"
        },
        {
            "drug_a": "varfarina",
            "drug_b": "ibuprofeno",
            "interaction_type": "farmacodinâmica",
            "severity": "alta",
            "mechanism": "inibição da agregação plaquetária + anticoagulação",
            "clinical_effect": "risco significativo de sangramento",
            "recommendation": "evitar uso concomitante, preferir alternativas",
            "source": "OMS Guidelines"
        }
    ]
    
    for interaction in interactions_data:
        cursor.execute("""
            INSERT INTO drug_interactions 
            (drug_a, drug_b, interaction_type, severity, mechanism, 
             clinical_effect, recommendation, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            interaction["drug_a"],
            interaction["drug_b"],
            interaction["interaction_type"],
            interaction["severity"],
            interaction["mechanism"],
            interaction["clinical_effect"],
            interaction["recommendation"],
            interaction["source"]
        ))
    
    # Dados de contraindicações por condição
    contraindications_data = [
        {
            "medication": "ibuprofeno",
            "condition_type": "úlcera péptica",
            "severity": "absoluta",
            "description": "AINEs podem agravar úlceras e causar perfuração",
            "recommendation": "contraindicado, usar alternativas",
            "source": "ANVISA RDC 47/2009"
        },
        {
            "medication": "dipirona",
            "condition_type": "deficiência G6PD",
            "severity": "absoluta",
            "description": "risco de anemia hemolítica",
            "recommendation": "contraindicado absolutamente",
            "source": "OMS Guidelines"
        }
    ]
    
    for contraind in contraindications_data:
        cursor.execute("""
            INSERT INTO contraindications 
            (medication, condition_type, severity, description, recommendation, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            contraind["medication"],
            contraind["condition_type"],
            contraind["severity"],
            contraind["description"],
            contraind["recommendation"],
            contraind["source"]
        ))
    
    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado com dados básicos")

def log_session(session_id: str, patient_data: dict, medication_name: str, 
                analysis_result: dict, risk_level: str, ip_address: str = None):
    """Registrar sessão para auditoria"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO sessions 
        (id, patient_data, medication_name, analysis_result, risk_level, ip_address)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        json.dumps(patient_data),
        medication_name,
        json.dumps(analysis_result),
        risk_level,
        ip_address
    ))
    
    conn.commit()
    conn.close()

def log_event(session_id: str, event_type: str, event_data: dict, ip_address: str = None):
    """Registrar evento para auditoria"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO audit_logs 
        (session_id, event_type, event_data, ip_address)
        VALUES (?, ?, ?, ?)
    """, (
        session_id,
        event_type,
        json.dumps(event_data),
        ip_address
    ))
    
    conn.commit()
    conn.close()