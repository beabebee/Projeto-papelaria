from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Nosso "cérebro" do assistente continua o mesmo
conversa_assistente = {
    "como faço para cadastrar um novo produto?": "Na página inicial, clique em 'Produtos'. Na tela de listagem, procure e clique no botão para 'Cadastrar Produto'.",
    "onde posso acessar a lista de produtos disponíveis?": "Acesse pelo botão 'Produtos' na páginas inicial.",
    "onde eu vejo a lista de clientes?": "Clique no botão 'Clientes' no menu da página inicial para ver, editar ou cadastrar novos clientes.",
    "como eu vejo a lista de vendas registradas?": "Acesse a seção 'Vendas' na página inicial",
    "como eu registro uma nova venda no sistema?": "Acesse a seção 'Vendas' a partir do menu inicial e clique em 'Nova Venda'. Você precisará selecionar o cliente e os produtos vendidos.",
    "é possível saber quais produtos recomendar a um cliente?": "Na página inicial, clique em 'Clientes'. Ao lado do botão 'Editar' você deve encontrar o botão que recomenda ao cleinte com base em suas ultimas compras.",
    "é possível alterar os dados de um cliente?": "Na lista de clientes, encontre o cliente desejado e clique na opção 'Editar' para atualizar as informações.",
    "e se eu errar o preço de um produto, posso corrigir?": "Para corrigir os dados de um produto, vá até a lista de 'Produtos', encontre o item e clique em 'Editar' para corrigir o preço e outras informações.",
    "o que devo fazer se eu esquecer minha senha?": "Na tela de login, clique no link 'Esqueci minha senha'. O sistema te guiará para criar uma nova senha através do seu e--mail.",
    "como posso contatar o suporte técnico?": "No canto superior direito de qualquer página, você encontrará um link chamado 'Suporte' para enviar uma mensagem à equipe técnica."
}

# Preparando o modelo de NLP
perguntas = list(conversa_assistente.keys())
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(perguntas)


def get_simple_bot_response(user_message):
    """
    Usa um modelo TF-IDF e similaridade de cosseno para encontrar a pergunta mais relevante.
    """
    # Converte a mensagem do usuário em um vetor com o mesmo padrão
    user_vec = vectorizer.transform([user_message])
    
    # Calcula a similaridade entre a pergunta do usuário e todas as perguntas conhecidas
    similarities = cosine_similarity(user_vec, X)
    
    # Encontra o índice da pergunta mais similar
    most_similar_index = similarities.argmax()
    
    # Pega o score de similaridade (de 0.0 a 1.0)
    confidence_score = similarities[0, most_similar_index]
    
    if confidence_score > 0.3: # Se a confiança for maior que 30%
        # Retorna a resposta da pergunta mais similar
        best_question = perguntas[most_similar_index]
        return conversa_assistente[best_question]
    else:
        return "Desculpe, não tenho certeza de como responder. Pode tentar reformular sua pergunta?"

# Para a página de FAQ, a exportação continua a mesma
faqs_list = conversa_assistente.items()