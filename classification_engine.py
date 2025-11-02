# Script para treinar o modelo de classificação de clientes, rodar no terminal uma vez para treinar e depois comentar o if __name__ == "__main__"

import pandas as pd
import joblib
from datetime import datetime
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# --- Constantes ---
MODELO_CLUSTER_PATH = 'modelo_cluster.pkl'
MODELO_SCALER_PATH = 'scaler_cluster.pkl'
N_CLUSTERS = 3

def calcular_rfm(app_context):
    """
    Busca todos os dados de vendas e calcula as métricas RFM
    (Recência, Frequência, Valor Monetário) para cada cliente.
    """
    print("Iniciando cálculo RFM...")
    from app import db
    
    with app_context:
        query = db.text("SELECT cliente_id, data_venda, valor_total FROM venda")
        df_vendas = pd.read_sql(query, db.engine, parse_dates=['data_venda'])

        if df_vendas.empty:
            print("Nenhum dado de venda encontrado. Abortando.")
            return None

        df_recencia = df_vendas.groupby('cliente_id')['data_venda'].max().reset_index()
        df_recencia['recencia'] = (datetime.now() - df_recencia['data_venda']).dt.days
        df_recencia = df_recencia[['cliente_id', 'recencia']]

        df_frequencia = df_vendas.groupby('cliente_id').size().reset_index(name='frequencia')

        df_monetario = df_vendas.groupby('cliente_id')['valor_total'].sum().reset_index(name='monetario')

        df_rfm = df_frequencia.merge(df_monetario, on='cliente_id')
        df_rfm = df_rfm.merge(df_recencia, on='cliente_id')

        print(f"Cálculo RFM concluído. {len(df_rfm)} clientes processados.")
        return df_rfm

def treinar_e_salvar_modelo(df_rfm):
    """
    Recebe o DataFrame RFM, treina o modelo K-Means e salva
    o modelo e o normalizador (scaler) em arquivos .pkl.
    """
    if df_rfm is None or df_rfm.empty:
        print("DataFrame RFM está vazio. Não é possível treinar.")
        return False
        
    print("Iniciando treinamento do modelo...")

    df_dados_cluster = df_rfm[['recencia', 'frequencia', 'monetario']]

    scaler = StandardScaler()
    dados_normalizados = scaler.fit_transform(df_dados_cluster)

    kmeans = KMeans(n_clusters=N_CLUSTERS, n_init=10, random_state=42)
    kmeans.fit(dados_normalizados)

    joblib.dump(kmeans, MODELO_CLUSTER_PATH)
    print(f"Modelo K-Means salvo em: {MODELO_CLUSTER_PATH}")
    joblib.dump(scaler, MODELO_SCALER_PATH)
    print(f"Modelo Scaler salvo em: {MODELO_SCALER_PATH}")
    
    print("\n--- Interpretação dos Clusters ---")
    centros_originais = scaler.inverse_transform(kmeans.cluster_centers_)
    df_centros = pd.DataFrame(centros_originais, columns=['Recência Média', 'Frequência Média', 'Valor Monetário Médio'])
    print(df_centros)
    print("\nLembre-se:")
    print(" -> 'Bom Comprador': Baixa Recência, Alta Frequência, Alto Valor")
    print(" -> 'Mau Comprador': Alta Recência, Baixa Frequência, Baixo Valor")

    return True

if __name__ == "__main__":
    print("Executando o script de treinamento de classificação de clientes...")
    from app import app
    
    app_context = app.app_context()
    
    rfm = calcular_rfm(app_context)
    
    if rfm is not None:
        treinar_e_salvar_modelo(rfm)
        print("\nTreinamento concluído com sucesso!")
    else:
        print("\nTreinamento falhou. Verifique se há dados de vendas no banco.")

# ==========================================================
# Código de Previsão
# ==========================================================
import os

MAPA_CLUSTER_NOMES = {
    0: 'Em Risco',
    1: 'Fiel',
    2: 'Alto Valor'
}

MAPA_CLUSTER_CORES = {
    0: '#dc3545',  # Vermelho (Danger)
    1: '#198754',  # Verde (Success)
    2: '#0d6efd'   # Azul (Primary)
}

def carregar_modelos():
    if not os.path.exists(MODELO_CLUSTER_PATH) or not os.path.exists(MODELO_SCALER_PATH):
        print("ERRO: Arquivos de modelo (.pkl) não encontrados.")
        print("Execute `python classification_engine.py` primeiro para treinar.")
        return None, None
        
    try:
        kmeans = joblib.load(MODELO_CLUSTER_PATH)
        scaler = joblib.load(MODELO_SCALER_PATH)
        print("Modelos de classificação carregados com sucesso.")
        return kmeans, scaler
    except Exception as e:
        print(f"Erro ao carregar modelos: {e}")
        return None, None

def calcular_rfm_cliente_unico(cliente_id):
    """
    Calcula o RFM para um ÚNICO cliente.
    Retorna um DataFrame com uma linha ou None se não houver vendas.
    """
    from app import app, db

    with app.app_context():
        query = db.text("""
            SELECT data_venda, valor_total 
            FROM venda 
            WHERE cliente_id = :cid
        """)
        df_vendas = pd.read_sql(query, db.engine, params={'cid': cliente_id}, parse_dates=['data_venda'])

    if df_vendas.empty:
        return None # Cliente não tem compras

    recencia = (datetime.now() - df_vendas['data_venda'].max()).days
    frequencia = len(df_vendas)
    monetario = df_vendas['valor_total'].sum()

    df_rfm_cliente = pd.DataFrame({
        'recencia': [recencia],
        'frequencia': [frequencia],
        'monetario': [monetario]
    })
    
    return df_rfm_cliente

def classificar_cliente(cliente_id, kmeans_model, scaler_model):
    """
    Classifica um único cliente usando os modelos carregados.
    Retorna um dicionário com o nome e a cor da classificação.
    """
    if kmeans_model is None or scaler_model is None:
        return { 'nome': 'Indefinido', 'cor': '#6c757d' } # Cinza

    df_rfm = calcular_rfm_cliente_unico(cliente_id)

    if df_rfm is None:
        return { 'nome': 'Novo', 'cor': '#6c757d' } # Cinza

    dados_normalizados = scaler_model.transform(df_rfm)

    cluster_predito = kmeans_model.predict(dados_normalizados)[0]

    nome_classificacao = MAPA_CLUSTER_NOMES.get(cluster_predito, 'Indefinido')
    cor_classificacao = MAPA_CLUSTER_CORES.get(cluster_predito, '#6c757d')

    return {
        'nome': nome_classificacao,
        'cor': cor_classificacao
    }