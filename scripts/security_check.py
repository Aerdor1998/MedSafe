#!/usr/bin/env python3
"""
MedSafe Security Checker
Script para verificar problemas de segurança automaticamente
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple
import json


class SecurityChecker:
    """Verificador de segurança do MedSafe"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.issues = []
        self.warnings = []
        self.info = []

    def _should_skip_file(self, path: Path) -> bool:
        """Skip files that should not be scanned (avoid self-reporting noise)."""
        rel = str(path.relative_to(self.project_root))
        if rel == "scripts/security_check.py":
            return True
        return False
    
    def check_hardcoded_secrets(self) -> List[Dict]:
        """Verificar secrets hardcoded"""
        print("Verificando secrets hardcoded...")
        
        dangerous_patterns = [
            (r'secret_key\s*=\s*["\']change_me', 'SECRET_KEY com valor padrão'),
            (r'password\s*=\s*["\']change_me', 'PASSWORD com valor padrão'),
            (r'jwt_secret\s*=\s*["\']change_me', 'JWT_SECRET com valor padrão'),
            (r'api_key\s*=\s*["\'][^"\']{20,}["\']', 'API_KEY hardcoded'),
            (r'SECRET_KEY\s*=\s*["\']change_me', 'SECRET_KEY em env com valor padrão'),
        ]
        
        issues_found = []
        
        # Verificar arquivos Python
        for py_file in self.project_root.rglob('*.py'):
            if 'venv' in str(py_file) or '__pycache__' in str(py_file):
                continue
            if self._should_skip_file(py_file):
                continue
            
            try:
                content = py_file.read_text()
                for pattern, description in dangerous_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        issues_found.append({
                            'file': str(py_file.relative_to(self.project_root)),
                            'line': line_num,
                            'issue': description,
                            'severity': 'CRITICAL'
                        })
            except Exception as e:
                pass
        
        # Verificar docker-compose.yml
        compose_file = self.project_root / 'docker-compose.yml'
        if compose_file.exists():
            content = compose_file.read_text()
            if 'change_me' in content.lower():
                issues_found.append({
                    'file': 'docker-compose.yml',
                    'line': 0,
                    'issue': 'Credenciais padrão em docker-compose',
                    'severity': 'CRITICAL'
                })
        
        self.issues.extend(issues_found)
        return issues_found
    
    def check_sql_injection(self) -> List[Dict]:
        """Verificar possíveis SQL Injections"""
        print("Verificando SQL Injection...")
        
        sql_patterns = [
            (r'execute\(text\(f["\']', 'SQL query com f-string'),
            (r'execute\(["\'].*\{.*\}.*["\']', 'SQL query com interpolação'),
            (r'raw\(["\'].*%s.*["\'].*%', 'Raw SQL com interpolação'),
        ]
        
        issues_found = []
        
        for py_file in self.project_root.rglob('*.py'):
            if 'venv' in str(py_file) or '__pycache__' in str(py_file):
                continue
            if self._should_skip_file(py_file):
                continue
            
            try:
                content = py_file.read_text()
                for pattern, description in sql_patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        issues_found.append({
                            'file': str(py_file.relative_to(self.project_root)),
                            'line': line_num,
                            'issue': description,
                            'severity': 'CRITICAL'
                        })
            except Exception:
                pass
        
        self.issues.extend(issues_found)
        return issues_found
    
    def check_cors_config(self) -> List[Dict]:
        """Verificar configuração de CORS"""
        print("Verificando configuração CORS...")
        
        issues_found = []
        
        for py_file in self.project_root.rglob('*.py'):
            if 'venv' in str(py_file):
                continue
            if self._should_skip_file(py_file):
                continue
            # Ignore test-only configs (wildcards are acceptable in unit tests)
            if "backend/tests/" in str(py_file).replace("\\", "/"):
                continue
            
            try:
                content = py_file.read_text()
                
                # Verificar CORS = "*"
                if re.search(r'allowed_origins.*\[.*["\*"].*\]', content):
                    line_num = re.search(r'allowed_origins.*\[.*["\*"].*\]', content).start()
                    line_num = content[:line_num].count('\n') + 1
                    issues_found.append({
                        'file': str(py_file.relative_to(self.project_root)),
                        'line': line_num,
                        'issue': 'CORS configurado com wildcard "*"',
                        'severity': 'HIGH'
                    })
            except Exception:
                pass
        
        self.warnings.extend(issues_found)
        return issues_found
    
    def check_file_upload_security(self) -> List[Dict]:
        """Verificar segurança de upload de arquivos"""
        print("Verificando segurança de upload...")
        
        issues_found = []
        
        for py_file in self.project_root.rglob('*.py'):
            if 'venv' in str(py_file):
                continue
            if self._should_skip_file(py_file):
                continue
            
            try:
                content = py_file.read_text()
                
                # Verificar se valida apenas Content-Type
                if 'file.content_type' in content and 'magic' not in content:
                    issues_found.append({
                        'file': str(py_file.relative_to(self.project_root)),
                        'line': 0,
                        'issue': 'Upload valida apenas Content-Type (inseguro)',
                        'severity': 'CRITICAL'
                    })
                
                # Verificar paths previsíveis
                if re.search(r'/tmp/.*\{.*filename', content):
                    line_num = re.search(r'/tmp/.*\{.*filename', content).start()
                    line_num = content[:line_num].count('\n') + 1
                    issues_found.append({
                        'file': str(py_file.relative_to(self.project_root)),
                        'line': line_num,
                        'issue': 'Path de upload previsível (Path Traversal)',
                        'severity': 'CRITICAL'
                    })
            except Exception:
                pass
        
        self.issues.extend(issues_found)
        return issues_found
    
    def check_rate_limiting(self) -> List[Dict]:
        """Verificar se há rate limiting"""
        print("Verificando rate limiting...")
        
        findings = []
        
        # Consider rate limiting implemented if SlowAPI limiter module exists and is wired in middleware.
        rate_limit_module = self.project_root / 'backend' / 'app' / 'middleware' / 'rate_limit.py'
        middleware_init = self.project_root / 'backend' / 'app' / 'middleware' / '__init__.py'
        if not rate_limit_module.exists():
            findings.append({
                'file': 'backend/app/middleware/rate_limit.py',
                'line': 0,
                'issue': 'Rate limiting module ausente',
                'severity': 'HIGH'
            })
        else:
            if middleware_init.exists():
                content = middleware_init.read_text()
                if 'RateLimitExceeded' not in content or 'rate_limit_exceeded_handler' not in content:
                    findings.append({
                        'file': 'backend/app/middleware/__init__.py',
                        'line': 0,
                        'issue': 'Rate limiting não parece estar registrado no middleware stack',
                        'severity': 'HIGH'
                    })
        
        self.warnings.extend(findings)
        return findings
    
    def check_dependencies(self) -> List[Dict]:
        """Verificar dependências desatualizadas ou vulneráveis"""
        print("Verificando dependências...")
        
        findings = []
        
        req_file = self.project_root / 'requirements.txt'
        if req_file.exists():
            content = req_file.read_text()
            
            # Versões antigas conhecidas
            old_versions = {
                'fastapi>=0.104': 'FastAPI tem versão mais recente (0.115+)',
                'uvicorn>=0.24': 'Uvicorn tem versão mais recente (0.32+)',
            }
            
            for pattern, message in old_versions.items():
                if pattern in content:
                    findings.append({
                        'file': 'requirements.txt',
                        'line': 0,
                        'issue': message,
                        'severity': 'INFO'
                    })
        
        self.info.extend(findings)
        return findings
    
    def check_docker_security(self) -> List[Dict]:
        """Verificar segurança do Docker"""
        print("Verificando configuração Docker...")
        
        findings = []
        
        dockerfile = self.project_root / 'Dockerfile'
        if dockerfile.exists():
            content = dockerfile.read_text()
            
            # Verificar se roda como root
            if 'USER' not in content:
                findings.append({
                    'file': 'Dockerfile',
                    'line': 0,
                    'issue': 'Container roda como root (inseguro)',
                    'severity': 'HIGH'
                })
            
            # Verificar imagem base pesada
            if 'FROM ubuntu' in content:
                findings.append({
                    'file': 'Dockerfile',
                    'line': 0,
                    'issue': 'Imagem base pesada (considere python:slim)',
                    'severity': 'INFO'
                })
        
        self.warnings.extend([f for f in findings if f['severity'] == 'HIGH'])
        self.info.extend([f for f in findings if f['severity'] == 'INFO'])
        return findings
    
    def check_env_file(self) -> List[Dict]:
        """Verificar arquivo .env"""
        print("Verificando arquivo .env...")
        
        findings = []
        
        env_file = self.project_root / '.env'
        if env_file.exists():
            findings.append({
                'file': '.env',
                'line': 0,
                'issue': 'Arquivo .env existe (verificar se está no .gitignore)',
                'severity': 'INFO'
            })
            
            content = env_file.read_text()
            if 'change_me' in content.lower():
                findings.append({
                    'file': '.env',
                    'line': 0,
                    'issue': 'Arquivo .env contém valores padrão',
                    'severity': 'CRITICAL'
                })
        else:
            findings.append({
                'file': '.env',
                'line': 0,
                'issue': 'Arquivo .env não existe (criar baseado em .env.example)',
                'severity': 'INFO'
            })
        
        self.info.extend([f for f in findings if f['severity'] == 'INFO'])
        self.issues.extend([f for f in findings if f['severity'] == 'CRITICAL'])
        return findings
    
    def check_gitignore(self) -> List[Dict]:
        """Verificar .gitignore"""
        print("Verificando .gitignore...")
        
        findings = []
        
        gitignore = self.project_root / '.gitignore'
        if gitignore.exists():
            content = gitignore.read_text()
            
            required_entries = [
                ('.env', 'Variáveis de ambiente'),
                ('*.db', 'Bancos de dados'),
                ('__pycache__', 'Cache Python'),
            ]
            
            for entry, description in required_entries:
                if entry not in content:
                    findings.append({
                        'file': '.gitignore',
                        'line': 0,
                        'issue': f'Faltando entrada: {entry} ({description})',
                        'severity': 'INFO'
                    })
        else:
            findings.append({
                'file': '.gitignore',
                'line': 0,
                'issue': 'Arquivo .gitignore não existe',
                'severity': 'HIGH'
            })
        
        self.info.extend(findings)
        return findings
    
    def run_all_checks(self) -> Dict:
        """Executar todas as verificações"""
        print("=" * 60)
        print("🛡️  MedSafe Security Checker")
        print("=" * 60)
        print()
        
        self.check_hardcoded_secrets()
        self.check_sql_injection()
        self.check_cors_config()
        self.check_file_upload_security()
        self.check_rate_limiting()
        self.check_dependencies()
        self.check_docker_security()
        self.check_env_file()
        self.check_gitignore()
        
        return {
            'critical': [i for i in self.issues if i.get('severity') == 'CRITICAL'],
            'high': [i for i in self.warnings if i.get('severity') == 'HIGH'],
            'info': self.info
        }
    
    def print_report(self, results: Dict):
        """Imprimir relatório"""
        print()
        print("=" * 60)
        print("RESULTADO DA ANÁLISE")
        print("=" * 60)
        print()
        
        critical = results['critical']
        high = results['high']
        info = results['info']
        
        print(f"🔴 CRÍTICOS:    {len(critical)}")
        print(f"🟡 ALTOS:       {len(high)}")
        print(f"ℹ️  INFORMATIVOS: {len(info)}")
        print()
        
        if critical:
            print("🔴 PROBLEMAS CRÍTICOS:")
            print("-" * 60)
            for issue in critical:
                print(f"  📁 {issue['file']}:{issue.get('line', 0)}")
                print(f"     {issue['issue']}")
                print()
        
        if high:
            print("🟡 PROBLEMAS ALTOS:")
            print("-" * 60)
            for issue in high:
                print(f"  📁 {issue['file']}:{issue.get('line', 0)}")
                print(f"     {issue['issue']}")
                print()
        
        if info:
            print("ℹ️  INFORMAÇÕES:")
            print("-" * 60)
            for item in info[:5]:  # Mostrar apenas primeiros 5
                print(f"  📁 {item['file']}")
                print(f"     {item['issue']}")
            if len(info) > 5:
                print(f"  ... e mais {len(info) - 5} itens")
            print()
        
        print("=" * 60)
        
        # Status final
        if critical:
            print("STATUS: NÃO SEGURO PARA PRODUÇÃO")
            print(f"   {len(critical)} problema(s) crítico(s) encontrado(s)")
            return 1
        elif high:
            print(" STATUS: REQUER ATENÇÃO")
            print(f"   {len(high)} problema(s) de alta prioridade")
            return 1
        else:
            print("STATUS: VERIFICAÇÕES BÁSICAS OK")
            print("   Considere executar ferramentas adicionais:")
            print("   - bandit -r backend/")
            print("   - safety check")
            return 0
    
    def save_report(self, results: Dict, output_file: Path):
        """Salvar relatório em JSON"""
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n📄 Relatório salvo em: {output_file}")


def main():
    """Função principal"""
    # Detectar diretório do projeto
    current_dir = Path.cwd()
    
    # Verificar se estamos no diretório do projeto
    if not (current_dir / 'backend').exists():
        print("Erro: Execute este script do diretório raiz do projeto MedSafe")
        sys.exit(1)
    
    checker = SecurityChecker(current_dir)
    results = checker.run_all_checks()
    exit_code = checker.print_report(results)
    
    # Salvar relatório
    output_file = current_dir / 'security_check_results.json'
    checker.save_report(results, output_file)
    
    sys.exit(exit_code)


if __name__ == '__main__':
    main()

