import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'chave_secreta_super_segura_ti'

# Definição segura de diretórios absolutos para o PythonAnywhere (usuário: intraneture)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'intranet.db')

UPLOAD_TUTORIAIS = os.path.join(BASE_DIR, 'static', 'uploads', 'tutoriais')
app.config['UPLOAD_TUTORIAIS'] = UPLOAD_TUTORIAIS
os.makedirs(UPLOAD_TUTORIAIS, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Tabela de Usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            nivel TEXT DEFAULT 'estagiario',
            ativo INTEGER DEFAULT 1,
            tentativas_erradas INTEGER DEFAULT 0,
            bloqueado_ate TEXT
        )
    ''')
    
    # Tabela de Unidades / Escolas
    cursor.execute('CREATE TABLE IF NOT EXISTS unidades (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE)')
    
    # Tabela de Equipamentos APs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Blanket_APs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, local TEXT NOT NULL, nome TEXT NOT NULL,
            mac_address TEXT NOT NULL, serial_number TEXT, localizacao TEXT NOT NULL,
            rack TEXT, switch TEXT, porta TEXT
        )
    ''')
    
    # Tabela de Tutoriais
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tutoriais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            icone TEXT DEFAULT 'fa-file-pdf',
            tipo_link TEXT NOT NULL,
            link_destino TEXT
        )
    ''')
    
    # Tabela de Logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_atividades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_nome TEXT NOT NULL,
            acao TEXT NOT NULL,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Popula com os dados iniciais de tutoriais se estiver vazia
    cursor.execute("SELECT COUNT(*) FROM tutoriais")
    if cursor.fetchone()[0] == 0:
        dados_iniciais = [
            ("Conectar Tablets na Rede", "Tutorial para conectar os Tablets na Rede Tablets-escolas.", "fa-tablet-screen-button", "externo", "https://midiasstoragesec.blob.core.windows.net/001/2025/06/wi-fi--tutorial-para-conectar-o-tablet-na-rede-tablets-escolas-v2-1.pdf"),
            ("Reset Chromebook Samsung", "Procedimento de reset do sistema para Chromebooks da Samsung.", "fa-laptop", "externo", "https://midiasstoragesec.blob.core.windows.net/001/2025/06/reset-do-sistema-do-chromebook-samsung.pdf"),
            ("Restaurar/Formatar PC", "Guia para restaurar e formatar Notebooks, Netbooks e Desktops.", "fa-computer", "externo", "https://midiasstoragesec.blob.core.windows.net/001/2025/06/restaurar-netbook.pdf"),
            ("Restauração Chromebook", "Restauração do Chromebook — Sistema Novo gerenciado sem pen drive.", "fa-chrome", "externo", "https://midiasstoragesec.blob.core.windows.net/001/2025/07/formatando-um-chromebook-gerenciado-sem-pen-drive.pdf")
        ]
        cursor.executemany("INSERT INTO tutoriais (titulo, descricao, icone, tipo_link, link_destino) VALUES (?,?,?,?,?)", dados_iniciais)
        conn.commit()

    # Cria usuário mestre
    cursor.execute("SELECT * FROM usuarios WHERE usuario = 'guilherme'")
    if not cursor.fetchone():
        senha_hash = generate_password_hash('123')
        cursor.execute('INSERT INTO usuarios (nome, usuario, senha, nivel, ativo) VALUES (?, ?, ?, ?, 1)', ('Guilherme Pires', 'guilherme', senha_hash, 'adm'))
        conn.commit()
    conn.close()

    # 1. Criação da tabela de avisos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avisos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            data_publicacao TEXT NOT NULL,
            prioridade TEXT DEFAULT 'normal'
        )
    ''')
    
    # 2. ADICIONE ESTE BLOCO AQUI (Tabela que estava faltando no seu banco):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_leitura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aviso_id INTEGER,
            usuario_id INTEGER,
            usuario_nome TEXT,
            data_leitura TEXT,
            FOREIGN KEY(aviso_id) REFERENCES avisos(id)
        )
    ''')
    
    conn.commit()
    conn.close()

    

@app.route('/')
def index():
    if 'usuario_id' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_input = request.form['usuario'].strip().lower()
        senha_input = request.form['senha'].strip()
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM usuarios WHERE usuario = ?', (usuario_input,))
        user = cursor.fetchone()
        
        if user:
            # 1. VERIFICA SE O USUÁRIO ESTÁ INATIVO NO PAINEL ADM
            if user['ativo'] != 1:
                flash('Esta conta está inativa. Contate o administrador.', 'danger')
                conn.close()
                return render_template('login.html')
            
            # 2. VERIFICA SE O USUÁRIO ESTÁ BLOQUEADO POR TENTATIVAS ERRADAS
            if user['bloqueado_ate']:
                bloqueio_limite = datetime.strptime(user['bloqueado_ate'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() < bloqueio_limite:
                    tempo_restante = int((bloqueio_limite - datetime.now()).total_seconds() / 60) + 1
                    flash(f'Conta bloqueada! Tente novamente em {tempo_restante} min.', 'danger')
                    conn.close()
                    return render_template('login.html')
                else:
                    # O tempo de bloqueio já passou, zera as tentativas erradas
                    cursor.execute('UPDATE usuarios SET tentativas_erradas = 0, bloqueado_ate = NULL WHERE id = ?', (user['id'],))
                    conn.commit()

            # 3. VALIDAÇÃO DA SENHA
            if check_password_hash(user['senha'], senha_input):
                # Login correto: limpa o contador de erros e abre a sessão
                cursor.execute('UPDATE usuarios SET tentativas_erradas = 0, bloqueado_ate = NULL WHERE id = ?', (user['id'],))
                conn.commit()
                
                session['usuario_id'] = user['id']
                session['usuario_nome'] = user['usuario']
                session['usuario_role'] = user['nivel']
                conn.close()
                return redirect(url_for('dashboard'))
            else:
                # Senha incorreta: incrementa o contador de erros
                novas_tentativas = user['tentativas_erradas'] + 1
                if novas_tentativas >= 3:
                    # 3 erros ou mais bloqueia o acesso por 5 minutos
                    liberacao_tempo = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('UPDATE usuarios SET tentativas_erradas = ?, bloqueado_ate = ? WHERE id = ?', (novas_tentativas, liberacao_tempo, user['id']))
                    flash('Acesso bloqueado por 5 minutos após 3 tentativas incorretas!', 'danger')
                else:
                    cursor.execute('UPDATE usuarios SET tentativas_erradas = ? WHERE id = ?', (novas_tentativas, user['id']))
                    flash(f'Senha incorreta! Tentativa {novas_tentativas} de 3.', 'danger')
                conn.commit()
        else:
            flash('Credenciais incorretas!', 'danger')
            
        conn.close()
    return render_template('login.html')

# Interceptação de Favicon Global
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Central de Tutoriais (Dashboard)
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST' and session.get('usuario_role') == 'adm':
        titulo = request.form['titulo'].strip()
        descricao = request.form['descricao'].strip()
        icone = request.form['icone'].strip()
        tipo_link = request.form['tipo_link']
        
        link_destino = ""
        if tipo_link == 'externo':
            link_destino = request.form['link_externo'].strip()
        elif tipo_link == 'interno':
            file = request.files.get('file_interno')
            if file and file.filename.endswith('.pdf'):
                filename = secure_filename(f"doc_{file.filename}").lower()
                file.save(os.path.join(app.config['UPLOAD_TUTORIAIS'], filename))
                link_destino = f"/static/uploads/tutoriais/{filename}"
        
        if titulo and link_destino:
            cursor.execute('INSERT INTO tutoriais (titulo, descricao, icone, tipo_link, link_destino) VALUES (?,?,?,?,?)', (titulo, descricao, icone, tipo_link, link_destino))
            conn.commit()
            flash('Novo tutorial publicado!', 'success')
            
    cursor.execute('SELECT * FROM tutoriais ORDER BY id DESC')
    lista_tutoriais = cursor.fetchall()
    conn.close()
    return render_template('dashboard.html', tutoriais=lista_tutoriais)

@app.route('/get-tutorial/<int:id>')
def get_tutorial(id):
    if 'usuario_id' not in session: return {"erro": "Não autorizado"}, 401
    conn = get_db(); cursor = conn.cursor()
    cursor.execute('SELECT * FROM tutoriais WHERE id = ?', (id,))
    row = cursor.fetchone(); conn.close()
    if row:
        return {"id": row['id'], "titulo": row['titulo'], "descricao": row['descricao'], "icone": row['icone'], "tipo_link": row['tipo_link'], "link_destino": row['link_destino']}
    return {"erro": "Não encontrado"}, 404

@app.route('/editar-tutorial/<int:id>', methods=['POST'])
def editar_tutorial(id):
    if 'usuario_id' not in session or session.get('usuario_role') != 'adm': return redirect(url_for('login'))
    titulo = request.form['titulo'].strip()
    descricao = request.form['descricao'].strip()
    icone = request.form['icone'].strip()
    tipo_link = request.form['tipo_link']
    
    conn = get_db(); cursor = conn.cursor()
    cursor.execute('SELECT link_destino FROM tutoriais WHERE id = ?', (id,))
    tutorial_antigo = cursor.fetchone()
    link_destino = tutorial_antigo['link_destino'] if tutorial_antigo else ""

    if tipo_link == 'externo':
        link_destino = request.form['link_externo'].strip()
    elif tipo_link == 'interno':
        file = request.files.get('file_interno')
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(f"doc_{file.filename}").lower()
            file.save(os.path.join(app.config['UPLOAD_TUTORIAIS'], filename))
            link_destino = f"/static/uploads/tutoriais/{filename}"

    cursor.execute('UPDATE tutoriais SET titulo=?, descricao=?, icone=?, tipo_link=?, link_destino=? WHERE id=?', (titulo, descricao, icone, tipo_link, link_destino, id))
    conn.commit(); conn.close()
    flash('Tutorial atualizado!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/deletar-tutorial/<int:id>')
def deletar_tutorial(id):
    if 'usuario_id' not in session or session.get('usuario_role') != 'adm': return redirect(url_for('login'))
    conn = get_db(); cursor = conn.cursor()
    cursor.execute('DELETE FROM tutoriais WHERE id = ?', (id,))
    conn.commit(); conn.close()
    flash('Tutorial removido!', 'success')
    return redirect(url_for('dashboard'))

# Gerenciamento de APs (Lote e Unitário)
@app.route('/aps', methods=['GET', 'POST'])
def gerenciar_aps():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    conn = get_db(); cursor = conn.cursor()
    
    if request.method == 'POST' and session.get('usuario_role') == 'adm':
        local = request.form.get('local', '').strip()
        nomes = request.form.getlist('nome[]')
        macs = request.form.getlist('mac_address[]')
        seriais = request.form.getlist('serial_number[]')
        localizacoes = request.form.getlist('localizacao[]')
        racks = request.form.getlist('rack[]')
        switches = request.form.getlist('switch[]')
        portas = request.form.getlist('porta[]')
        
        for i in range(len(nomes)):
            if nomes[i].strip():
                cursor.execute('''
                    INSERT INTO Blanket_APs (local, nome, mac_address, serial_number, localizacao, rack, switch, porta)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (local, nomes[i].strip(), macs[i].strip().upper(), seriais[i].strip().upper(), localizacoes[i].strip(), racks[i].strip(), switches[i].strip(), portas[i].strip()))
        conn.commit()
    
    busca = request.args.get('busca', '').strip()
    if busca:
        cursor.execute("SELECT * FROM Blanket_APs WHERE local LIKE ? OR nome LIKE ? ORDER BY local ASC", (f"%{busca}%", f"%{busca}%"))
    else:
        cursor.execute("SELECT * FROM Blanket_APs ORDER BY local ASC")
    lista_aps = cursor.fetchall()
    
    # NOVA QUERY: Busca as unidades trazendo a contagem de APs associados de cada uma
    cursor.execute('''
        SELECT u.id, u.nome, COUNT(a.id) as total_aps
        FROM unidades u
        LEFT JOIN Blanket_APs a ON u.nome = a.local
        GROUP BY u.id, u.nome
        ORDER BY u.nome ASC
    ''')
    lista_unidades = cursor.fetchall()
    
    conn.close()
    return render_template('aps.html', aps=lista_aps, unidades=lista_unidades, busca=busca)

