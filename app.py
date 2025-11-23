from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer
from flask_moment import Moment
from chatbot_config import get_simple_bot_response, faqs_list 
from classification_engine import carregar_modelos
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail as SendGridMail
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import io
import base64

kmeans_model, scaler_model = carregar_modelos()

load_dotenv()

######################################
# Configuração inicial
######################################
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') # Chave secreta para proteger sessões
app.config['SECURITY_PASSWORD_SALT'] = os.getenv('SECURITY_PASSWORD_SALT')

moment = Moment(app)

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

def enviar_email_sendgrid(para_emails, assunto, html_conteudo):
    """
    Função helper para disparar emails usando a API do SendGrid.
    'para_emails' pode ser um único email (string) ou uma lista de emails.
    """
    sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
    message = SendGridMail(
        from_email=os.getenv('MAIL_DEFAULT_SENDER'),
        to_emails=para_emails,
        subject=assunto,
        html_content=html_conteudo
    )

    try:
        response = sg.send(message)
        app.logger.info(f"Email enviado para {para_emails}, status: {response.status_code}")
        return response.status_code
    except Exception as e:
        app.logger.error(f"Erro ao enviar email via SendGrid: {e}")
        return None

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
        assunto = "Bem-vindo à Papelaria Arte & Papel!"
        html = f"""
        <h2>Olá, {usuario.nome}!</h2>
        <p>Seu cadastro foi realizado com sucesso.</p>
        <p>Seu login é: {usuario.email}</p>
        <p><a href="{url_for('login', _external=True)}">Clique aqui para acessar o sistema</a></p>
        """
        enviar_email_sendgrid(usuario.email, assunto, html)

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
    assunto = "Redefinição de Senha - Papelaria Arte & Papel"
    html = f"""
        <h2>Olá, {usuario.nome}!</h2>
        <p>Recebemos um pedido para redefinir sua senha.</p>
        <p>Para redefinir sua senha, clique no link abaixo:</p>
        <p><a href="{url_for('redefinir_senha', token=token, _external=True)}">Redefinir Senha</a></p>
        """
    enviar_email_sendgrid(usuario.email, assunto, html)

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

def enviar_email_recomendacao(cliente, produtos, tipo):
    """
    Envia um email de recomendação para um cliente específico.
    """
    html_lista_produtos = "<ul style='list-style-type: none; padding-left: 0;'>"
    for p in produtos:
        preco_formatado = f"R$ {p.preco:.2f}".replace('.', ',')
        html_lista_produtos += f"""
        <li style='margin-bottom: 15px; border: 1px solid #ddd; padding: 10px; border-radius: 5px;'>
            <strong style='font-size: 1.1em;'>{p.nome}</strong><br>
            <span style='color: #333;'>{p.descricao or 'Sem descrição'}</span><br>
            <span style='font-size: 1.1em; font-weight: bold; color: #0056b3;'>{preco_formatado}</span>
        </li>
        """
    html_lista_produtos += "</ul>"

    if tipo == 'personalizada':
        titulo = f"Olá, {cliente.nome}! Vimos que você pode gostar destes produtos:"
        assunto_base = "Temos sugestões especiais para você!"
    else:
        titulo = f"Olá, {cliente.nome}! Confira nossos produtos mais populares:"
        assunto_base = "Confira os mais vendidos da Papelaria Arte & Papel!"

    assunto_completo = f"{assunto_base} - Papelaria Arte & Papel"

    html = f"""
        <div style='font-family: Arial, sans-serif; line-height: 1.6;'>
            <h2 style='color: #004a99;'>{titulo}</h2>
            <p>Aqui estão algumas sugestões que separamos para você:</p>
            {html_lista_produtos}
            <p>Esperamos te ver em breve!</p>
            <hr>
            <p style='font-size: 0.9em; color: #777;'>
                Atenciosamente,<br>Equipe Arte & Papel
            </p>
        </div>
        """
    enviar_email_sendgrid(cliente.email, assunto_completo, html)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

######################################
# Rotas principais
######################################

