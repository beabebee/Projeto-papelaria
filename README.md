# Projeto Papelaria - Implementações novas de Automação com IA

Este documento detalha as novas funcionalidades de Inteligência Artificial implementadas no sistema. Ele pode ser deletado posteriormente

A versão anterior do projeto consistia em um sistema CRUD (Create, Read, Update, Delete) para produtos, clientes e vendas, com autenticação de usuários. A atualização adicionou duas camadas de automação: um chatbot assistente e um sistema de recomendação de produtos.

Crie e ative um ambiente virtual:

```bash
python3 -m venv venv
source venv/bin/activate
```

O arquivo de requirements.txt foi atualizado com novas bibliotecas, sendo elas:

```ts
SQLAlchemy==2.0.21
pandas==2.1.0
scikit-learn==1.3.2
numpy==1.26.4
python-Levenshtein==0.25.1

gunicorn
```

Instale as dependências:

```Bash
pip install -r requirements.txt
```

Execute a aplicação Flask:

```Bash
flask run
```

Acesse http://127.0.0.1:5000 no seu navegador.

---

Alterei o arquivo .gitignore para adicionar a linha /**pycache** nele, para garantir que qualquer cache do python não suba para o github.

## Assistente Virtual (Chatbot)

Foi implementado um chatbot para servir como um assistente para o vendedor, ajudando-o a navegar e a tirar dúvidas sobre as funcionalidades do sistema. A abordagem inicial de usar a biblioteca ChatterBot foi descartada devido a severos conflitos de dependência em ambientes modernos. Em seu lugar, foi criada uma solução customizada, mais leve e robusta.

### Implementação

- chatbot_config.py: "cérebro" do chatbot. Ele contém o dicionário conversa_assistente com perguntas e respostas conhecidos. Inclui a função get_simple_bot_response, que recebe a mensagem do usuário, a normaliza (converte para minúsculas) e busca a resposta mais relevante usando técnicas de similaridade de texto (NLP com scikit-learn).
- app.py (modificado): importa as novas funções e o dicionario do arquivo anterior; criado a rota /faq que usa o dicionario criado para treinar o chatbot para exibir as perguntas frequentes em uma página; criado a rota /chat que recebe apenas chamadas do tipo POST, e recebe a mensagem do usuario e a envia para a função get_simple_bot_response, retornando a resposta em json.
- \_chatbox.html: é o arquivo referente a caixa de dialogo com o chatbot, foi estilizada com um mecanismo de minimizar a caixinha, e contem scripts que fazem isso; além de uma função que lida com o input de mensagem e é responsavel por fazer a requisição para a rota /chat, obter a resposta do modelo e exibir ele na tela.
- faq page: uma simples exibição do dicionario de perguntas e respostas na tela.
- base.html (modificado): foi incluido o botão que leva a FAQ page e inclui o arquivo \_chatbox.html na página inteira.
- styles.css (modificado): foi incluido estilos (devidamente identificado com comentários) referentes ao chatbox.

## Sistema de Recomendações

Foi implementado um sistema de recomendação com duas frentes para auxiliar o vendedor a impulsionar as vendas, cumprindo os requisitos obrigatórios e o extra do projeto.

### Implementação

- recommendation_engine.py: Arquivo complexo que centraliza toda a lógica de recomendação; possui 4 funções, a get_purchase_matrix que transforma os dados de venda em uma matriz, a recommend_for_client que recomenda 'n' produtos para um cliente específico com base no cliente mais similar, a recommend_for_client_knn que cumpre um requisito extra do projeto, ela faz o mesmo que a função anterior, mas ela pesquisa com base nos 'k' vizinhos mais próximos, e a ultima get_best_sellers que pega os 'n' produtos mais vendidos em todo o site.
- app.py (modificado): @nova rota /recomendar/cliente/<int:id> que recebe o ID de um cliente, chama a função recommend_for_client_knn e retorna uma lista de produtos recomendados em JSON. Se nenhuma recomendação personalizada for encontrada, ela retorna uma lista dos produtos mais vendidos como um "plano B"; modifica a rota / para exibir os 6 produtos mais vendidos na tela inicial com a função get_best_sellers.
- templates/clientes/listar.html (Modificado): Um botão "Recomendações" foi adicionado a cada linha da tabela de clientes; O código de um modal (janela pop-up) foi adicionado usando HTML/CSS nativo; O script da página agora controla a exibição do modal e usa fetch para chamar a rota /recomendar/cliente/<id>, exibindo dinamicamente as sugestões de produtos recebidas.
- templates/index.html (modificado): Uma seção "Produtos Mais Vendidos" foi adicionada à página inicial, exibindo os produtos retornados pela rota /.
- styles.css (modificado): foi incluido estilos (devidamente identificado com comentarios) referentes ao sistema de recomendação.

Foi feito deploy na plataforma render:
https://projeto-papelaria-czug.onrender.com

Na versão de deploy o sistema de email não funciona, pois a biblioteca necessita utilizar portas que o render bloqueia na versão gratuita.