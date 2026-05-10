import os
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pymysql
from datetime import datetime, timedelta
import traceback
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CORS(app)

# ================== FUNÇÕES DE SEGURANÇA ==================
def hash_senha(senha):
    """Gera hash bcrypt da senha"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(senha.encode('utf-8'), salt).decode('utf-8')

def verificar_senha(senha, hash_armazenado):
    """Verifica se a senha corresponde ao hash"""
    return bcrypt.checkpw(senha.encode('utf-8'), hash_armazenado.encode('utf-8'))

# ================== DEBUG COMPLETO ==================
import sys
import traceback

# Habilitar debug detalhado
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['DEBUG'] = True

# Função para log de erros
def log_erro(rota, erro):
    print(f"\n{'='*70}")
    print(f"❌ ERRO NA ROTA: {rota}")
    print(f"📝 Mensagem: {str(erro)}")
    print(f"📍 Detalhes:")
    traceback.print_exc()
    print(f"{'='*70}\n")
# ================== CONFIGURAÇÃO DE E-MAIL ==================
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',  # Altere conforme seu e-mail
    'smtp_port': 587,
    'email_remetente': 'seuemail@gmail.com',  # Coloque SEU e-mail
    'email_senha': 'sua_senha'  # Coloque SUA senha (ou senha de app)
}

# ================== CONFIGURAÇÃO DO BANCO ==================

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'ifpi2026',
    'database': 'ifpi_aulas',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
    # Verifica se está no Render (usa DATABASE_URL do PostgreSQL)
    if 'DATABASE_URL' in os.environ:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        url = os.environ['DATABASE_URL']
        return psycopg2.connect(url, cursor_factory=RealDictCursor)
    else:
        # Conexão local com MySQL (computador do professor)
        import pymysql
        return pymysql.connect(
            host='localhost',
            user='root',
            password="Ifpi@2026#Segura",
            database='ifpi_aulas',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
# ================== FUNÇÕES AUXILIARES ==================

def converter_timedelta_para_string(valor):
    if valor is None:
        return None
    if isinstance(valor, timedelta):
        total_seconds = int(valor.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    if hasattr(valor, 'strftime'):
        return valor.strftime('%H:%M:%S')
    return str(valor)

def serializar_registro(registro):
    if not registro:
        return None
    registro_dict = dict(registro)
    for key, value in registro_dict.items():
        if isinstance(value, timedelta):
            registro_dict[key] = converter_timedelta_para_string(value)
    return registro_dict

def get_semana_atual():
    hoje = datetime.now().date()
    return hoje - timedelta(days=hoje.weekday())

def get_professor_id_by_usuario_id(usuario_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM professores WHERE usuario_id = %s", (usuario_id,))
        result = cursor.fetchone()
        conn.close()
        return result['id'] if result else None
    except Exception as e:
        print(f"Erro ao buscar professor_id: {e}")
        return None

def get_tipo_usuario(usuario_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT tipo FROM usuarios WHERE id = %s", (usuario_id,))
        result = cursor.fetchone()
        conn.close()
        return result['tipo'] if result else None
    except Exception as e:
        print(f"Erro ao buscar tipo do usuário: {e}")
        return None

def get_nome_professor(professor_id):
    if not professor_id:
        return "Coordenador"
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.nome_completo 
            FROM professores p
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE p.id = %s
        """, (professor_id,))
        result = cursor.fetchone()
        conn.close()
        return result['nome_completo'] if result else "Professor"
    except Exception as e:
        print(f"Erro ao buscar nome do professor: {e}")
        return "Professor"

def get_dia_nome(dia_num):
    dias = {1: 'Segunda-feira', 2: 'Terça-feira', 3: 'Quarta-feira', 4: 'Quinta-feira', 5: 'Sexta-feira', 6: 'Sábado'}
    return dias.get(dia_num, 'Dia')


# ================== FUNÇÃO DE AUDITORIA ==================
def registrar_log(usuario_id, usuario_nome, acao, tabela=None, registro_id=None, dados_antes=None, dados_depois=None):
    try:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs_auditoria 
            (usuario_id, usuario_nome, acao, tabela, registro_id, dados_antes, dados_depois, ip, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (usuario_id, usuario_nome, acao, tabela, registro_id, dados_antes, dados_depois, ip, user_agent))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao registrar log: {e}")

