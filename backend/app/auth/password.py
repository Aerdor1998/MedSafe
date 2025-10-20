"""
Gerenciamento de senhas com bcrypt
"""

from passlib.context import CryptContext

# Contexto de criptografia
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Criar hash de senha usando bcrypt
    
    Args:
        password: Senha em texto plano
        
    Returns:
        Hash da senha
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verificar se a senha corresponde ao hash
    
    Args:
        plain_password: Senha em texto plano
        hashed_password: Hash da senha armazenado
        
    Returns:
        True se a senha é válida, False caso contrário
    """
    return pwd_context.verify(plain_password, hashed_password)


