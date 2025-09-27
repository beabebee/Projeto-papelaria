from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer
from flask_moment import Moment
from chatbot_config import get_simple_bot_response, faqs_list 

load_dotenv()

######################################
# Configuração inicial
######################################
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') # Chave secreta para proteger sessões
app.config['SECURITY_PASSWORD_SALT'] = os.getenv('SECURITY_PASSWORD_SALT')

moment = Moment(app)

# Configuração do Flask-Mail
app.config.update(
    MAIL_SERVER=os.getenv('MAIL_SERVER', 'smtp.gmail.com'),
    MAIL_PORT=int(os.getenv('MAIL_PORT', '587')),
    MAIL_USE_TLS=os.getenv('MAIL_USE_TLS', 'True') == 'True',
    MAIL_USE_SSL=os.getenv('MAIL_USE_SSL', 'False') == 'True',
    MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_DEFAULT_SENDER=os.getenv('MAIL_DEFAULT_SENDER')
)

mail = Mail(app)

# Configuração do banco de dados
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///papelaria.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

######################################
# Sistema de Autenticação
######################################
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), default='funcionario')

    def verificar_senha(self, senha):
        return check_password_hash(self.senha, senha)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

######################################
# Modelos do Negócio
######################################
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(200))
    preco = db.Column(db.Float, nullable=False)
    quantidade = db.Column(db.Integer, default=0)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    telefone = db.Column(db.String(20))
    endereco = db.Column(db.String(200))
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    quantidade = db.Column(db.Integer, nullable=False)
    data_venda = db.Column(db.DateTime, default=datetime.utcnow)
    valor_total = db.Column(db.Float, nullable=False)
    
    cliente = db.relationship('Cliente', backref='vendas')
    produto = db.relationship('Produto', backref='vendas')

######################################
# Inicialização do banco
######################################
with app.app_context():
    db.create_all()
    
    if not Usuario.query.filter_by(email='admin.papelaria@example.com').first():
        admin = Usuario(
            nome='Administrador',
            email='admin.papelaria@example.com',
            senha=generate_password_hash('admin123'),
            tipo='admin'
        )
        db.session.add(admin)
        db.session.commit()

