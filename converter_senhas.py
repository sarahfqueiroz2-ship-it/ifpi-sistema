#!/usr/bin/env python3
"""Script para converter senhas MD5 para bcrypt"""

import bcrypt
import psycopg2
import os
import sys
import ssl

def hash_senha(senha):
    """Gera hash bcrypt da senha"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(senha.encode('utf-8'), salt).decode('utf-8')

def main():
    # Conectar no banco de dados
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("❌ DATABASE_URL não encontrada!")
        print("   Execute assim: DATABASE_URL='sua_url' python3 converter_senhas.py")
        sys.exit(1)
    
    print(f"📦 Conectando ao banco...")
    
    # Adicionar parâmetro SSL para o Render
    conn = psycopg2.connect(database_url, sslmode='require')
    cursor = conn.cursor()
    
    # Buscar usuários
    cursor.execute("SELECT id, usuario, senha FROM usuarios")
    usuarios = cursor.fetchall()
    
    print(f"📋 Encontrados {len(usuarios)} usuários")
    
    convertidos = 0
    erros = 0
    
    for user in usuarios:
        user_id, usuario, senha_atual = user
        
        # Verificar se a senha está em MD5 (32 caracteres hex)
        if len(senha_atual) == 32 and all(c in '0123456789abcdef' for c in senha_atual.lower()):
            print(f"\n⚠️ Usuário '{usuario}' (ID: {user_id}) tem senha MD5")
            print(f"   Para converter, você precisa saber a senha original")
            print(f"   Use a opção 'Esqueci minha senha' no site")
            erros += 1
        else:
            print(f"✅ Usuário '{usuario}' já está seguro (não é MD5)")
            convertidos += 1
    
    print(f"\n" + "="*50)
    print(f"RESUMO:")
    print(f"  ✅ Usuários OK: {convertidos}")
    print(f"  ⚠️ Usuários com MD5: {erros}")
    print(f"\n📌 Recomendação:")
    print(f"  Peça para os usuários com MD5 usarem a função")
    print(f"  'Esqueci minha senha' para redefinir.")
    print("="*50)
    
    conn.close()

if __name__ == '__main__':
    main()

