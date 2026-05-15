from flask import Flask, jsonify
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)

def get_db():
    conn = sqlite3.connect('ifpi.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    return jsonify({'message': 'API funcionando! Acesse /cursos_com_turmas'})

@app.route('/cursos_com_turmas', methods=['GET'])
def listar_cursos():
    conn = get_db()
    cursor = conn.cursor()
    
    # Criar tabelas se não existirem
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cursos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE,
            ativo INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS turmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            curso_id INTEGER,
            modulo INTEGER,
            ativo INTEGER DEFAULT 1,
            FOREIGN KEY (curso_id) REFERENCES cursos(id)
        )
    ''')
    
    # Inserir curso de Administração
    cursor.execute("INSERT OR IGNORE INTO cursos (id, nome) VALUES (1, 'Bacharelado em Administração')")
    
    # Inserir módulos 1 a 9 para Administração
    for modulo in range(1, 10):
        try:
            cursor.execute("INSERT OR IGNORE INTO turmas (curso_id, modulo) VALUES (1, ?)", (modulo,))
        except:
            pass
    
    conn.commit()
    
    # Buscar todos os cursos
    cursor.execute("SELECT id, nome FROM cursos WHERE ativo = 1")
    cursos = cursor.fetchall()
    
    resultado = []
    for curso in cursos:
        cursor.execute("SELECT modulo FROM turmas WHERE curso_id = ? AND ativo = 1 ORDER BY modulo", (curso['id'],))
        turmas = cursor.fetchall()
        
        if curso['nome'] == 'Bacharelado em Administração':
            turmas_lista = [{'modulo': t['modulo'], 'nome': f"{t['modulo']}º Módulo"} for t in turmas]
        else:
            turmas_lista = [{'modulo': t['modulo'], 'nome': f"{t['modulo']}º Módulo"} for t in turmas if t['modulo'] <= 8]
        
        resultado.append({
            'id': curso['id'],
            'nome': curso['nome'],
            'turmas': turmas_lista
        })
    
    conn.close()
    return jsonify({'cursos': resultado, 'success': True})

@app.route('/admin/criar_modulo_9', methods=['GET'])
def criar_modulo_9():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM cursos WHERE nome = 'Bacharelado em Administração'")
        curso = cursor.fetchone()
        
        if not curso:
            return jsonify({'success': False, 'message': 'Curso não encontrado'})
        
        curso_id = curso['id']
        
        # Verificar se módulo 9 já existe
        cursor.execute("SELECT id FROM turmas WHERE curso_id = ? AND modulo = 9", (curso_id,))
        existe = cursor.fetchone()
        
        if existe:
            return jsonify({'success': True, 'message': 'Módulo 9 já existe!'})
        
        # Criar módulo 9
        cursor.execute("INSERT INTO turmas (curso_id, modulo, ativo) VALUES (?, 9, 1)", (curso_id,))
        conn.commit()
        
        # Mostrar todos os módulos
        cursor.execute("SELECT modulo FROM turmas WHERE curso_id = ? ORDER BY modulo", (curso_id,))
        modulos = cursor.fetchall()
        
        conn.close()
        
        modulos_str = ', '.join([f"{m['modulo']}º" for m in modulos])
        return jsonify({'success': True, 'message': f'✅ Módulo 9 criado! Módulos disponíveis: {modulos_str}'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/debug/mostrar_tudo', methods=['GET'])
def mostrar_tudo():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM cursos")
    cursos = cursor.fetchall()
    
    cursor.execute("SELECT * FROM turmas")
    turmas = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        'cursos': [dict(c) for c in cursos],
        'turmas': [dict(t) for t in turmas]
    })

@app.route('/calendario_professor/turmas', methods=['GET'])
def get_turmas_calendario():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                t.id as turma_id,
                t.modulo,
                c.id as curso_id,
                c.nome as curso_nome
            FROM turmas t
            JOIN cursos c ON t.curso_id = c.id
            WHERE t.ativo = 1
            ORDER BY c.nome, t.modulo
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
                    'turmas': []
                }
            
            # Mostra todos os módulos (incluindo 9)
            nome_turma = f"{turma['modulo']}º Módulo"
            
            cursos_dict[curso_id]['turmas'].append({
                'id': turma['turma_id'],
                'nome': nome_turma,
                'modulo': turma['modulo']
            })
        
        # Ordenar turmas por módulo
        for curso_id in cursos_dict:
            cursos_dict[curso_id]['turmas'].sort(key=lambda x: x['modulo'])
        
        cursos = list(cursos_dict.values())
        return jsonify({'cursos': cursos, 'success': True})
        
    except Exception as e:
        print(f"Erro ao listar turmas: {e}")
        return jsonify({'cursos': [], 'success': False, 'message': str(e)}), 500

@app.route('/calendario_professor/horarios/<int:turma_id>', methods=['GET'])
def get_calendario_turma_marcacoes(turma_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Buscar informações da turma (SQLite usa ? no lugar de %s)
        cursor.execute("""
            SELECT t.*, c.nome as curso_nome
            FROM turmas t
            JOIN cursos c ON t.curso_id = c.id
            WHERE t.id = ?
        """, (turma_id,))
        
        turma = cursor.fetchone()
        conn.close()
        
        if not turma:
            return jsonify({'success': False, 'message': 'Turma não encontrada'}), 404
        
        # Nome da turma com módulo
        nome_turma = f"{turma['modulo']}º Módulo - {turma['curso_nome']}"
        
        # Horários padrão
        horarios = [
            {'id': 1, 'nome': '1ª Aula', 'inicio': '07:00', 'fim': '08:00'},
            {'id': 2, 'nome': '2ª Aula', 'inicio': '08:00', 'fim': '09:00'},
            {'id': 3, 'nome': '3ª Aula', 'inicio': '09:00', 'fim': '10:00'},
            {'id': 4, 'nome': '4ª Aula', 'inicio': '10:20', 'fim': '11:20'},
            {'id': 5, 'nome': '5ª Aula', 'inicio': '11:20', 'fim': '12:20'},
        ]
        
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
            
            for horario in horarios:
                linha_dia['horarios'].append({
                    'horario_id': horario['id'],
                    'horario_nome': horario['nome'],
                    'horario_inicio': horario['inicio'],
                    'horario_fim': horario['fim'],
                    'status': 'normal',
                    'professor_id': None,
                    'professor_nome': None
                })
            
            calendario.append(linha_dia)
        
        # Converter turma para dicionário
        turma_dict = dict(turma)
        turma_dict['nome_turma'] = nome_turma
        
        return jsonify({
            'success': True,
            'turma': turma_dict,
            'calendario': calendario
        })
        
    except Exception as e:
        print(f"Erro ao buscar calendário: {e}")
        return jsonify({'success': False, 'message': str(e)}), 50


@app.route('/debug/turmas_completas', methods=['GET'])
def debug_turmas_completas():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT t.id, t.modulo, c.nome as curso_nome
        FROM turmas t
        JOIN cursos c ON t.curso_id = c.id
        ORDER BY c.nome, t.modulo
    """)
    
    turmas = cursor.fetchall()
    conn.close()
    
    return jsonify({'turmas': [dict(t) for t in turmas]})


if __name__ == '__main__':
    print("="*60)
    print("🚀 SERVIDOR SQLITE INICIADO")
    print("="*60)
    print("📌 Acesse:")
    print("   - http://localhost:8080/cursos_com_turmas")
    print("   - http://localhost:8080/admin/criar_modulo_9")
    print("   - http://localhost:8080/debug/mostrar_tudo")
    print("="*60)
    app.run(host='0.0.0.0', port=8080, debug=True)