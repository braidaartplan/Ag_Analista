# 🧠 Agente de Monitoramento de Campanhas com AGNO

Este repositório contém a implementação de um **agente inteligente de análise de campanhas de marketing**, construído com o framework [AGNO](https://docs.agno.com/). O agente se conecta a um banco de dados relacional (MySQL), consulta dados de campanhas, e gera análises semanais com **destaques positivos e negativos** dos criativos, considerando o objetivo da campanha e principais KPIs.

---

## 📌 Funcionalidades

- 🔍 **Consulta inteligente ao banco de dados** usando linguagem natural.
- 📊 **Análise semanal de performance de criativos** com base nos objetivos das campanhas (ex: alcance, visualização, conversão).
- 🧠 **Resumos analíticos**, destaques positivos/negativos e **recomendações acionáveis**.
- 💬 Interface via AGNO Playground para interação com o agente.
- 🗂️ Armazenamento do histórico de conversas com `SqliteStorage`.

---

## 🛠️ Tecnologias utilizadas

- [AGNO](https://github.com/agno-agi/agno): Framework para construção de agentes multimodais.
- [OpenAI Chat Model](https://platform.openai.com/docs): Utilização do modelo `gpt-4.1-mini`.
- `SQLTools`: Conector nativo da AGNO para executar queries SQL com segurança.
- `Playground`: Interface local de interação com agentes.
- `.env`: Gerenciamento seguro de credenciais via `python-dotenv`.

---

## 🗃️ Estrutura esperada da tabela `Metricas`

O agente utiliza uma tabela chamada `Metricas` com os seguintes campos:

- `Cliente`  
- `Campanha`  
- `Veiculo`  
- `Data`  
- `Impressoes`  
- `Investimento`  
- `Visualizacoes_ate_100`  
- `Video_Play`  
- `Formato`  
- `Criativo`  
- `Objetivo`  
- `Editoria`  
- `Link_do_Anuncio`

> O agente interpreta os dados de acordo com o **objetivo da campanha** para selecionar os KPIs mais relevantes (por exemplo: Impressões e CPM para "Alcance"; Visualizações 100% e CPV para "Visualização").

---

## 🚀 Como rodar o projeto

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/agent-agno-monitoramento.git
cd agent-agno-monitoramento
```

### 2. Instale as dependências

Recomenda-se o uso de ambiente virtual:

```bash
python -m venv venv
source venv/bin/activate  # ou .\venv\Scripts\activate no Windows
pip install -r requirements.txt
```

> Caso o `requirements.txt` não esteja criado ainda, você pode gerar com:  
> `pip freeze > requirements.txt`

### 3. Configure o `.env`

Crie um arquivo `.env` com as seguintes variáveis:

```env
DB_USUARIO=seu_usuario
DB_SENHA=sua_senha
DB_HOST=localhost
DB_NOME=nome_do_banco
```

### 4. Execute a aplicação

```bash
python seu_script.py
```

> O `Playground` será iniciado localmente e permitirá conversar com o agente via navegador ou terminal.

---

## ✅ Exemplos de perguntas para o agente

- *Quais foram os melhores criativos da semana para a campanha do SEBRAE RJ?*  
- *Qual criativo teve pior desempenho na campanha de Conversão do BNDES?*  
- *Recomende ajustes para melhorar os KPIs da campanha da Eletrobras.*

---

## 📂 To-do / Próximos passos

- [ ] Criar um segundo agente para geração de relatórios automatizados (PDF / e-mail)
- [ ] Integração com agendamento (ex: análise semanal automática)
- [ ] Testes unitários nas funções de suporte (caso haja lógica externa)
- [ ] Melhorar interface do Playground para visualização de métricas

---

## 📄 Licença

Este projeto está sob a licença MIT. Sinta-se à vontade para usá-lo, modificá-lo e distribuí-lo conforme necessário.