@app.route('/get-ap/<int:id>')
def get_ap(id):
    conn = get_db(); cursor = conn.cursor(); cursor.execute('SELECT * FROM Blanket_APs WHERE id = ?', (id,))
    row = cursor.fetchone(); conn.close()
    return dict(row) if row else {"erro": "Não encontrado"}

@app.route('/editar-ap/<int:id>', methods=['POST'])
def editar_ap(id):
    conn = get_db(); cursor = conn.cursor()
    cursor.execute('UPDATE Blanket_APs SET local=?, nome=?, mac_address=?, serial_number=?, localizacao=?, rack=?, switch=?, porta=? WHERE id=?',
                   (request.form['local'], request.form['nome'], request.form['mac_address'].upper(), request.form['serial_number'].upper(), request.form['localizacao'], request.form['rack'], request.form['switch'], request.form['porta'], id))
    conn.commit(); conn.close()
    return redirect(url_for('gerenciar_aps'))

@app.route('/adicionar-escola', methods=['POST'])
def adicionar_escola():
    conn = get_db(); cursor = conn.cursor()
    try: cursor.execute('INSERT INTO unidades (nome) VALUES (?)', (request.form['nome_escola'].strip().upper(),)); conn.commit()
    except: pass
    conn.close()
    return redirect(url_for('gerenciar_aps'))

