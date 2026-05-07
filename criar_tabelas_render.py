import psycopg2
from psycopg2.extras import RealDictCursor

# Conexão com o banco do Render
url = "postgresql://ifpi_user:dJZKgKnWJVM2GZzG32tA61HbVLXvNF4c@dpg-d7sfrr77f7vs73d8r0gg-a.virginia-postgres.render.com/ifpi_aulas_kdt1"

try:
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    cursor = conn.cursor()
    print("✅ Conectado ao banco com sucesso!")
    
    # Criar tabela usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome_completo VARCHAR(100) NOT NULL,
            usuario VARCHAR(50) UNIQUE NOT NULL,
            senha VARCHAR(32) NOT NULL,
            tipo VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            email VARCHAR(100)
        )
    """)
    print("✅ Tabela 'usuarios' criada")
    
    # Criar tabela professores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS professores (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER REFERENCES usuarios(id),
            disciplina VARCHAR(100),
            tipo VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ Tabela 'professores' criada")
    
    # Criar tabela cursos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cursos (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(100) NOT NULL,
            turno VARCHAR(20),
            ativo INTEGER DEFAULT 1,
            tipo VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ Tabela 'cursos' criada")
    
    # Criar tabela turmas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS turmas (
            id SERIAL PRIMARY KEY,
            curso_id INTEGER REFERENCES cursos(id),
            nome VARCHAR(100),
            serie VARCHAR(10),
            modulo VARCHAR(10),
            turma VARCHAR(10),
            ativo INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ Tabela 'turmas' criada")
    
    # Inserir usuário admin
    cursor.execute("""
        INSERT INTO usuarios (nome_completo, usuario, senha, tipo) 
        VALUES ('Administrador', 'admin', '21232f297a57a5a743894a0e4a801fc3', 'admin')
        ON CONFLICT (usuario) DO NOTHING
    """)
    print("✅ Usuário 'admin' inserido")
    
    # Inserir cursos básicos
    cursor.execute("""
        INSERT INTO cursos (nome, turno, ativo, tipo) VALUES
        ('Técnico em Informática integrado ao médio', 'manha', 1, 'tecnico'),
        ('Técnico em Administração integrado ao médio', 'manha', 1, 'tecnico'),
        ('Técnico em Meio Ambiente integrado ao médio', 'manha', 1, 'tecnico'),
        ('Gastronomia', 'noite', 1, 'tecnico')
        ON CONFLICT (nome) DO NOTHING
    """)
    print("✅ Cursos básicos inseridos")
    
    conn.commit()
    print("\n🎉 Todas as tabelas foram criadas com sucesso!")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Erro: {e}")
