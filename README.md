# Sistema de Registro de Aulas — IFPI

Sistema web desenvolvido como Projeto Integrador do Instituto Federal do Piauí (IFPI), com o objetivo de digitalizar e automatizar o registro de presença e aulas dos professores.

## Sobre o Projeto

O sistema permite que professores registrem suas aulas de forma prática, acompanhem o histórico de registros e visualizem um calendário com os horários de cada turma. A plataforma conta também com uma área administrativa para gestão de usuários e auditoria de logs.

O backend foi desenvolvido em Python com Flask e suporta dois bancos de dados: MySQL para ambiente local e PostgreSQL para deploy em produção via Render.

## Funcionalidades

- Login com autenticação segura (bcrypt)
- Recuperação de senha por e-mail com código de verificação
- Registro de aulas por professor e turma
- Histórico completo de registros com filtros
- Calendário do professor com marcação de aulas
- Dashboard com resumo de atividades
- Notificações internas
- Área administrativa com gestão de usuários
- Logs de auditoria para administradores
- Suporte a MySQL (local) e PostgreSQL (produção)

## Tecnologias Utilizadas

**Backend**
- Python 3
- Flask
- Flask-CORS
- PyMySQL / psycopg2
- bcrypt
- Gunicorn

**Frontend**
- HTML5
- CSS3
- JavaScript
- Chart.js

**Banco de Dados**
- MySQL (desenvolvimento local)
- PostgreSQL (produção — Render)

**Deploy**
- Render (render.yaml + Procfile)

## Estrutura do Projeto

```
ifpi-sistema/
│
├── app.py                      → Backend principal (Flask)
├── app_sqlite.py               → Versão alternativa com SQLite
├── requirements.txt            → Dependências Python
├── Procfile                    → Configuração para deploy no Render
├── render.yaml                 → Configuração do serviço Render
├── runtime.txt                 → Versão do Python
│
├── login.html                  → Página de login
├── formulario.html             → Registro de aulas
├── pagina-inicial.html         → Dashboard do professor
├── historico-de-registro.html  → Histórico de registros
├── calendario_professor.html   → Calendário de aulas
├── pagina-administrativa.html  → Painel administrativo
├── admin_usuarios.html         → Gestão de usuários
├── admin_logs.html             → Logs de auditoria
│
├── dados_reais.sql             → Dados do banco de dados
├── dados_postgres.sql          → Scripts para PostgreSQL
└── criar_tabelas_render.py     → Script de criação de tabelas
```

## Como Executar Localmente

### Pré-requisitos

- Python 3.10+
- MySQL instalado e rodando
- pip

### Passos

```bash
# 1. Clone o repositório
git clone https://github.com/SEU_USUARIO/ifpi-sistema.git
cd ifpi-sistema

# 2. Crie e ative o ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure o banco de dados MySQL
# Crie o banco ifpi_aulas e importe os dados
mysql -u root -p < dados_reais.sql

# 5. Execute a aplicação
python app.py
```

Acesse em: `http://localhost:5000`

## API — Principais Rotas

| Método | Rota | Descrição |
|---|---|---|
| POST | `/login` | Autenticação do usuário |
| GET | `/registros` | Lista registros de aulas |
| POST | `/registros` | Cria novo registro |
| PUT | `/registros/<id>` | Edita registro |
| DELETE | `/registros/<id>` | Remove registro |
| GET | `/dashboard/<id>` | Dados do dashboard do professor |
| GET | `/calendario_professor/turmas` | Turmas do professor |
| GET | `/notificacoes` | Notificações do usuário |
| GET | `/admin/usuarios` | Lista usuários (admin) |
| POST | `/recuperar/enviar_codigo` | Recuperação de senha |

## Instituição

**Instituto Federal do Piauí — IFPI**
Projeto Integrador — 2025/2026