@app.route('/aps/deletar/<int:id>')
def deletar_ap(id):
    conn = get_db(); cursor = conn.cursor(); cursor.execute('DELETE FROM Blanket_APs WHERE id=?', (id,)); conn.commit(); conn.close()
    return redirect(url_for('gerenciar_aps'))

# Painel ADM Colaboradores
@app.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    if 'usuario_id' not in session or session.get('usuario_role') != 'adm': return redirect(url_for('dashboard'))
    conn = get_db(); cursor = conn.cursor()
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        usuario = request.form.get('usuario', '').strip().lower()
        senha = request.form.get('senha', '').strip()
        nivel = request.form.get('nivel', 'estagiario')
        if nome and usuario and senha:
            try:
                cursor.execute('INSERT INTO usuarios (nome, usuario, senha, nivel, ativo) VALUES (?, ?, ?, ?, 1)', (nome, usuario, generate_password_hash(senha), nivel))
                conn.commit()
                flash('Usuário cadastrado!', 'success')
            except: flash('Login já existente.', 'danger')
    cursor.execute('SELECT id, nome, usuario, nivel, ativo FROM usuarios ORDER BY id DESC'); lista_usuarios = cursor.fetchall(); conn.close()
    return render_template('usuarios.html', usuarios=lista_usuarios)

