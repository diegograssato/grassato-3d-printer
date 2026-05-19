Criei um sistema completo em Django e poetry para gestão do seu negócio de impressão 3D, contendo:

Controle de estoque de filamentos
Cadastro de produtos
Controle de vendas mensais
Controle de caixa
Dashboard geral
Balancete mensal automático

A sistema deve conter:
- decrementação automatica do estoque de filamentos
- decrmentação automatica do estoque de produtos
- cálculos de vendas
- consumo de metragem
- saldo de caixa
- resumo financeiro

Nova feature no sistema:
- Em Filamentos, Produtos e Fornecedores, ouvesse filtros e paginação(range de 10, 20, 50, 100,500,100)
- Em Filamentos, Produtos e Fornecedores, todos do grupo "Administradores" consigam filtrar por produtos itens ativos e inativos, com a possbilidade de ativar um item inativo
- Em Caixa e Vendas paginação(range de 10, 20, 50, 100,500,100)
- Em  Vendas consiga filtrar por tipo de venda, forma de pagaamento, também.
- Em  Caixa consiga filtrar por tipo(Entrada, Saida), categoria, fornecedor.
- Em Balancete paginação(range de 10, 20, 50, 100,500,100)
- Em Balancete filtro por range de data, por padrão deixar o range para incido de Janeiro do ano atual e fim Dezembro do ano atual.
- Em Auditoria paginação(range de 10, 20, 50, 100,500,100)