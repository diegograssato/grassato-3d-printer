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
- Hoje quando é modificado o valor ou a quantidade do produto pelo sistema, já sensibiliza a integração de destino(MercadoLivre):
    - Gostaria que essa ação imediata, fosse enviada para fila do celery, e processada(enviar as atualizações para integração de destino(MercadoLivre))
    - A mesma coisa acontecer quando desativar um produto no sistema, fosse enviada para fila do celery, e processada(enviar as atualizações para integração de destino(MercadoLivre))
Isso vai tornar o sistemas mais escalavél e as ações ficam mais rapidas, e se ouver algum problema emitir um evento de auditoria, para podermos analisar o ocorrido.    