@app.route('/editar-senha-usuario/<int:id>', methods=['POST'])
def editar_senha_usuario(id):
    conn = get_db(); cursor = conn.cursor(); cursor.execute('UPDATE usuarios SET senha=? WHERE id=?', (generate_password_hash(request.form.get('nova_senha').strip()), id)); conn.commit(); conn.close()
    flash('Senha atualizada!', 'success')
    return redirect(url_for('usuarios'))

@app.route('/usuarios/deletar/<int:id>')
def deletar_usuario(id):
    if 'usuario_id' not in session or session.get('usuario_role') != 'adm':
        return redirect('/login')
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM usuarios WHERE id=?', (id,))
    conn.commit()
    conn.close()
    
    flash('Usuário removido.', 'success')
    # Corrigido: Redireciona direto para a URL em formato string
    return redirect('/usuarios')

# 1. ROTA PARA ALTERNAR STATUS (INATIVAR / ATIVAR)
@app.route('/alternar-status/<int:id>')
def alternar_status(id):
    if 'usuario_id' not in session or session.get('usuario_role') != 'adm':
        return redirect(url_for('login'))
        
    conn = get_db()
    cursor = conn.cursor()
    
    # Pega o status atual do usuário para inverter
    cursor.execute("SELECT ativo FROM usuarios WHERE id = ?", (id,))
    usuario = cursor.fetchone()
    
    if usuario:
        # Se estiver usando row_factory=sqlite3.Row usa usuario['ativo'], senão usuario[0]
        status_atual = usuario['ativo'] if hasattr(usuario, 'keys') else usuario[0]
        novo_status = 0 if status_atual == 1 else 1
        
        cursor.execute("UPDATE usuarios SET ativo = ? WHERE id = ?", (novo_status, id))
        conn.commit()
        flash('Status do usuário atualizado com sucesso!', 'success')
        
    conn.close()
    return redirect('/usuarios') # Ajuste para o nome da sua rota de usuários



    

