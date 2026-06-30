# 🖥️ Intranet - Central de Suporte & Mapeamento de Ativos de TI

Este projeto é um ecossistema completo de Intranet corporativa desenvolvido para centralizar o gerenciamento de infraestrutura de redes, controle de inventário técnico em lote, central de procedimentos e comunicação interna segura.

## 🚀 Principais Funcionalidades

* **Mapeamento de Ativos:** Cadastro avançado e gerenciamento de equipamentos de rede (Access Points) com filtros inteligentes de busca por nome, endereço MAC, número de série ou localização física.
* **Inserção em Lote Dinâmica:** Interface otimizada que permite ao administrador cadastrar múltiplos ativos de infraestrutura de uma única vez em uma interface de grade dinâmica.
* **Mural de Avisos com Sistema de Check-in:** Alertas pulsantes globais em todas as páginas do sistema para notificações pendentes. Possui painel de logs em tempo real para administradores rastrearem quais colaboradores confirmaram a leitura.
* **Central de Tutoriais Avançada:** Upload e gerenciamento de manuais operacionais internos e externos com layouts responsivos em estilo *Premium Dark*.
* **Autenticação & Controle de Nível de Acesso (RBAC):** Proteção de rotas do sistema diferenciando as ações permitidas para Administradores e Estagiários.

## 🛠️ Tecnologias Utilizadas

* **Backend:** Python / Flask
* **Banco de Dados:** SQLite3 (Persistência relacional)
* **Frontend:** HTML5 estruturado, CSS3 personalizado, JavaScript Assíncrono (Fetch API / Manipulação do DOM)
* **Template Engine:** Jinja2

## 📦 Estrutura de Banco de Dados Implementada

O sistema utiliza relacionamentos foreign-key para garantir integridade e auditoria:
* `usuarios`: Armazena credenciais, roles (`adm`/`estagiario`) e status de ativação.
* `avisos`: Gerencia os comunicados e níveis de criticidade.
* `logs_leitura`: Registra timestamps e auditoria de leitura de comunicados por usuário.
* `Blanket_APs`: Tabela principal de gerenciamento de hardware de rede.