######################################
# Rotas de autenticação
######################################
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            flash(f'Bem-vindo(a), {usuario.nome}!', 'success')
            return redirect(url_for('home'))
        
        flash('Credenciais inválidas!', 'danger')
    
    return render_template('auth/login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        try:
            novo_usuario = Usuario(
                nome=request.form['nome'],
                email=request.form['email'],
                senha=generate_password_hash(request.form['senha']),
                tipo='funcionario'
            )
            db.session.add(novo_usuario)
            db.session.commit()

            # Chama o envio do email de boas-vindas
            enviar_email_boas_vindas(novo_usuario)

            flash('Cadastro realizado! Faça login.', 'success')
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            flash('Email já cadastrado!', 'danger')
    
    return render_template('auth/cadastro.html')


def enviar_email_boas_vindas(usuario):
    msg = Message(
        subject="Bem-vindo à Papelaria Arte & Papel!",
        recipients=[usuario.email],
        html=f"""
        <h2>Olá, {usuario.nome}!</h2>
        <p>Seu cadastro foi realizado com sucesso.</p>
        <p>Seu login é: {usuario.email}</p>
        <p><a href="{url_for('login', _external=True)}">Clique aqui para acessar o sistema</a></p>
        """
    )
    mail.send(msg)

@app.route('/esqueci-minha-senha', methods=['GET', 'POST'])
def esqueci_minha_senha():
    if request.method == 'POST':
        email = request.form['email']
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario:
            # Enviar email com link para redefinir senha
            enviar_email_redefinicao_senha(usuario)
            flash('Email de redefinição de senha enviado!', 'success')
            return redirect(url_for('login'))
        flash('Email não encontrado!', 'danger')
    return render_template('auth/esqueci_minha_senha.html')

def enviar_email_redefinicao_senha(usuario):
    token = gerar_token_redefinicao_senha(usuario)
    msg = Message(
        subject="Redefinição de Senha - Papelaria Arte & Papel",
        recipients=[usuario.email],
        html=f"""
        <h2>Olá, {usuario.nome}!</h2>
        <p>Recebemos um pedido para redefinir sua senha.</p>
        <p>Para redefinir sua senha, clique no link abaixo:</p>
        <p><a href="{url_for('redefinir_senha', token=token, _external=True)}">Redefinir Senha</a></p>
        """
    )
    mail.send(msg)

def gerar_token_redefinicao_senha(usuario):
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return s.dumps({'user_id': usuario.id}, salt=app.config['SECURITY_PASSWORD_SALT'])

@app.route('/redefinir-senha/<token>', methods=['GET', 'POST'])
def redefinir_senha(token):
    usuario = verificar_token_redefinicao_senha(token)
    if not usuario:
        flash('O link é inválido ou expirou.', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        nova_senha = request.form['senha']
        usuario.senha = generate_password_hash(nova_senha)
        db.session.commit()
        flash('Senha alterada com sucesso!', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/redefinir_senha.html', token=token)

def verificar_token_redefinicao_senha(token, tempo_expiracao=900000):
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        data = s.loads(
            token,
            salt=app.config['SECURITY_PASSWORD_SALT'],
            max_age=tempo_expiracao
        )
    except Exception:
        return None
    return Usuario.query.get(data['user_id'])

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

######################################
# Rotas principais
######################################
@app.route('/')
@login_required
def home():
    from recommendation_engine import get_best_sellers
    # Busca os 5 produtos mais vendidos
    produtos_mais_vendidos = get_best_sellers(n=6)
    
    # Envia a lista para o template
    return render_template('index.html', 
                         titulo="Papelaria Arte & Papel",
                         mensagem="Bem-vindo ao sistema de gerenciamento!",
                         produtos_mais_vendidos=produtos_mais_vendidos)

# Rotas de Produtos
@app.route('/produtos')
@login_required
def listar_produtos():
    produtos = Produto.query.all()
    return render_template("produtos/listar.html", produtos=produtos)

@app.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
def cadastrar_produto():
    if request.method == 'POST':
        novo_produto = Produto(
            nome=request.form['nome'],
            descricao=request.form['descricao'],
            preco=float(request.form['preco']),
            quantidade=int(request.form['quantidade'])
        )
        db.session.add(novo_produto)
        db.session.commit()
        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_produtos'))
    return render_template('produtos/cadastrar.html')

# Editar produtos
@app.route('/produtos/editar/<int:id>', methods=['GET', 'POST'])
def editar_produto(id):
    produto = Produto.query.get_or_404(id)
    if request.method == 'POST':
        produto.nome = request.form['nome']
        produto.descricao = request.form['descricao']
        produto.preco = float(request.form['preco'])
        produto.quantidade = int(request.form['quantidade'])
        db.session.commit()
        flash('Produto atualizado com sucesso!', 'success')
        return redirect(url_for('listar_produtos'))
    return render_template('produtos/editar.html', produto=produto)

# Excluir produtos
@app.route('/produtos/deletar/<int:id>', methods=['POST'])
def deletar_produto(id):
    produto = Produto.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()
    flash('Produto excluído com sucesso!', 'success')
    return redirect(url_for('listar_produtos'))

# Rotas de Clientes
@app.route('/clientes')
@login_required
def listar_clientes():
    clientes = Cliente.query.all()
    return render_template('clientes/listar.html', clientes=clientes)

@app.route('/clientes/novo', methods=['GET', 'POST'])
@login_required
def cadastrar_cliente():
    if request.method == 'POST':
        novo_cliente = Cliente(
            nome=request.form['nome'],
            email=request.form['email'],
            telefone=request.form['telefone'],
            endereco=request.form['endereco']
        )
        db.session.add(novo_cliente)
        db.session.commit()
        flash('Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('listar_clientes'))
    return render_template('clientes/cadastrar.html')

# Editar Cliente
@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cliente.nome = request.form['nome']
        cliente.email = request.form['email']
        cliente.telefone = request.form['telefone']
        cliente.endereco = request.form['endereco']
        db.session.commit()
        flash('Cliente atualizado com sucesso!', 'success')
        return redirect(url_for('listar_clientes'))
    return render_template('clientes/editar.html', cliente=cliente)

# Excluir Cliente
@app.route('/clientes/deletar/<int:id>', methods=['POST'])
def deletar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    db.session.delete(cliente)
    db.session.commit()
    flash('Cliente excluído com sucesso!', 'success')
    return redirect(url_for('listar_clientes'))

# Rotas de Vendas
@app.route('/vendas')
@login_required
def listar_vendas():
    vendas = Venda.query.all()
    return render_template('vendas/listar.html', vendas=vendas)

@app.route('/vendas/nova', methods=['GET', 'POST'])
@login_required
def nova_venda():
    if request.method == 'POST':
        try:
            produto = Produto.query.get(request.form['produto_id'])
            if produto.quantidade < int(request.form['quantidade']):
                flash('Estoque insuficiente!', 'danger')
                return redirect(url_for('nova_venda'))
            
            nova_venda = Venda(
                cliente_id=request.form['cliente_id'],
                produto_id=request.form['produto_id'],
                quantidade=int(request.form['quantidade']),
                valor_total=float(produto.preco) * int(request.form['quantidade'])
            )
            
            produto.quantidade -= nova_venda.quantidade
            db.session.add(nova_venda)
            db.session.commit()
            flash('Venda registrada!', 'success')
            return redirect(url_for('listar_vendas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'danger')
            return redirect(url_for('nova_venda'))
    
    clientes = Cliente.query.all()
    produtos = Produto.query.filter(Produto.quantidade > 0).all()
    return render_template('vendas/nova.html', clientes=clientes, produtos=produtos)

# Página de Suporte
@app.route('/suporte', methods=['GET', 'POST'])
def suporte():
    if request.method == 'POST':
        destinatario = request.form['destinatario']
        solicitante = request.form['solicitante']
        assunto = request.form['assunto']
        mensagem = request.form['mensagem']
        data_hora = request.form['data_hora']

        msg = Message(
            subject=f"[Suporte] {traduzir_assunto(assunto)}",
            recipients=[destinatario, solicitante],
            body=f"""
            Mensagem de: {solicitante}
            Data e Hora: {data_hora}

            {mensagem}
            """
        )
        mail.send(msg)
        flash('Sua mensagem foi enviada. Entraremos em contato em breve!', 'success')
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        return redirect(url_for('login'))

    return render_template('support/support.html', data_hora=datetime.now(), mail_owner=os.getenv('MAIL_OWNER'))

def traduzir_assunto(assunto):
    traducoes = {
        "erro_sistema": "Erro no sistema",
        "problemas_cadastro": "Problemas no cadastro de produtos",
        "problema_acesso": "Problema de acesso (login/senha)",
        "lentidao_instabilidade": "Lentidão ou instabilidade no sistema",
        "solicitacao_suporte": "Solicitação de suporte remoto",
        "sugestao_melhoria": "Sugestão de melhoria no sistema",
        "duvidas_sistema": "Dúvidas sobre o sistema",
        "pedido_exclusao": "Pedido de exclusão ou criação de conta",
        "solicitacao_ferias": "Solicitação de férias/ausência",
        "alteracao_informacoes": "Alteração de informações cadastrais",
        "comunicacao_problema": "Comunicação de problema interno",
        "pedido_material": "Pedido de material ou recurso",
        "duvidas_politicas": "Dúvidas sobre políticas da empresa",
        "reclamacao_feedback": "Reclamação ou feedback",
        "comunicacao_geral": "Comunicação geral ou aviso importante"
    }
    return traducoes.get(assunto, assunto)


# Rotas do Chatbot e FAQ
@app.route('/faq')
@login_required
def faq():
    return render_template('support/faq.html', faqs=faqs_list)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("mensagem")
    if not user_message:
        return jsonify({"resposta": "Por favor, digite uma mensagem."})

    bot_response = get_simple_bot_response(user_message)
    return jsonify({"resposta": bot_response})

# Rotas de Recomendação
@app.route('/recomendar/cliente/<int:id>')
@login_required
def recomendar_para_cliente(id):
    from recommendation_engine import recommend_for_client_knn, get_best_sellers
    
    # Tenta obter recomendações personalizadas primeiro
    produtos_recomendados = recommend_for_client_knn(client_id=id)
    
    # Se a lista de recomendações personalizadas estiver vazia...
    if not produtos_recomendados:
        # ...busque os produtos mais vendidos como um fallback.
        produtos_recomendados = get_best_sellers(n=3) # Pega os 3 mais vendidos
        tipo_recomendacao = 'fallback'
    else:
        tipo_recomendacao = 'personalizada'


   # Transforma a lista de produtos em um formato JSON
    resultado_produtos = [
        {'id': p.id, 'nome': p.nome, 'preco': p.preco} 
        for p in produtos_recomendados
    ]
    
    # Retorna um objeto JSON com o tipo e a lista de produtos
    return jsonify({
        'tipo': tipo_recomendacao,
        'produtos': resultado_produtos
    })

######################################
# Inicialização
######################################
if __name__ == '__main__':
    app.run(debug=True)