@app.route('/editar-escola/<int:id>', methods=['POST'])
def editar_escola(id):
    if 'usuario_id' not in session or session.get('usuario_role') != 'adm': 
        return redirect(url_for('login'))
    
    novo_nome = request.form.get('nome_escola', '').strip().upper()
    if novo_nome:
        conn = get_db()
        cursor = conn.cursor()
        
        # Pega o nome antigo para atualizar também as referências na Blanket_APs se necessário
        cursor.execute('SELECT nome FROM unidades WHERE id = ?', (id,))
        antigo = cursor.fetchone()
        
        if antigo:
            # Atualiza o nome da unidade
            cursor.execute('UPDATE unidades SET nome = ? WHERE id = ?', (novo_nome, id))
            # Atualiza em cascata os APs que usavam o nome antigo
            cursor.execute('UPDATE Blanket_APs SET local = ? WHERE local = ?', (novo_nome, antigo['nome']))
            conn.commit()
            flash('Unidade/Escola renomeada com sucesso!', 'success')
        conn.close()
        
    return redirect(url_for('gerenciar_aps'))

# 1. ROTA PARA EXIBIR A TELA DE AVISOS
@app.route('/avisos')
def gerenciar_avisos():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Força a criação da tabela se não existir
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_leitura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aviso_id INTEGER,
            usuario_id INTEGER,
            usuario_nome TEXT,
            data_leitura TEXT,
            FOREIGN KEY(aviso_id) REFERENCES avisos(id)
        )
    ''')
    conn.commit()
    
    # Busca todos os avisos do mais recente para o mais antigo
    cursor.execute("SELECT * FROM avisos ORDER BY id DESC")
    lista_avisos = [dict(row) for row in cursor.fetchall()]
    
    # Se for Administrador, puxa os logs de quem já leu cada aviso
    logs_por_aviso = {}
    if session.get('usuario_role') == 'adm':
        cursor.execute("SELECT * FROM logs_leitura ORDER BY data_leitura DESC")
        todos_logs = cursor.fetchall()
        for log in todos_logs:
            a_id = log['aviso_id']
            if a_id not in logs_por_aviso:
                logs_por_aviso[a_id] = []
            logs_por_aviso[a_id].append(f"{log['usuario_nome']} ({log['data_leitura']})")
            
    # Verifica quais avisos o usuário atual JÁ MARCOU como lido para sumir o botão dele
    cursor.execute("SELECT aviso_id FROM logs_leitura WHERE usuario_id = ?", (session['usuario_id'],))
    avisos_lidos = [row[0] for row in cursor.fetchall()]
    
    # Injeta os dados extras dentro do dicionário de cada aviso antes de mandar pro HTML
    for aviso in lista_avisos:
        aviso['lido_por_mim'] = aviso['id'] in avisos_lidos
        aviso['leitores'] = logs_por_aviso.get(aviso['id'], [])
        
    conn.close()
    
    # ALTERADO: Removemos a contagem manual e fixa que travava a bolinha vermelha.
    # O template 'avisos.html' agora vai herdar o total do context_processor sem conflito!
    return render_template('avisos.html', avisos=lista_avisos)

# 2. NOVA ROTA: REGISTRAR CHECK-IN DE LEITURA
@app.route('/checkin-aviso/<int:id>')
def checkin_aviso(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    usuario_id = session['usuario_id']
    usuario_nome = session.get('usuario_nome', 'Usuário')
    data_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Evita duplicar o mesmo check-in se ele clicar duas vezes
    cursor.execute("SELECT id FROM logs_leitura WHERE aviso_id = ? AND usuario_id = ?", (id, usuario_id))
    existe = cursor.fetchone()
    
    if not existe:
        cursor.execute("INSERT INTO logs_leitura (aviso_id, usuario_id, usuario_nome, data_leitura) VALUES (?, ?, ?, ?)",
                       (id, usuario_id, usuario_nome, data_atual))
        conn.commit()
        flash('Confirmação de leitura registrada!', 'success')
        
    conn.close()
    return redirect(url_for('gerenciar_avisos'))

# 2. ROTA PARA ADICIONAR AVISO (APENAS ADM)
@app.route('/adicionar-aviso', methods=['POST'])
def adicionar_aviso():
    if 'usuario_id' not in session or session.get('usuario_role') != 'adm':
        return redirect(url_for('login'))
        
    titulo = request.form.get('titulo', '').strip()
    conteudo = request.form.get('conteudo', '').strip()
    prioridade = request.form.get('prioridade', 'normal')
    data_atual = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    if titulo and conteudo:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO avisos (titulo, conteudo, data_publicacao, prioridade) VALUES (?, ?, ?, ?)',
                       (titulo, conteudo, data_atual, prioridade))
        conn.commit()
        conn.close()
        flash('Aviso publicado com sucesso!', 'success')
    return redirect(url_for('gerenciar_avisos'))

# 3. ROTA PARA DELETAR AVISO (APENAS ADM)
@app.route('/deletar-aviso/<int:id>')
def deletar_aviso(id):
    if 'usuario_id' not in session or session.get('usuario_role') != 'adm':
        return redirect(url_for('login'))
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM avisos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Aviso removido com sucesso!', 'success')
    return redirect(url_for('gerenciar_avisos'))

# CONTEXT PROCESSOR GLOBAL: Injeta a contagem em todas as páginas do sistema

@app.context_processor
def injetar_avisos_pendentes():
    if 'usuario_id' not in session:
        return dict(total_avisos_ativos=0)
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Query corrigida: Conta os avisos onde NÃO existe um registro de leitura para o usuário atual
        cursor.execute('''
            SELECT COUNT(a.id) 
            FROM avisos a
            LEFT JOIN logs_leitura l ON a.id = l.aviso_id AND l.usuario_id = ?
            WHERE l.id IS NULL
        ''', (session['usuario_id'],))
        
        avisos_pendentes = cursor.fetchone()[0]
        conn.close()
        
        return dict(total_avisos_ativos=avisos_pendentes)
    except Exception as e:
        print(f"Erro no context_processor: {e}")
        return dict(total_avisos_ativos=0)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 1. A FUNÇÃO INIT_DB FICA SOLTA NO ARQUIVO (FORA DO IF __NAME__)
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # ... Suas outras criações de tabela ficam aqui (usuarios, Blanket_APs, etc.) ...

    # Criando a tabela de avisos com o banco aberto:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS avisos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            data_publicacao TEXT NOT NULL,
            prioridade TEXT DEFAULT 'normal'
        )
    ''')
    
    conn.commit()
    conn.close() # Fecha o banco certinho aqui

# 2. O BLOCO PRINCIPAL QUE LIGA O SERVIDOR
if __name__ == '__main__':
    init_db()  # Executa a criação das tabelas primeiro
    app.run(debug=True, port=5000)  # Inicia o servidor Flask por último