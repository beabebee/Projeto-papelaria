import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from app import db, Venda, Produto  # Importa os modelos do seu app
from collections import Counter

def get_purchase_matrix():
    """
    Busca os dados de vendas do banco e os transforma em uma matriz
    [cite_start]onde as linhas são clientes e as colunas são produtos. [cite: 313, 314, 315, 316, 317]
    O valor 1 significa que o cliente comprou o produto.
    """
    # Consulta para pegar pares distintos de (cliente, produto)
    sales_query = db.session.query(Venda.cliente_id, Venda.produto_id).distinct().all()
    
    if not sales_query:
        return None

    df_sales = pd.DataFrame(sales_query, columns=['cliente_id', 'produto_id'])
    
    # Usa o crosstab do pandas para criar a matriz cliente-produto
    user_product_matrix = pd.crosstab(df_sales['cliente_id'], df_sales['produto_id'])
    
    return user_product_matrix

# versão 1: simples, sem KNN
def recommend_for_client(client_id, n=3):
    """
    Recomenda 'n' produtos para um cliente específico com base no cliente mais similar.
    [cite_start]Esta é a implementação do requisito básico. [cite: 410, 411, 413]
    """
    matrix = get_purchase_matrix()
    
    # Retorna uma lista vazia se não houver dados ou se o cliente não tiver compras
    if matrix is None or client_id not in matrix.index:
        return []

    # [cite_start]Calcula a similaridade de cosseno entre todos os clientes [cite: 397, 398]
    client_similarity = cosine_similarity(matrix)
    sim_df = pd.DataFrame(client_similarity, index=matrix.index, columns=matrix.index)

    # Encontra os clientes mais parecidos com o cliente alvo
    similar_clients = sim_df[client_id].drop(client_id).sort_values(ascending=False)
    
    # Se não houver outros clientes para comparar, retorna lista vazia
    if similar_clients.empty:
        return []

    # [cite_start]Pega o ID do cliente mais parecido (o "vizinho" mais próximo) [cite: 411]
    closest_client_id = similar_clients.index[0]

    # Pega os produtos que o vizinho comprou
    vizinho_comprou = matrix.loc[closest_client_id]
    
    # Pega os produtos que o cliente alvo já comprou
    alvo_comprou = matrix.loc[client_id]
    
    # Identifica os produtos que o vizinho comprou (valor 1) e o alvo não (valor 0)
    recommended_product_ids = vizinho_comprou[(vizinho_comprou == 1) & (alvo_comprou == 0)].index.tolist()

    # Busca os objetos de Produto no banco de dados e retorna os 'n' primeiros
    recommended_products = Produto.query.filter(Produto.id.in_(recommended_product_ids)).limit(n).all()
    
    return recommended_products

# versão 2: complexa, utiliza comparação com mais de um vizinho 
def recommend_for_client_knn(client_id, k=3, n=3):
    """
    Recomenda produtos com base nos 'k' vizinhos mais próximos.
    [cite_start]Esta é a implementação do RECURSO EXTRA. [cite: 469, 451]
    """
    matrix = get_purchase_matrix()
    if matrix is None or client_id not in matrix.index:
        return []

    client_similarity = cosine_similarity(matrix)
    sim_df = pd.DataFrame(client_similarity, index=matrix.index, columns=matrix.index)

    # 1. Encontra os 'k' vizinhos mais próximos
    similar_clients = sim_df[client_id].drop(client_id).sort_values(ascending=False)
    if similar_clients.empty:
        return []
    top_k_neighbors_ids = similar_clients.head(k).index

    # 2. Coleta todos os produtos que os vizinhos compraram e o alvo não
    alvo_comprou = matrix.loc[client_id]
    recommended_product_ids = []
    
    for neighbor_id in top_k_neighbors_ids:
        vizinho_comprou = matrix.loc[neighbor_id]
        new_products = vizinho_comprou[(vizinho_comprou == 1) & (alvo_comprou == 0)].index.tolist()
        recommended_product_ids.extend(new_products)

    # 3. Conta a frequência dos produtos e pega os mais populares
    if not recommended_product_ids:
        return []
    
    product_counts = Counter(recommended_product_ids)
    most_common_product_ids = [pid for pid, count in product_counts.most_common(n)]

    # 4. Retorna os 'n' produtos mais populares
    recommended_products = Produto.query.filter(Produto.id.in_(most_common_product_ids)).all()
    
    return recommended_products

def get_best_sellers(n=5):
    """
    Busca os 'n' produtos mais vendidos com base na quantidade total em Vendas.
    """
    best_sellers = db.session.query(
        Produto,
        db.func.sum(Venda.quantidade).label('total_vendido')
    ).join(Venda).group_by(Produto.id).order_by(db.desc('total_vendido')).limit(n).all()
    
    # A consulta retorna uma lista de tuplas (Objeto Produto, total_vendido)
    # Nós queremos apenas a lista de objetos Produto.
    return [produto for produto, total in best_sellers]