def gerar_grafico_vendas():
    vendas = db.session.query(
        Venda.data_venda, 
        Venda.valor_total
    ).all()
    
    if not vendas:
        return None

    df = pd.DataFrame(vendas, columns=['data', 'valor'])
    df['data'] = pd.to_datetime(df['data']).dt.date
    df_agrupado = df.groupby('data')['valor'].sum().reset_index()
    df_agrupado['data'] = pd.to_datetime(df_agrupado['data']).dt.strftime('%d/%m/%Y')

    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(10, 5))
    
    cores = sns.color_palette("blend:#007bff,#e83e8c", n_colors=len(df_agrupado))
    
    grafico = sns.barplot(x='data', y='valor', data=df_agrupado, palette=cores)
    plt.title('Receita de Vendas por Dia', color='#333333')
    plt.xlabel('Data')
    plt.ylabel('Total (R$)')
    plt.xticks(rotation=45)
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()
    return base64.b64encode(img.getvalue()).decode('utf8')

def gerar_grafico_produtos_top():
    resultados = db.session.query(
        Produto.nome, 
        db.func.sum(Venda.valor_total).label('total_vendas')
    ).join(Venda).group_by(Produto.nome).order_by(db.text('total_vendas DESC')).limit(5).all()

    if not resultados:
        return None

    df = pd.DataFrame(resultados, columns=['produto', 'total'])

    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(8, 5))
    
    cores = sns.color_palette("blend:#e83e8c,#007bff", n_colors=len(df))
    
    sns.barplot(x='total', y='produto', data=df, palette=cores, orient='h')
    plt.title('Top 5 Produtos por Receita', color='#333333')
    plt.xlabel('Receita Total (R$)')
    plt.ylabel('')
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()

    return base64.b64encode(img.getvalue()).decode('utf8')


@app.route('/')
@login_required
def home():
    from recommendation_engine import get_best_sellers
    
    produtos_mais_vendidos = get_best_sellers(n=6)
    
    grafico_vendas_img = gerar_grafico_vendas()
    grafico_top_produtos_img = gerar_grafico_produtos_top()
    
    return render_template('index.html', 
                         titulo="Papelaria Arte & Papel",
                         mensagem="Bem-vindo ao sistema de gerenciamento!",
                         produtos_mais_vendidos=produtos_mais_vendidos,
                         grafico_vendas=grafico_vendas_img,
                         grafico_produtos=grafico_top_produtos_img)

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
    from classification_engine import classificar_cliente

    clientes = Cliente.query.all()

    clientes_com_classificacao = []
    for cliente in clientes:
        classificacao = classificar_cliente(cliente.id, kmeans_model, scaler_model)
        clientes_com_classificacao.append({
            'cliente': cliente,
            'classificacao': classificacao
        })

    return render_template('clientes/listar.html', clientes_info=clientes_com_classificacao)

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

        assunto_final = f"[Suporte] {traduzir_assunto(assunto)}"

        html = f"""
        <div style='font-family: Arial, sans-serif; line-height: 1.6;'>
            <p><strong>Mensagem de:</strong> {solicitante}</p>
            <p><strong>Data e Hora:</strong> {data_hora}</p>
            <hr>
            <p style='white-space: pre-wrap;'>{mensagem}</p>
        </div>
        """
        enviar_email_sendgrid(destinatario, assunto_final, html)
        enviar_email_sendgrid(solicitante, assunto_final, html)

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

@app.route('/enviar-recomendacoes/cliente/<int:id>', methods=['POST'])
@login_required
def enviar_recomendacoes_email(id):
    from recommendation_engine import recommend_for_client_knn, get_best_sellers

    cliente = Cliente.query.get_or_404(id)
    if not cliente.email:
        return jsonify({'status': 'error', 'message': 'Cliente não possui email cadastrado.'}), 400

    produtos_recomendados = recommend_for_client_knn(client_id=id)
    tipo_recomendacao = 'personalizada'
    
    if not produtos_recomendados:
        produtos_recomendados = get_best_sellers(n=3)
        tipo_recomendacao = 'fallback'

    if not produtos_recomendados:
        return jsonify({'status': 'error', 'message': 'Nenhum produto para recomendar.'}), 400

    try:
        enviar_email_recomendacao(cliente, produtos_recomendados, tipo_recomendacao)
        return jsonify({'status': 'success', 'message': f'Email de recomendação enviado para {cliente.email}!'})
    except Exception as e:
        app.logger.error(f"Erro ao enviar email: {str(e)}")
        return jsonify({'status': 'error', 'message': 'Erro interno ao enviar o email.'}), 500

######################################
# Inicialização
######################################
if __name__ == '__main__':
    app.run(debug=True)