def criar_tabelas():
    """Cria as tabelas necessárias no PostgreSQL (Render)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            usuario VARCHAR(100) UNIQUE NOT NULL,
            senha VARCHAR(100) NOT NULL,
            nome_completo VARCHAR(200) NOT NULL,
            tipo VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabela professores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS professores (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER REFERENCES usuarios(id),
            disciplina VARCHAR(200),
            tipo VARCHAR(50)
        )
    """)
    
    # Tabela cursos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cursos (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(200) NOT NULL,
            turno VARCHAR(50),
            tipo VARCHAR(50),
            ativo BOOLEAN DEFAULT TRUE
        )
    """)
    
    # Tabela turmas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS turmas (
            id SERIAL PRIMARY KEY,
            curso_id INTEGER REFERENCES cursos(id),
            serie VARCHAR(50),
            modulo VARCHAR(50),
            turma VARCHAR(50),
            ativo BOOLEAN DEFAULT TRUE
        )
    """)
    
    # Tabela registros
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id SERIAL PRIMARY KEY,
            professor_id INTEGER REFERENCES professores(id),
            professor_nome VARCHAR(200),
            data DATE NOT NULL,
            tipo VARCHAR(50),
            curso_id INTEGER REFERENCES cursos(id),
            serie VARCHAR(50),
            quantidade INTEGER,
            horario_inicio TIME,
            horario_fim TIME,
            disciplina VARCHAR(200),
            observacoes TEXT,
            tipo_professor VARCHAR(50)
        )
    """)
    
    # Tabela calendario_marcacoes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calendario_marcacoes (
            id SERIAL PRIMARY KEY,
            turma_id INTEGER NOT NULL,
            dia_semana INTEGER NOT NULL,
            horario_id INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'normal',
            professor_id INTEGER,
            dono_original_id INTEGER,
            semana_inicio DATE NOT NULL,
            data_marcacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(turma_id, dia_semana, horario_id, semana_inicio)
        )
    """)
    
    # Tabela notificacoes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notificacoes (
            id SERIAL PRIMARY KEY,
            tipo VARCHAR(50),
            turma_id INTEGER,
            turma_nome VARCHAR(100),
            curso_nome VARCHAR(100),
            dia_semana INTEGER,
            dia_nome VARCHAR(50),
            horario_id INTEGER,
            professor_origem_id INTEGER,
            professor_origem_nome VARCHAR(200),
            professor_destino_id INTEGER,
            status VARCHAR(20) DEFAULT 'pendente',
            mensagem TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            lida_em TIMESTAMP
        )
    """)
    
    # Tabela recuperacao_senha
      # Tabela recuperacao_senha
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recuperacao_senha (
            id SERIAL PRIMARY KEY,
            email VARCHAR(100) NOT NULL,
            codigo VARCHAR(10) NOT NULL,
            expira_em TIMESTAMP NOT NULL,
            usado INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ Tabelas verificadas/criadas com sucesso!")
# ================== ROTAS ESTÁTICAS ==================

@app.route('/')
@app.route('/<path:filename>')
def frontend(filename='login.html'):
    # Usa a mesma pasta do app.py
    import os
    return send_from_directory('.', filename)
# ================== ROTAS DE AUTENTICAÇÃO ==================

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        usuario = data.get('usuario')
        senha = data.get('senha')
        
        print(f"=== TENTATIVA DE LOGIN ===")
        print(f"Usuário: {usuario}")
        print(f"Senha digitada: {senha}")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT u.*, p.disciplina, p.tipo as tipo_professor FROM usuarios u LEFT JOIN professores p ON u.id = p.usuario_id WHERE u.usuario = %s",
            (usuario,)
        )
        user = cursor.fetchone()
        conn.close()

        if not user:
            print(f"❌ Usuário {usuario} não encontrado!")
            return jsonify({'success': False, 'message': 'Usuário ou senha incorretos'}), 401

        print(f"✅ Usuário encontrado: {user['usuario']}")
        print(f"Hash no banco: {user['senha'][:30]}...")
        print(f"Tipo do hash: {'bcrypt' if user['senha'].startswith('$2b$') else 'MD5'}")

        # Verifica a senha
        if user['senha'].startswith('$2b$'):
            print("Verificando com bcrypt...")
            if bcrypt.checkpw(senha.encode('utf-8'), user['senha'].encode('utf-8')):
                print("✅ Senha bcrypt OK!")
            else:
                print("❌ Senha bcrypt incorreta!")
                return jsonify({'success': False, 'message': 'Usuário ou senha incorretos'}), 401
        else:
            print("Verificando com MD5...")
            import hashlib
            senha_md5 = hashlib.md5(senha.encode()).hexdigest()
            print(f"MD5 gerado: {senha_md5}")
            print(f"MD5 no banco: {user['senha']}")
            if user['senha'] != senha_md5:
                print("❌ Senha MD5 incorreta!")
                return jsonify({'success': False, 'message': 'Usuário ou senha incorretos'}), 401
            
            print("✅ Senha MD5 OK! Convertendo para bcrypt...")
            nova_senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt(12)).decode()
            conn2 = get_db_connection()
            cursor2 = conn2.cursor()
            cursor2.execute("UPDATE usuarios SET senha = %s WHERE id = %s", (nova_senha_hash, user['id']))
            conn2.commit()
            conn2.close()
            print("✅ Senha convertida para bcrypt!")

            registrar_log(user['id'], user['nome_completo'], 'LOGIN', 'usuarios', user['id'])


        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'nome': user['nome_completo'],
                'tipo': user['tipo'],
                'disciplina': user.get('disciplina'),
                'tipo_professor': user.get('tipo_professor')
            }
        })

    except Exception as e:
        print(f"❌ ERRO: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Erro no servidor'}), 500

# ================== ROTAS DE REGISTROS ==================

@app.route('/registros', methods=['GET'])
def listar_registros():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, c.nome as curso_nome
            FROM registros r
            LEFT JOIN cursos c ON r.curso_id = c.id
            ORDER BY r.data DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        registros = []
        for row in rows:
            reg = dict(row)
            for key, value in reg.items():
                if isinstance(value, (timedelta,)):
                    reg[key] = str(value)
                elif hasattr(value, 'isoformat'):
                    reg[key] = value.isoformat()
                elif isinstance(value, bytes):
                    reg[key] = value.decode('utf-8')
            registros.append(reg)

        return jsonify({'registros': registros})
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return jsonify({'registros': [], 'erro': str(e)}), 500
        
@app.route('/registros_com_horarios', methods=['GET'])
def listar_registros_com_horarios():
    try:
        professor_id = request.args.get('professor_id', type=int)

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT r.*, c.nome as curso_nome
            FROM registros r
            JOIN cursos c ON r.curso_id = c.id
        """
        
        if professor_id:
            query += " WHERE r.professor_id = %s"
            params = (professor_id,)
        else:
            params = ()
        
        query += " ORDER BY r.data DESC"
        
        cursor.execute(query, params)
        registros = cursor.fetchall()
        
        # Processar cada registro
        resultados = []
        for reg in registros:
            # Converter timedelta para string
            reg_dict = dict(reg)
            
            # Converter horario_inicio se for timedelta
            if reg_dict.get('horario_inicio'):
                if isinstance(reg_dict['horario_inicio'], timedelta):
                    total_seconds = int(reg_dict['horario_inicio'].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    reg_dict['horario_inicio'] = f"{hours:02d}:{minutes:02d}:00"
                else:
                    reg_dict['horario_inicio'] = str(reg_dict['horario_inicio'])[:5]
            
            if reg_dict.get('horario_fim'):
                if isinstance(reg_dict['horario_fim'], timedelta):
                    total_seconds = int(reg_dict['horario_fim'].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    reg_dict['horario_fim'] = f"{hours:02d}:{minutes:02d}:00"
                else:
                    reg_dict['horario_fim'] = str(reg_dict['horario_fim'])[:5]
            
            # Buscar horários múltiplos
            cursor.execute("""
                SELECT horario_inicio, horario_fim, ordem
                FROM registro_horarios
                WHERE registro_id = %s
                ORDER BY ordem
            """, (reg['id'],))
            
            horarios = cursor.fetchall()
            
            if horarios:
                horarios_str = []
                for h in horarios:
                    inicio = str(h['horario_inicio'])[:5] if h['horario_inicio'] else ''
                    fim = str(h['horario_fim'])[:5] if h['horario_fim'] else ''
                    horarios_str.append(f"{inicio} - {fim}")
                reg_dict['horarios'] = ', '.join(horarios_str)
            else:
                # Usar horario único
                if reg_dict.get('horario_inicio') and reg_dict.get('horario_fim'):
                    reg_dict['horarios'] = f"{reg_dict['horario_inicio']} - {reg_dict['horario_fim']}"
                else:
                    reg_dict['horarios'] = None
            
            resultados.append(reg_dict)
        
        conn.close()

        return jsonify({'registros': resultados, 'success': True})

    except Exception as e:
        print("Erro ao listar registros com horários:", str(e))
        traceback.print_exc()
        return jsonify({'registros': [], 'success': False, 'message': str(e)}), 500


@app.route('/registros', methods=['POST'])
def criar_registro():
    try:
        data = request.json

        campos_obrigatorios = ['professor_id', 'data', 'tipo', 'curso_id', 'serie', 'quantidade', 'disciplina']
        for campo in campos_obrigatorios:
            if campo not in data or data[campo] == '':
                return jsonify({'success': False, 'message': f'Campo obrigatório: {campo}'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.id, u.nome_completo 
            FROM professores p 
            JOIN usuarios u ON p.usuario_id = u.id 
            WHERE p.id = %s
        """, (data['professor_id'],))
        prof = cursor.fetchone()

        if not prof:
            conn.close()
            return jsonify({'success': False, 'message': 'Professor não encontrado'}), 404

        # Inserir registro principal COM RETURNING id
        query = """
            INSERT INTO registros
            (professor_id, professor_nome, data, tipo, curso_id, serie, quantidade, disciplina, observacoes, tipo_professor)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        valores = (
            prof['id'],
            prof['nome_completo'],
            data['data'],
            data['tipo'],
            data['curso_id'],
            data['serie'],
            data['quantidade'],
            data['disciplina'],
            data.get('observacoes', ''),
            data.get('tipo_professor', 'Não definido')
        )

        cursor.execute(query, valores)
        registro_id = cursor.fetchone()['id']

        # Inserir múltiplos horários
        horarios = data.get('horarios', [])
        for idx, horario in enumerate(horarios):
            partes = horario.split(' - ')
            if len(partes) == 2:
                cursor.execute("""
                    INSERT INTO registro_horarios (registro_id, horario_inicio, horario_fim, ordem)
                    VALUES (%s, %s, %s, %s)
                """, (registro_id, partes[0] + ':00', partes[1] + ':00', idx))

        conn.commit()
        conn.close()

        # LOG DE AUDITORIA
        usuario_id = request.args.get('usuario_id') or data.get('usuario_id')
        usuario_nome = request.args.get('usuario_nome') or data.get('usuario_nome')
        registrar_log(usuario_id, usuario_nome, 'CRIAR', 'registros', registro_id)

        return jsonify({'success': True, 'id': registro_id}), 201

    except Exception as e:
        print("Erro geral:", str(e))
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/registros/<int:id>', methods=['PUT'])
def atualizar_registro(id):
    try:
        data = request.json
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Atualizar o registro principal
        query = """
            UPDATE registros 
            SET data = %s, tipo = %s, curso_id = %s, serie = %s, 
                quantidade = %s, disciplina = %s, observacoes = %s
            WHERE id = %s
        """
        valores = (
            data['data'],
            data['tipo'],
            data['curso_id'],
            data['serie'],
            data['quantidade'],
            data['disciplina'],
            data.get('observacoes', ''),
            id
        )
        
        cursor.execute(query, valores)
        
        # Remover horários antigos e inserir novos
        cursor.execute("DELETE FROM registro_horarios WHERE registro_id = %s", (id,))
        
        # Inserir os novos horários
        horarios = data.get('horarios', [])
        for idx, horario in enumerate(horarios):
            partes = horario.split(' - ')
            if len(partes) == 2:
                cursor.execute("""
                    INSERT INTO registro_horarios (registro_id, horario_inicio, horario_fim, ordem)
                    VALUES (%s, %s, %s, %s)
                """, (id, partes[0] + ':00', partes[1] + ':00', idx))
        
        conn.commit()
        conn.close()

        # LOG DE AUDITORIA
        usuario_id = request.args.get('usuario_id') or data.get('usuario_id')
        usuario_nome = request.args.get('usuario_nome') or data.get('usuario_nome')
        registrar_log(usuario_id, usuario_nome, 'EDITAR', 'registros', id)
        
        return jsonify({'success': True})
    except Exception as e:
        print("Erro ao atualizar registro:", str(e))
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/registros/<int:id>', methods=['DELETE'])
def deletar_registro(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Primeiro, excluir os horários relacionados
        cursor.execute("DELETE FROM registro_horarios WHERE registro_id = %s", (id,))
        
        # Depois, excluir o registro
        cursor.execute("DELETE FROM registros WHERE id = %s", (id,))
        
        conn.commit()
        conn.close()

        # LOG DE AUDITORIA
        usuario_id = request.args.get('usuario_id')
        usuario_nome = request.args.get('usuario_nome')
        registrar_log(usuario_id, usuario_nome, 'EXCLUIR', 'registros', id)

        return jsonify({'success': True})
    except Exception as e:
        print("Erro ao deletar registro:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500

# ================== ROTAS DE CURSOS E TURMAS ==================

@app.route('/cursos', methods=['GET'])
def listar_cursos():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cursos ORDER BY nome")
        cursos = cursor.fetchall()
        conn.close()
        return jsonify({'cursos': cursos})
    except Exception as e:
        print("Erro ao listar cursos:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/turmas', methods=['GET'])
def listar_turmas():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.*, c.nome as curso_nome 
            FROM turmas t
            JOIN cursos c ON t.curso_id = c.id
            ORDER BY c.nome, t.serie, t.turma
        """)
        
        turmas = cursor.fetchall()
        conn.close()
        
        return jsonify({'turmas': turmas, 'success': True})
    except Exception as e:
        print("Erro ao listar turmas:", str(e))
        traceback.print_exc()
        return jsonify({'turmas': [], 'success': False, 'message': str(e)}), 500

@app.route('/cursos_com_turmas', methods=['GET'])
def listar_cursos_com_turmas():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                c.id,
                c.nome,
                c.turno,
                c.tipo,
                t.id as turma_id,
                t.serie,
                t.modulo,
                t.turma as turma_nome
            FROM cursos c
            LEFT JOIN turmas t ON c.id = t.curso_id AND t.ativo = 1
            WHERE c.ativo = 1
            ORDER BY c.turno, c.nome, t.serie, t.modulo
        """)
        
        resultados = cursor.fetchall()
        conn.close()
        
        # Lista de cursos que devem usar MÓDULO em vez de ANO
        cursos_modulo = [
            'Técnico em Gastronomia',
            'Técnico em Restaurante e Bar',
            'Técnico em Gastronomia PROEJA',
            'Gastronomia',
            'Restaurante e Bar',
            'Gastronomia PROEJA'
        ]
        
        cursos_dict = {}
        for row in resultados:
            if row['id'] not in cursos_dict:
                cursos_dict[row['id']] = {
                    'id': row['id'],
                    'nome': row['nome'],
                    'turno': row['turno'],
                    'tipo': row['tipo'],
                    'turmas': []
                }
            
            if row['turma_id']:
                # Verificar se o curso deve usar módulo
                usar_modulo = any(curso in row['nome'] for curso in cursos_modulo)
                
                if usar_modulo and row['modulo']:
                    nome_turma = f"{row['modulo']}º Módulo"
                elif row['serie']:
                    nome_turma = f"{row['serie']}º Ano"
                elif row['modulo']:
                    nome_turma = f"{row['modulo']}º Módulo"
                else:
                    nome_turma = "Turma"
                
                cursos_dict[row['id']]['turmas'].append({
                    'id': row['turma_id'],
                    'nome': nome_turma,
                    'serie': row['serie'],
                    'modulo': row['modulo']
                })
        
        # Ordenar as turmas de cada curso
        for curso_id in cursos_dict:
            turmas = cursos_dict[curso_id]['turmas']
            turmas.sort(key=lambda x: (
                0 if x['serie'] else 1,
                x['serie'] if x['serie'] else 0,
                int(x['modulo']) if x['modulo'] else 0
            ))
        
        cursos = list(cursos_dict.values())
        return jsonify({'cursos': cursos, 'success': True})
        
    except Exception as e:
        print("Erro ao listar cursos com turmas:", str(e))
        traceback.print_exc()
        return jsonify({'cursos': [], 'success': False, 'message': str(e)}), 500

# ================== ROTAS DE PROFESSORES ==================

@app.route('/professores_lista', methods=['GET'])
def professores_lista():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.id, u.nome_completo as nome
            FROM professores p
            JOIN usuarios u ON p.usuario_id = u.id
            WHERE u.tipo = 'professor'
            ORDER BY u.nome_completo
        """)
        
        professores = cursor.fetchall()
        conn.close()
        
        return jsonify({'professores': professores})
    except Exception as e:
        print("Erro ao listar professores:", str(e))
        return jsonify({'professores': []}), 500

@app.route('/professor_por_usuario/<int:usuario_id>', methods=['GET'])
def professor_por_usuario(usuario_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM professores WHERE usuario_id = %s", (usuario_id,))
        prof = cursor.fetchone()
        conn.close()
        
        if prof:
            return jsonify({'id': prof['id']})
        else:
            return jsonify({'id': None}), 404
    except Exception as e:
        print("Erro:", str(e))
        return jsonify({'error': str(e)}), 500

# ================== ROTAS DE DASHBOARD ==================

@app.route('/dashboard/<int:professor_id>', methods=['GET'])
def dashboard(professor_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total_registros,
                SUM(CASE WHEN tipo = 'reposicao' OR tipo = 'reposição' THEN quantidade ELSE 0 END) as reposicoes,
                SUM(CASE WHEN tipo = 'antecipacao' OR tipo = 'antecipação' THEN quantidade ELSE 0 END) as antecipacoes,
                SUM(CASE WHEN tipo = 'ausencia' OR tipo = 'ausência' THEN quantidade ELSE 0 END) as ausencias
            FROM registros
            WHERE professor_id = %s
        """, (professor_id,))

        stats = cursor.fetchone()
        conn.close()

        total_registros = stats['total_registros'] or 0
        reposicoes = stats['reposicoes'] or 0
        antecipacoes = stats['antecipacoes'] or 0
        ausencias = stats['ausencias'] or 0
        saldo = reposicoes + antecipacoes - ausencias

        return jsonify({
            'total': total_registros,
            'reposicoes': reposicoes,
            'antecipacoes': antecipacoes,
            'ausencias': ausencias,
            'saldo': saldo
        })
    except Exception as e:
        print("Erro no dashboard:", str(e))
        return jsonify({'total': 0, 'reposicoes': 0, 'antecipacoes': 0, 'ausencias': 0, 'saldo': 0}), 200

# ================== ROTAS DE HORÁRIOS ==================

@app.route('/horarios_aula', methods=['GET'])
def listar_horarios_aula():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, nome, horario_inicio, horario_fim, tipo, ordem
            FROM horarios_aula 
            WHERE ativo = 1 
            ORDER BY ordem
        """)
        
        horarios = cursor.fetchall()
        conn.close()
        
        for horario in horarios:
            horario['horario_inicio'] = converter_timedelta_para_string(horario['horario_inicio'])
            horario['horario_fim'] = converter_timedelta_para_string(horario['horario_fim'])
        
        return jsonify({'horarios_aula': horarios, 'success': True})
    except Exception as e:
        print("Erro ao listar horários de aula:", str(e))
        traceback.print_exc()
        return jsonify({'horarios_aula': [], 'success': False, 'message': str(e)}), 500

# ================== ROTAS DO CALENDÁRIO ==================

@app.route('/calendario_professor/turmas', methods=['GET'])
def get_turmas_calendario():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                t.id as turma_id,
                t.serie,
                t.modulo,
                t.turma,
                c.id as curso_id,
                c.nome as curso_nome,
                c.turno
            FROM turmas t
            JOIN cursos c ON t.curso_id = c.id
            WHERE t.ativo = 1
            ORDER BY c.nome, t.serie, t.modulo
        """)
        
        turmas = cursor.fetchall()
        conn.close()
        
        cursos_dict = {}
        for turma in turmas:
            curso_id = turma['curso_id']
            if curso_id not in cursos_dict:
                cursos_dict[curso_id] = {
                    'id': curso_id,
                    'nome': turma['curso_nome'],
                    'turno': turma['turno'],
                    'turmas': []
                }
            
            if turma['serie']:
                nome_turma = f"{turma['serie']}º Ano"
            elif turma['modulo']:
                nome_turma = f"{turma['modulo']}º Módulo"
            else:
                nome_turma = "Turma"
            
            if turma['turma']:
                nome_turma += f" - Turma {turma['turma']}"
            
            cursos_dict[curso_id]['turmas'].append({
                'id': turma['turma_id'],
                'nome': nome_turma
            })
        
        cursos = list(cursos_dict.values())
        return jsonify({'cursos': cursos, 'success': True})
        
    except Exception as e:
        print("Erro ao listar turmas:", str(e))
        traceback.print_exc()
        return jsonify({'cursos': [], 'success': False, 'message': str(e)}), 500

@app.route('/calendario_professor/horarios/<int:turma_id>', methods=['GET'])
def get_calendario_turma_marcacoes(turma_id):
    try:
        semana_inicio = request.args.get('semana_inicio')
        
        if not semana_inicio:
            semana_inicio = get_semana_atual().strftime('%Y-%m-%d')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.*, c.nome as curso_nome, c.turno
            FROM turmas t
            JOIN cursos c ON t.curso_id = c.id
            WHERE t.id = %s
        """, (turma_id,))
        
        turma = cursor.fetchone()
        
        if not turma:
            conn.close()
            return jsonify({'success': False, 'message': 'Turma não encontrada'}), 404
        
        turno = turma['turno']
        
        horarios_config = {
            'manha': [
                {'id': 1, 'nome': '1ª Aula', 'inicio': '07:00', 'fim': '08:00'},
                {'id': 2, 'nome': '2ª Aula', 'inicio': '08:00', 'fim': '09:00'},
                {'id': 3, 'nome': '3ª Aula', 'inicio': '09:00', 'fim': '10:00'},
                {'id': 4, 'nome': '4ª Aula', 'inicio': '10:20', 'fim': '11:20'},
                {'id': 5, 'nome': '5ª Aula', 'inicio': '11:20', 'fim': '12:20'},
            ],
            'tarde': [
                {'id': 10, 'nome': '1ª Aula', 'inicio': '13:00', 'fim': '14:00'},
                {'id': 11, 'nome': '2ª Aula', 'inicio': '14:00', 'fim': '15:00'},
                {'id': 12, 'nome': '3ª Aula', 'inicio': '15:00', 'fim': '16:00'},
                {'id': 13, 'nome': '4ª Aula', 'inicio': '16:00', 'fim': '17:00'},
                {'id': 14, 'nome': '5ª Aula', 'inicio': '17:00', 'fim': '18:00'},
            ],
            'noite': [
                {'id': 15, 'nome': '1ª Aula', 'inicio': '18:00', 'fim': '19:00'},
                {'id': 16, 'nome': '2ª Aula', 'inicio': '19:00', 'fim': '20:00'},
                {'id': 17, 'nome': '3ª Aula', 'inicio': '20:00', 'fim': '21:00'},
                {'id': 18, 'nome': '4ª Aula', 'inicio': '21:00', 'fim': '22:00'},
            ]
        }
        
        horarios_lista = horarios_config.get(turno, horarios_config['manha'])
        
        cursor.execute("""
            SELECT cm.*, 
                   p_origem.usuario_id as origem_usuario_id,
                   u_origem.nome_completo as professor_nome
            FROM calendario_marcacoes cm
            LEFT JOIN professores p_origem ON cm.professor_id = p_origem.id
            LEFT JOIN usuarios u_origem ON p_origem.usuario_id = u_origem.id
            WHERE cm.turma_id = %s AND cm.semana_inicio = %s
        """, (turma_id, semana_inicio))
        
        marcacoes = cursor.fetchall()
        conn.close()
        
        marcacoes_map = {}
        for marcacao in marcacoes:
            key = f"{marcacao['dia_semana']}_{marcacao['horario_id']}"
            marcacoes_map[key] = {
                'status': marcacao['status'],
                'professor_id': marcacao['professor_id'],
                'professor_nome': marcacao['professor_nome']
            }
        
        dias = [
            {'id': 1, 'nome': 'Segunda-feira', 'abreviado': 'SEG'},
            {'id': 2, 'nome': 'Terça-feira', 'abreviado': 'TER'},
            {'id': 3, 'nome': 'Quarta-feira', 'abreviado': 'QUA'},
            {'id': 4, 'nome': 'Quinta-feira', 'abreviado': 'QUI'},
            {'id': 5, 'nome': 'Sexta-feira', 'abreviado': 'SEX'}
        ]
        
        calendario = []
        for dia in dias:
            linha_dia = {
                'dia_id': dia['id'],
                'dia_nome': dia['nome'],
                'dia_abreviado': dia['abreviado'],
                'horarios': []
            }
            
            for horario in horarios_lista:
                key = f"{dia['id']}_{horario['id']}"
                marcacao = marcacoes_map.get(key, {
                    'status': 'normal',
                    'professor_id': None,
                    'professor_nome': None
                })
                
                linha_dia['horarios'].append({
                    'horario_id': horario['id'],
                    'horario_nome': horario['nome'],
                    'horario_inicio': horario['inicio'],
                    'horario_fim': horario['fim'],
                    'status': marcacao['status'],
                    'professor_id': marcacao['professor_id'],
                    'professor_nome': marcacao['professor_nome']
                })
            
            calendario.append(linha_dia)
        
        return jsonify({
            'success': True,
            'turma': turma,
            'semana_inicio': semana_inicio,
            'calendario': calendario
        })
        
    except Exception as e:
        print("Erro ao buscar calendário:", str(e))
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/calendario_professor/marcar', methods=['POST'])
def marcar_horario():
    try:
        data = request.json
        
        print("\n" + "="*60)
        print("[DEBUG] /calendario_professor/marcar chamado")
        print(f"[DEBUG] Dados recebidos: {data}")
        print("="*60)
        
        campos_obrigatorios = ['turma_id', 'dia_semana', 'horario_id', 'status', 'semana_inicio', 'usuario_id']
        for campo in campos_obrigatorios:
            if campo not in data:
                return jsonify({'success': False, 'message': f'Campo obrigatório: {campo}'}), 400
        
        if data['status'] not in ['normal', 'vago', 'ocupado']:
            return jsonify({'success': False, 'message': 'Status inválido'}), 400
        
        usuario_id = data['usuario_id']
        professor_id = get_professor_id_by_usuario_id(usuario_id)
        user_tipo = get_tipo_usuario(usuario_id)
        
        print(f"[DEBUG] usuario_id: {usuario_id}, professor_id: {professor_id}, user_tipo: {user_tipo}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Buscar informações da turma
        cursor.execute("""
            SELECT t.id as turma_id, t.serie, t.modulo, 
                   c.id as curso_id, c.nome as curso_nome, c.turno
            FROM turmas t
            JOIN cursos c ON t.curso_id = c.id
            WHERE t.id = %s
        """, (data['turma_id'],))
        
        turma_info = cursor.fetchone()
        
        if not turma_info:
            conn.close()
            return jsonify({'success': False, 'message': 'Turma não encontrada'}), 404
        
        turma_nome = f"{turma_info['serie']}º Ano" if turma_info['serie'] else f"{turma_info['modulo']}º Módulo"
        curso_nome = turma_info['curso_nome']
        
        # Verificar se já existe marcação
        cursor.execute("""
            SELECT id, status, professor_id
            FROM calendario_marcacoes 
            WHERE turma_id = %s AND dia_semana = %s AND horario_id = %s AND semana_inicio = %s
        """, (data['turma_id'], data['dia_semana'], data['horario_id'], data['semana_inicio']))
        
        existente = cursor.fetchone()
        
               # ========== REGRAS DE NEGÓCIO ==========
        
        # REGRA 1: COORDENADOR disponibilizando horário VAGO (normal -> vago)
        if data['status'] == 'vago' and user_tipo == 'coordenador':
            if not existente:
                # Criar novo VAGO
                cursor.execute("""
                    INSERT INTO calendario_marcacoes 
                    (turma_id, dia_semana, horario_id, status, semana_inicio)
                    VALUES (%s, %s, %s, %s, %s)
                """, (data['turma_id'], data['dia_semana'], data['horario_id'], 'vago', data['semana_inicio']))
                conn.commit()
                
                # Notificar professores (opcional)
                cursor.execute("SELECT id FROM professores")
                professores = cursor.fetchall()
                for prof in professores:
                    try:
                        cursor.execute("""
                            INSERT INTO notificacoes 
                            (tipo, turma_id, turma_nome, curso_nome, dia_semana, dia_nome, horario_id, professor_origem_nome, professor_destino_id, status, mensagem)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, ('vago_disponivel', data['turma_id'], turma_nome, curso_nome, data['dia_semana'], 
                              get_dia_nome(data['dia_semana']), data['horario_id'], 'Coordenador', prof['id'], 'pendente', f'Horário VAGO disponível em {turma_nome}'))
                    except Exception as e:
                        print(f"Erro notificação: {e}")
                
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': 'Horário disponibilizado como VAGO!'})
            else:
                # Já existe marcação, tentar atualizar
                if existente['status'] == 'normal':
                    cursor.execute("""
                        UPDATE calendario_marcacoes 
                        SET status = 'vago', professor_id = NULL 
                        WHERE id = %s
                    """, (existente['id'],))
                    conn.commit()
                    conn.close()
                    return jsonify({'success': True, 'message': 'Horário alterado para VAGO!'})
                else:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Este horário já está marcado'}), 400
        
        # REGRA 2: COORDENADOR removendo VAGO (vago -> normal)
        elif data['status'] == 'normal' and user_tipo == 'coordenador':
            if existente and existente['status'] == 'vago':
                cursor.execute("DELETE FROM calendario_marcacoes WHERE id = %s", (existente['id'],))
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': 'Horário VAGO removido!'})
            else:
                conn.close()
                return jsonify({'success': False, 'message': 'Este horário não está VAGO'}), 400
        
        # REGRA 3: PROFESSOR pegando horário VAGO (vago -> ocupado)
        elif data['status'] == 'ocupado' and user_tipo == 'professor' and professor_id:
            if existente and existente['status'] == 'vago':
                cursor.execute("""
                    UPDATE calendario_marcacoes 
                    SET status = 'ocupado', professor_id = %s 
                    WHERE id = %s
                """, (professor_id, existente['id']))
                conn.commit()
                
                # Notificar coordenador
                cursor.execute("SELECT id FROM usuarios WHERE tipo = 'coordenador'")
                coordenadores = cursor.fetchall()
                for coord in coordenadores:
                    try:
                        cursor.execute("""
                            INSERT INTO notificacoes 
                            (tipo, turma_id, turma_nome, curso_nome, dia_semana, dia_nome, horario_id, professor_origem_nome, professor_destino_id, status, mensagem)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, ('horario_ocupado', data['turma_id'], turma_nome, curso_nome, data['dia_semana'], 
                              get_dia_nome(data['dia_semana']), data['horario_id'], get_nome_professor(professor_id), coord['id'], 'pendente', 
                              f'{get_nome_professor(professor_id)} pegou horário VAGO'))
                    except Exception as e:
                        print(f"Erro notificação: {e}")
                
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': 'Você pegou este horário!'})
            else:
                conn.close()
                return jsonify({'success': False, 'message': 'Este horário não está disponível'}), 400
        
        # REGRA 4: PROFESSOR cancelando seu próprio horário (ocupado -> vago)
        elif data['status'] == 'vago' and user_tipo == 'professor' and professor_id:
            if existente and existente['status'] == 'ocupado' and existente['professor_id'] == professor_id:
                # Em vez de DELETAR, transforma em VAGO
                cursor.execute("""
                    UPDATE calendario_marcacoes 
                    SET status = 'vago', professor_id = NULL 
                    WHERE id = %s
                """, (existente['id'],))
                conn.commit()
                
                # Notificar coordenador
                cursor.execute("SELECT id FROM usuarios WHERE tipo = 'coordenador'")
                coordenadores = cursor.fetchall()
                for coord in coordenadores:
                    try:
                        cursor.execute("""
                            INSERT INTO notificacoes 
                            (tipo, turma_id, turma_nome, curso_nome, dia_semana, dia_nome, horario_id, professor_origem_nome, professor_destino_id, status, mensagem)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, ('horario_cancelado', data['turma_id'], turma_nome, curso_nome, data['dia_semana'], 
                              get_dia_nome(data['dia_semana']), data['horario_id'], get_nome_professor(professor_id), coord['id'], 'pendente', 
                              f'{get_nome_professor(professor_id)} cancelou seu horário (voltou para VAGO)'))
                    except Exception as e:
                        print(f"Erro notificação: {e}")
                
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': 'Horário cancelado! Voltou a ser VAGO.'})
            else:
                conn.close()
                return jsonify({'success': False, 'message': 'Este horário não pertence a você'}), 400
        
        # REGRA 5: PROFESSOR marcando como VAGO? NÃO PERMITIDO
        elif data['status'] == 'vago' and user_tipo == 'professor':
            conn.close()
            return jsonify({'success': False, 'message': 'Apenas o coordenador pode disponibilizar horários VAGOS'}), 403
        
        # REGRA 6: COORDENADOR pegando horário? NÃO PERMITIDO
        elif data['status'] == 'ocupado' and user_tipo == 'coordenador':
            conn.close()
            return jsonify({'success': False, 'message': 'Coordenador não pode pegar horários'}), 403
        
        else:
            conn.close()
            return jsonify({'success': False, 'message': 'Operação não permitida para seu perfil'}), 400
        
    except Exception as e:
        print(f"[ERRO] /calendario_professor/marcar: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/calendario_professor/reset_semanal', methods=['POST'])
def reset_semanal():
    try:
        semana_atual = get_semana_atual().strftime('%Y-%m-%d')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM calendario_marcacoes WHERE semana_inicio < %s", (semana_atual,))
        deletados = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'{deletados} marcações antigas removidas'})
    except Exception as e:
        print("Erro ao resetar marcações:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500

# ================== ROTAS DE NOTIFICAÇÕES ==================

@app.route('/notificacoes', methods=['GET'])
def listar_notificacoes():
    try:
        usuario_id = request.args.get('usuario_id', type=int)
        
        if not usuario_id:
            return jsonify({'success': False, 'message': 'Usuário ID obrigatório'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM notificacoes 
            WHERE professor_destino_id = %s AND status = 'pendente'
            ORDER BY criado_em DESC
        """, (usuario_id,))
        
        notificacoes = cursor.fetchall()
        conn.close()
        
        return jsonify({'notificacoes': notificacoes, 'success': True})
        
    except Exception as e:
        print("Erro ao listar notificações:", str(e))
        traceback.print_exc()
        return jsonify({'notificacoes': [], 'success': False, 'message': str(e)}), 200

@app.route('/notificacoes/marcar_lida', methods=['POST'])
def marcar_notificacao_lida():
    try:
        data = request.json
        notificacao_id = data.get('notificacao_id')
        
        if not notificacao_id:
            return jsonify({'success': False, 'message': 'ID da notificação obrigatório'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE notificacoes SET status = 'lida', lida_em = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (notificacao_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Notificação marcada como lida'})
        
    except Exception as e:
        print("Erro ao marcar notificação:", str(e))
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/notificacoes/contador', methods=['GET'])
def contador_notificacoes():
    try:
        usuario_id = request.args.get('usuario_id', type=int)
        
        if not usuario_id:
            return jsonify({'success': False, 'message': 'Usuário ID obrigatório'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) as total FROM notificacoes 
            WHERE professor_destino_id = %s AND status = 'pendente'
        """, (usuario_id,))
        
        resultado = cursor.fetchone()
        conn.close()
        
        return jsonify({'total': resultado['total'] if resultado else 0, 'success': True})
        
    except Exception as e:
        print("Erro ao contar notificações:", str(e))
        traceback.print_exc()
        return jsonify({'total': 0, 'success': False, 'message': str(e)}), 500

# ================== ROTAS DE ADMINISTRAÇÃO ==================

@app.route('/admin/usuarios', methods=['GET'])
def admin_listar_usuarios():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT u.id, u.usuario, u.nome_completo, u.tipo, 
                   p.id as professor_id, p.disciplina, p.tipo as professor_tipo
            FROM usuarios u
            LEFT JOIN professores p ON u.id = p.usuario_id
            ORDER BY u.tipo, u.nome_completo
        """)
        
        usuarios = cursor.fetchall()
        conn.close()
        
        return jsonify({'usuarios': usuarios, 'success': True})
    except Exception as e:
        print("Erro ao listar usuários:", str(e))
        return jsonify({'usuarios': [], 'success': False, 'message': str(e)}), 500

@app.route('/admin/usuarios', methods=['POST'])
def admin_criar_usuario():
    try:
        data = request.json
        
        campos_obrigatorios = ['usuario', 'senha', 'nome_completo', 'tipo']
        for campo in campos_obrigatorios:
            if campo not in data or not data[campo]:
                return jsonify({'success': False, 'message': f'Campo obrigatório: {campo}'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM usuarios WHERE usuario = %s", (data['usuario'],))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Usuário já existe'}), 400

        senha_hash = hash_senha(data['senha'])
        
        cursor.execute("""
            INSERT INTO usuarios (usuario, senha, nome_completo, tipo)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (data['usuario'], senha_hash, data['nome_completo'], data['tipo']))
        
        usuario_id = cursor.fetchone()['id']
        
        if data['tipo'] == 'professor':
            disciplina = data.get('disciplina', '')
            professor_tipo = data.get('professor_tipo', 'Base Comum')
            cursor.execute("""
                INSERT INTO professores (usuario_id, disciplina, tipo)
                VALUES (%s, %s, %s)
            """, (usuario_id, disciplina, professor_tipo))
        
        conn.commit()
        conn.close()

        admin_id = data.get('admin_id')
        admin_nome = data.get('admin_nome')
        registrar_log(admin_id, admin_nome, 'CRIAR_USUARIO', 'usuarios', usuario_id, None, f'usuario: {data["usuario"]}, tipo: {data["tipo"]}')
        
        return jsonify({'success': True, 'message': 'Usuário criado com sucesso', 'id': usuario_id})
    except Exception as e:
        print(f"Erro ao criar usuário: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/usuarios/<int:id>', methods=['PUT'])
def admin_atualizar_usuario(id):
    try:
        data = request.json
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, tipo FROM usuarios WHERE id = %s", (id,))
        usuario = cursor.fetchone()
        
        if not usuario:
            conn.close()
            return jsonify({'success': False, 'message': 'Usuário não encontrado'}), 404
        
        updates = []
        params = []
        
        if 'nome_completo' in data:
            updates.append("nome_completo = %s")
            params.append(data['nome_completo'])
        
        if 'tipo' in data:
            updates.append("tipo = %s")
            params.append(data['tipo'])
        
        if 'usuario' in data:
            updates.append("usuario = %s")
            params.append(data['usuario'])
        
        if 'senha' in data and data['senha']:
            updates.append("senha = %s")
            params.append(hash_senha(data['senha']))
        
        if updates:
            params.append(id)
            cursor.execute(f"UPDATE usuarios SET {', '.join(updates)} WHERE id = %s", params)
        
        if data.get('tipo') == 'professor' or usuario['tipo'] == 'professor':
            cursor.execute("SELECT id FROM professores WHERE usuario_id = %s", (id,))
            professor = cursor.fetchone()
            
            disciplina = data.get('disciplina', '')
            professor_tipo = data.get('professor_tipo', 'Base Comum')
            
            if professor:
                cursor.execute("""
                    UPDATE professores SET disciplina = %s, tipo = %s WHERE usuario_id = %s
                """, (disciplina, professor_tipo, id))
            else:
                cursor.execute("""
                    INSERT INTO professores (usuario_id, disciplina, tipo) VALUES (%s, %s, %s)
                """, (id, disciplina, professor_tipo))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Usuário atualizado com sucesso'})
    except Exception as e:
        print("Erro ao atualizar usuário:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/usuarios/<int:id>', methods=['DELETE'])
def admin_deletar_usuario(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM usuarios WHERE id = %s", (id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Usuário não encontrado'}), 404
        
        # Primeiro, deletar da tabela professores (se existir)
        cursor.execute("DELETE FROM professores WHERE usuario_id = %s", (id,))
        
        # Depois, deletar o usuário
        cursor.execute("DELETE FROM usuarios WHERE id = %s", (id,))
        
        conn.commit()
        conn.close()

        # LOG DE AUDITORIA
        usuario_id = request.args.get('admin_id')
        usuario_nome = request.args.get('admin_nome')
        registrar_log(usuario_id, usuario_nome, 'EXCLUIR_USUARIO', 'usuarios', id)
        
        return jsonify({'success': True, 'message': 'Usuário excluído com sucesso'})
    except Exception as e:
        print("Erro ao deletar usuário:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/usuarios/tipos', methods=['GET'])
def admin_listar_tipos():
    return jsonify({'tipos': ['professor', 'coordenador', 'tecnico_administrativo', 'admin'], 'success': True})

@app.route('/debug/usuarios', methods=['GET'])
def debug_usuarios():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, usuario, nome_completo, tipo FROM usuarios")
        usuarios = cursor.fetchall()
        conn.close()
        return jsonify({'usuarios': usuarios})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/marcacoes/<int:turma_id>', methods=['GET'])
def debug_marcacoes(turma_id):
    try:
        semana_inicio = request.args.get('semana_inicio', get_semana_atual().strftime('%Y-%m-%d'))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cm.*, u.nome_completo as professor_nome
            FROM calendario_marcacoes cm
            LEFT JOIN professores p ON cm.professor_id = p.id
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            WHERE cm.turma_id = %s AND cm.semana_inicio = %s
        """, (turma_id, semana_inicio))
        marcacoes = cursor.fetchall()
        conn.close()
        return jsonify({'marcacoes': marcacoes, 'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ================== ROTAS DE RECUPERAÇÃO DE SENHA ==================

import smtplib
import random
import string
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


import os
import requests

def enviar_email(destinatario, codigo):
    """Envia e-mail REAL usando API do SendGrid"""
    try:
        api_key = os.environ.get('SENDGRID_API_KEY')
        
        # Se não tiver API Key (modo desenvolvimento/local)
        if not api_key:
            print(f"\n📧 [MODO DEBUG] Código para {destinatario}: {codigo}")
            return True
        
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "personalizations": [
                {"to": [{"email": destinatario}]}
            ],
            "from": {"email": "sarahfqueiroz2@gmail.com"},
            "subject": "🔐 Código de Recuperação - IFPI",
            "content": [
                {
                    "type": "text/plain",
                    "value": f"Olá,\n\nSeu código de verificação é: {codigo}\n\nEste código é válido por 5 minutos.\n\nIFPI Campus Pedro II"
                }
            ]
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 202:
            print(f"✅ E-mail enviado para {destinatario}")
            return True
        else:
            print(f"❌ Erro ao enviar: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

@app.route('/recuperar/enviar_codigo', methods=['POST'])
def recuperar_enviar_codigo():
    try:
        data = request.json
        email = data.get('email')

        if not email:
            return jsonify({'success': False, 'message': 'E-mail obrigatório'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM usuarios WHERE usuario = %s", (email,))
        usuario = cursor.fetchone()

        if not usuario:
            conn.close()
            return jsonify({'success': False, 'message': 'E-mail não cadastrado'}), 404

        codigo = gerar_codigo()
        expira_em = datetime.now() + timedelta(minutes=5)
        
        # TABELA CORRIGIDA PARA POSTGRESQL (SEM AUTO_INCREMENT)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recuperacao_senha (
                id SERIAL PRIMARY KEY,
                email VARCHAR(100) NOT NULL,
                codigo VARCHAR(10) NOT NULL,
                expira_em TIMESTAMP NOT NULL,
                usado INTEGER DEFAULT 0,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("DELETE FROM recuperacao_senha WHERE email = %s", (email,))
        
        cursor.execute("""
            INSERT INTO recuperacao_senha (email, codigo, expira_em)
            VALUES (%s, %s, %s)
        """, (email, codigo, expira_em))

        conn.commit()
        conn.close()

        enviar_email(email, codigo)

        return jsonify({'success': True, 'message': 'Código enviado para seu e-mail'})

    except Exception as e:
        print("Erro ao enviar código:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/recuperar/verificar_codigo', methods=['POST'])
def recuperar_verificar_codigo():
    try:
        data = request.json
        email = data.get('email')
        codigo = data.get('codigo')

        if not email or not codigo:
            return jsonify({'success': False, 'message': 'E-mail e código obrigatórios'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id FROM recuperacao_senha 
            WHERE email = %s AND codigo = %s AND usado = 0 AND expira_em > NOW()
        """, (email, codigo))

        recuperacao = cursor.fetchone()
        conn.close()

        if not recuperacao:
            return jsonify({'success': False, 'message': 'Código inválido ou expirado'}), 400

        return jsonify({'success': True, 'message': 'Código válido'})

    except Exception as e:
        print("Erro ao verificar código:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/recuperar/alterar_senha', methods=['POST'])
def recuperar_alterar_senha():
    try:
        data = request.json
        email = data.get('email')
        codigo = data.get('codigo')
        usuario = data.get('usuario')
        nova_senha = data.get('nova_senha')

        if not email or not codigo or not usuario or not nova_senha:
            return jsonify({'success': False, 'message': 'Todos os campos são obrigatórios'}), 400

        if len(nova_senha) < 6:
            return jsonify({'success': False, 'message': 'A senha deve ter pelo menos 6 caracteres'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id FROM recuperacao_senha 
            WHERE email = %s AND codigo = %s AND usado = 0 AND expira_em > NOW()
        """, (email, codigo))

        recuperacao = cursor.fetchone()

        if not recuperacao:
            conn.close()
            return jsonify({'success': False, 'message': 'Código inválido ou expirado'}), 400

        cursor.execute("SELECT id FROM usuarios WHERE usuario = %s", (usuario,))
        user = cursor.fetchone()

        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'Usuário não encontrado'}), 404

        cursor.execute("UPDATE usuarios SET senha = %s WHERE usuario = %s", (hash_senha(nova_senha), usuario))
        cursor.execute("UPDATE recuperacao_senha SET usado = 1 WHERE id = %s", (recuperacao['id'],))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Senha alterada com sucesso'})

    except Exception as e:
        print("Erro ao alterar senha:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500


# ================== FUNÇÕES AUXILIARES PARA RECUPERAÇÃO ==================
def gerar_codigo():
    import random
    import string
    return ''.join(random.choices(string.digits, k=6))


@app.route('/registros/<int:id>', methods=['GET'])
def get_registro(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM registros WHERE id = %s", (id,))
        registro = cursor.fetchone()
        conn.close()
        
        if registro:
            # Converter tipos não serializáveis
            for key, value in registro.items():
                if hasattr(value, 'total_seconds'):  # timedelta
                    registro[key] = str(value)
                elif hasattr(value, 'strftime'):  # date/datetime
                    registro[key] = value.isoformat()
            return jsonify({'registro': registro})
        else:
            return jsonify({'error': 'Registro não encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/resetar-seq', methods=['GET'])
def resetar_sequencia():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT setval('registros_id_seq', (SELECT max(id) FROM registros));")
        cursor.execute("SELECT setval('registro_horarios_id_seq', (SELECT max(id) FROM registro_horarios));")
        conn.commit()
        conn.close()
        return "✅ Sequências resetadas com sucesso!"
    except Exception as e:
        return f"❌ Erro: {e}"

# ================== ROTA DE LOGS DE AUDITORIA ==================
@app.route('/admin/logs', methods=['GET'])
def admin_visualizar_logs():
    try:
        usuario_id = request.args.get('usuario_id', type=int)
        
        if not usuario_id:
            return jsonify({'success': False, 'message': 'Usuario nao autenticado'}), 401
        
        user_tipo = get_tipo_usuario(usuario_id)
        
        # So admin pode ver os logs
        if user_tipo != 'admin':
            return jsonify({'success': False, 'message': 'Acesso negado'}), 403
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Buscar os ultimos 200 logs
        cursor.execute("""
            SELECT * FROM logs_auditoria 
            ORDER BY created_at DESC 
            LIMIT 200
        """)
        
        logs = cursor.fetchall()
        conn.close()
        
        # Converter para JSON
        logs_json = []
        for log in logs:
            logs_json.append({
                'id': log['id'],
                'usuario_id': log['usuario_id'],
                'usuario_nome': log['usuario_nome'],
                'acao': log['acao'],
                'tabela': log['tabela'],
                'registro_id': log['registro_id'],
                'dados_antes': log['dados_antes'],
                'dados_depois': log['dados_depois'],
                'ip': log['ip'],
                'user_agent': log['user_agent'],
                'created_at': log['created_at'].isoformat() if log['created_at'] else None
            })
        
        return jsonify({'logs': logs_json, 'success': True})
        
    except Exception as e:
        print(f"Erro ao buscar logs: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/consertar-sequence', methods=['GET'])
def consertar_sequence():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar se a tabela tem dados
        cursor.execute("SELECT COUNT(*) as total FROM usuarios")
        resultado = cursor.fetchone()
        count = resultado['total'] if resultado else 0
        
        if count == 0:
            cursor.execute("ALTER SEQUENCE usuarios_id_seq RESTART WITH 1")
            proximo = 1
        else:
            cursor.execute("SELECT MAX(id) as max_id FROM usuarios")
            resultado = cursor.fetchone()
            max_id = resultado['max_id'] if resultado else 0
            proximo = max_id + 1
            cursor.execute(f"ALTER SEQUENCE usuarios_id_seq RESTART WITH {proximo}")
        
        conn.commit()
        
        # Testar se funcionou
        cursor.execute("SELECT nextval('usuarios_id_seq') as next_id")
        next_val = cursor.fetchone()['next_id']
        
        conn.close()
        
        return f"✅ Sucesso! Total usuarios: {count}, Proximo ID: {next_val}"
    except Exception as e:
        import traceback
        return f"❌ Erro: {str(e)}"

@app.route('/consertar-sequence-professores', methods=['GET'])
def consertar_sequence_professores():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT MAX(id) FROM professores")
        resultado = cursor.fetchone()
        max_id = resultado['max_id'] if resultado and resultado['max_id'] else 0
        
        novo_valor = max_id + 1 if max_id > 0 else 1
        
        cursor.execute(f"ALTER SEQUENCE professores_id_seq RESTART WITH {novo_valor}")
        conn.commit()
        
        conn.close()
        
        return f"✅ Sequence professores resetada! Maior ID: {max_id}, Próximo ID: {novo_valor}"
    except Exception as e:
        return f"❌ Erro: {str(e)}"
# ================== INICIALIZAÇÃO ==================

if __name__ == '__main__':
    # Criar tabelas necessárias
    criar_tabelas()
    
    # Pega a porta do Heroku ou usa 8080
    port = int(os.environ.get('PORT', 8080))
    
    print("="*60)
    print("SERVIDOR INICIADO")
    print("="*60)
    print(f"Acesse: http://localhost:{port}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
