import os
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

# ================== CRIAR TABELAS AUTOMATICAMENTE (RENDER) ==================
with app.app_context():
    try:
        print("📦 Verificando/Criando tabelas no banco de dados...")
        criar_tabelas()
        print("✅ Tabelas verificadas/criadas com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")

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
            password='ifpi2026',
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

def criar_tabelas():
    """Cria as tabelas necessárias se não existirem"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela calendario_marcacoes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calendario_marcacoes (
            id INT PRIMARY KEY AUTO_INCREMENT,
            turma_id INT NOT NULL,
            dia_semana INT NOT NULL,
            horario_id INT NOT NULL,
            status VARCHAR(20) DEFAULT 'normal',
            professor_id INT NULL,
            dono_original_id INT NULL,
            semana_inicio DATE NOT NULL,
            data_marcacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_marcacao (turma_id, dia_semana, horario_id, semana_inicio)
        )
    """)
    
    # Tabela notificacoes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notificacoes (
            id INT PRIMARY KEY AUTO_INCREMENT,
            tipo VARCHAR(50),
            turma_id INT,
            turma_nome VARCHAR(100),
            curso_nome VARCHAR(100),
            dia_semana INT,
            dia_nome VARCHAR(50),
            horario_id INT,
            professor_origem_id INT,
            professor_origem_nome VARCHAR(200),
            professor_destino_id INT,
            status VARCHAR(20) DEFAULT 'pendente',
            mensagem TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            lida_em TIMESTAMP NULL
        )
    """)
    
    conn.commit()
    conn.close()
    print("Tabelas verificadas/criadas com sucesso!")

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

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT u.*, p.disciplina, p.tipo as tipo_professor FROM usuarios u LEFT JOIN professores p ON u.id = p.usuario_id WHERE u.usuario = %s AND u.senha = MD5(%s)",
            (usuario, senha)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
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
        else:
            return jsonify({'success': False, 'message': 'Usuário ou senha incorretos'}), 401
    except Exception as e:
        print("Erro no login:", str(e))
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Erro no servidor'}), 500

# ================== ROTAS DE REGISTROS ==================

@app.route('/registros', methods=['GET'])
def listar_registros():
    try:
        professor_id = request.args.get('professor_id')

        conn = get_db_connection()
        cursor = conn.cursor()

        if professor_id:
            cursor.execute("""
                SELECT r.*, c.nome as curso_nome
                FROM registros r
                JOIN cursos c ON r.curso_id = c.id
                WHERE r.professor_id = %s
                ORDER BY r.data DESC
            """, (professor_id,))
        else:
            cursor.execute("""
                SELECT r.*, c.nome as curso_nome, u.nome_completo as professor_nome
                FROM registros r
                JOIN cursos c ON r.curso_id = c.id
                JOIN professores p ON r.professor_id = p.id
                JOIN usuarios u ON p.usuario_id = u.id
                ORDER BY r.data DESC
            """)

        registros = cursor.fetchall()
        conn.close()

        registros_serializaveis = [serializar_registro(reg) for reg in registros]
        return jsonify({'registros': registros_serializaveis})

    except Exception as e:
        print("Erro ao listar registros:", str(e))
        traceback.print_exc()
        return jsonify({'registros': []}), 200


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

        # Inserir registro principal (sem horário_inicio e horario_fim)
        query = """
            INSERT INTO registros
            (professor_id, professor_nome, data, tipo, curso_id, serie, quantidade, disciplina, observacoes, tipo_professor)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        registro_id = cursor.lastrowid

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
        
        query = """
            UPDATE registros 
            SET data = %s, tipo = %s, curso_id = %s, serie = %s, 
                quantidade = %s, horario_inicio = %s, horario_fim = %s, 
                disciplina = %s, observacoes = %s
            WHERE id = %s
        """
        valores = (
            data['data'],
            data['tipo'],
            data['curso_id'],
            data['serie'],
            data['quantidade'],
            data['horario_inicio'],
            data['horario_fim'],
            data['disciplina'],
            data.get('observacoes', ''),
            id
        )
        
        cursor.execute(query, valores)
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        print("Erro ao atualizar registro:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/registros/<int:id>', methods=['DELETE'])
def deletar_registro(id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM registros WHERE id = %s", (id,))
        conn.commit()
        conn.close()
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
        
        # CASO 1: Não existe marcação
        if not existente:
            print("[DEBUG] Criando nova marcação...")
            
            # Coordenador criando VAGO
            if data['status'] == 'vago':
                if user_tipo != 'coordenador':
                    conn.close()
                    return jsonify({'success': False, 'message': 'Apenas o coordenador pode disponibilizar horários vagos'}), 403
                
                cursor.execute("""
                    INSERT INTO calendario_marcacoes 
                    (turma_id, dia_semana, horario_id, status, semana_inicio)
                    VALUES (%s, %s, %s, %s, %s)
                """, (data['turma_id'], data['dia_semana'], data['horario_id'], 'vago', data['semana_inicio']))
                conn.commit()
                
                # Notificar professores
                cursor.execute("SELECT id FROM professores")
                professores = cursor.fetchall()
                
                for prof in professores:
                    cursor.execute("""
                        INSERT INTO notificacoes 
                        (tipo, turma_id, turma_nome, curso_nome, dia_semana, dia_nome, horario_id, professor_origem_nome, professor_destino_id, status, mensagem)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, ('vago_disponivel', data['turma_id'], turma_nome, curso_nome, data['dia_semana'], get_dia_nome(data['dia_semana']), data['horario_id'], 'Coordenador', prof['id'], 'pendente', f'Horario VAGO em {turma_nome}'))
                
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': 'Horário marcado como VAGO! Professores notificados.'})
            
            # Professor criando OCUPADO (pegando horário)
            elif data['status'] == 'ocupado':
                if not professor_id:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Apenas professores podem pegar horários'}), 403
                
                cursor.execute("""
                    INSERT INTO calendario_marcacoes 
                    (turma_id, dia_semana, horario_id, status, professor_id, dono_original_id, semana_inicio)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (data['turma_id'], data['dia_semana'], data['horario_id'], 'ocupado', professor_id, professor_id, data['semana_inicio']))
                conn.commit()
                conn.close()
                return jsonify({'success': True, 'message': 'Horário ocupado com sucesso!'})
            
            else:
                conn.close()
                return jsonify({'success': False, 'message': 'Operação não permitida'}), 400
        
        # CASO 2: Já existe marcação
        else:
            print(f"[DEBUG] Marcação existente: {existente}")
            
            # Usuário NÃO é o dono
            if existente['professor_id'] != professor_id:
                # Só pode pegar se estiver VAGO
                if existente['status'] == 'vago' and data['status'] == 'ocupado' and professor_id:
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
                        cursor.execute("""
                            INSERT INTO notificacoes 
                            (tipo, turma_id, turma_nome, curso_nome, dia_semana, dia_nome, horario_id, professor_origem_nome, professor_destino_id, status, mensagem)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, ('horario_ocupado', data['turma_id'], turma_nome, curso_nome, data['dia_semana'], get_dia_nome(data['dia_semana']), data['horario_id'], get_nome_professor(professor_id), coord['id'], 'pendente', f'{get_nome_professor(professor_id)} pegou horario VAGO'))
                    
                    conn.commit()
                    conn.close()
                    return jsonify({'success': True, 'message': 'Horário ocupado! Coordenador notificado.'})
                else:
                    conn.close()
                    return jsonify({'success': False, 'message': 'Você não pode alterar este horário'}), 403
            
            # Usuário É o dono
            else:
                # Voltar para branco (normal)
                if data['status'] == 'normal':
                    cursor.execute("DELETE FROM calendario_marcacoes WHERE id = %s", (existente['id'],))
                    conn.commit()
                    conn.close()
                    return jsonify({'success': True, 'message': 'Horário desmarcado!'})
                
                # Transformar em VAGO
                elif data['status'] == 'vago':
                    cursor.execute("""
                        UPDATE calendario_marcacoes 
                        SET status = 'vago', professor_id = NULL 
                        WHERE id = %s
                    """, (existente['id'],))
                    conn.commit()
                    
                    # Notificar outros professores
                    cursor.execute("SELECT id FROM professores WHERE id != %s", (professor_id,))
                    professores = cursor.fetchall()
                    
                    for prof in professores:
                        cursor.execute("""
                            INSERT INTO notificacoes 
                            (tipo, turma_id, turma_nome, curso_nome, dia_semana, dia_nome, horario_id, professor_origem_nome, professor_destino_id, status, mensagem)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, ('vago_disponivel', data['turma_id'], turma_nome, curso_nome, data['dia_semana'], get_dia_nome(data['dia_semana']), data['horario_id'], get_nome_professor(professor_id), prof['id'], 'pendente', f'Horario VAGO disponivel por {get_nome_professor(professor_id)}'))
                    
                    conn.commit()
                    conn.close()
                    return jsonify({'success': True, 'message': 'Horário disponibilizado como VAGO!'})
                
                # Manter como OCUPADO
                elif data['status'] == 'ocupado':
                    cursor.execute("""
                        UPDATE calendario_marcacoes 
                        SET status = 'ocupado', professor_id = %s 
                        WHERE id = %s
                    """, (professor_id, existente['id']))
                    conn.commit()
                    conn.close()
                    return jsonify({'success': True, 'message': 'Horário ocupado!'})
        
        conn.close()
        return jsonify({'success': False, 'message': 'Operação não permitida'}), 400
        
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
        
        cursor.execute("""
            INSERT INTO usuarios (usuario, senha, nome_completo, tipo)
            VALUES (%s, MD5(%s), %s, %s)
        """, (data['usuario'], data['senha'], data['nome_completo'], data['tipo']))
        
        usuario_id = cursor.lastrowid
        
        if data['tipo'] == 'professor':
            disciplina = data.get('disciplina', '')
            professor_tipo = data.get('professor_tipo', 'Base Comum')
            cursor.execute("""
                INSERT INTO professores (usuario_id, disciplina, tipo)
                VALUES (%s, %s, %s)
            """, (usuario_id, disciplina, professor_tipo))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Usuário criado com sucesso', 'id': usuario_id})
    except Exception as e:
        print("Erro ao criar usuário:", str(e))
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
            updates.append("senha = MD5(%s)")
            params.append(data['senha'])
        
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
        
        cursor.execute("DELETE FROM usuarios WHERE id = %s", (id,))
        conn.commit()
        conn.close()
        
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
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recuperacao_senha (
                id INT PRIMARY KEY AUTO_INCREMENT,
                email VARCHAR(100) NOT NULL,
                codigo VARCHAR(10) NOT NULL,
                expira_em DATETIME NOT NULL,
                usado BOOLEAN DEFAULT 0,
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

        cursor.execute("UPDATE usuarios SET senha = MD5(%s) WHERE usuario = %s", (nova_senha, usuario))
        cursor.execute("UPDATE recuperacao_senha SET usado = 1 WHERE id = %s", (recuperacao['id'],))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Senha alterada com sucesso'})

    except Exception as e:
        print("Erro ao alterar senha:", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500


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
