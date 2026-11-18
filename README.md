# Assistente de suporte — GPT-OSS-20B + Google Workspace

Protótipo Python de terminal para suporte interno. Consulta uma lista autorizada de Google Docs, recupera trechos por palavras-chave, solicita triagem ao GPT-OSS-20B via Groq e registra chamados no Google Sheets. O modelo não escreve diretamente nas APIs.

## Arquivos

## Interface web local

### Iniciar automaticamente com a tarefa do VS Code

O projeto já inclui uma tarefa pronta para iniciar o servidor em modo demo no VS Code:

- [tasks.json](.vscode/tasks.json)

No menu de tarefas do VS Code, execute `Iniciar atendimento web (demo)`.

### Iniciar manualmente

Com as dependências instaladas e o `.env` preenchido, execute:

```powershell
.\.venv\Scripts\python.exe web.py
```

Para demonstração com respostas simuladas e registros locais:

```powershell
.\.venv\Scripts\python.exe web.py --demo
```

Abra http://127.0.0.1:5000 no navegador. A interface HTML/CSS consulta a base, apresenta fontes e permite confirmar a resolução ou registrar um chamado na planilha.

O servidor é local, sem autenticação, e não deve ser exposto à rede. O estado do atendimento fica na memória e é perdido quando o servidor reinicia. A prevenção de envio duplicado vale para a sessão ativa, sem garantia distribuída. Interrompa com Ctrl+C.

### Estrutura

- `app.py`: atendimento interativo e demonstração sem serviços externos.
- `core.py`: recuperação, prompt estruturado, validação e chamados.
- `adapters.py`: leitura de Docs, abas e tabelas; inferência Groq; automação Sheets.
- `tests/test_support.py`: testes automatizados com substitutos das integrações.
- `PLANO_TESTES.md`: cenários, critérios e homologação real.
- `.github/workflows/tests.yml`: testes automáticos em Python 3.11, 3.12 e 3.13.
- `examples/base.json`: documentação fictícia para demonstração; substituir por procedimentos aprovados.

## Executar a demonstração

Python 3.11 ou superior. Na pasta do projeto:

```bash
python app.py --demo
```

A demonstração usa respostas determinísticas, sem carregar o modelo nem acessar o Google. Experimente “Como configurar wifi?” e confirme a resolução. Para testar a abertura, informe “Erro no servidor” ou responda que a orientação não resolveu. O chamado será salvo SOMENTE em `chamados_demo.jsonl` local. Não use dados sensíveis nessa demonstração.

## Configurar a integração real

1. Crie um projeto no Google Cloud e habilite Google Docs API e Google Sheets API.
2. Crie uma conta de serviço. Disponibilize a credencial JSON em local protegido, fora do repositório; não a envie por chat. A política da organização pode restringir chaves e compartilhamento.
3. Compartilhe apenas os documentos de suporte autorizados como leitor com o e-mail da conta de serviço. Compartilhe a planilha como editor. O protótipo lê com a identidade de serviço, não verifica permissões de cada colaborador: use somente base comum a todos os usuários do piloto.
4. Crie uma aba vazia `Chamados` na planilha. Copie os IDs dos documentos e da planilha a partir de suas URLs.
5. Crie uma nova chave no painel https://console.groq.com/keys e configure `GROQ_API_KEY` somente no ambiente local. Revogue qualquer chave anteriormente exposta. O modelo é fixado como `openai/gpt-oss-20b`; não é necessário instalar Ollama nem baixar pesos. A conta Groq precisa ter acesso ao modelo e quota disponível.

A pergunta e os trechos recuperados da documentação são enviados à Groq para inferência. Nome e setor não são enviados separadamente ao modelo, mas podem aparecer no texto informado. Use somente conteúdo autorizado pela empresa para processamento nesse provedor externo.

6. Instale as dependências em um ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

No PowerShell, ative com `.venv\Scripts\Activate.ps1`. Os limites de versões são faixas de compatibilidade, não um lockfile homologado.

7. Preencha o arquivo `.env` na pasta do `app.py` com a chave Groq, o caminho da credencial Google e os IDs. Use `.env.example` como referência. O aplicativo carrega `.env` automaticamente; variáveis já configuradas no terminal têm prioridade. O `.env` está excluído do Git. Como alternativa, configure as variáveis no mesmo terminal:

Linux:

```bash
export GOOGLE_APPLICATION_CREDENTIALS='/caminho/seguro/conta-servico.json'
export GOOGLE_DOC_IDS='ID_DOC_WIFI,ID_DOC_IMPRESSORAS'
export GOOGLE_SHEET_ID='ID_PLANILHA'
export GOOGLE_SHEET_TAB='Chamados'
read -rsp 'Nova chave Groq: ' GROQ_API_KEY
export GROQ_API_KEY
printf '\n'
```

PowerShell:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS='C:\seguro\conta-servico.json'
$env:GOOGLE_DOC_IDS='ID_DOC_WIFI,ID_DOC_IMPRESSORAS'
$env:GOOGLE_SHEET_ID='ID_PLANILHA'
$env:GOOGLE_SHEET_TAB='Chamados'
$groqSecret = Read-Host 'Nova chave Groq' -AsSecureString
$env:GROQ_API_KEY = [System.Net.NetworkCredential]::new('', $groqSecret).Password
Remove-Variable groqSecret
```

8. Inicialize e execute:

```bash
python app.py --init-sheet
python app.py
```

O inicializador não substitui uma aba preenchida com cabeçalho diferente. Execute-o antes do piloto, com um operador por vez.

## Fluxo e regras

O colaborador informa nome, setor e problema. Pode solicitar humano diretamente. A aplicação consulta Docs a cada atendimento, seleciona até quatro trechos e pede JSON ao modelo. Orientações precisam apontar para IDs recuperados. Ausência de trecho, erro de API/modelo ou saída inválida encaminham para chamado. Após orientação, o colaborador confirma a resolução; caso contrário, o cadastro ocorre automaticamente, após coleta do impacto.

Campos A:I: protocolo UUID, data/hora de São Paulo, colaborador, setor, descrição, orientações apresentadas, impacto, prioridade e status “Aberto”. Impacto individual → Normal; setor → Alta; empresa ou segurança → Crítica. Trata-se de uma regra inicial a ser aprovada pela equipe, baseada em informação declarada pelo usuário. O histórico registra o que foi apresentado, sem afirmar que cada passo foi executado.

A planilha recebe `RAW`, evitando interpretar entrada como fórmula. Só há confirmação quando `updatedRows=1`. Não há repetição automática de append: em timeout, o resultado pode ser ambíguo. A referência da tentativa permite procurar na planilha antes de cadastrar novamente. Não há garantia de exatamente uma gravação nem deduplicação distribuída.

## Limites e evolução

Protótipo para piloto supervisionado; não é uma implantação corporativa concluída. Sem autenticação de colaboradores, notificações, fila durável ou controle de SLA. Não há monitoramento ativo de incidentes: “Crítica” é um campo da planilha, portanto o usuário ainda deve acionar o canal emergencial da empresa.

A busca lexical e os trechos sobrepostos podem perder contexto ou recuperar conteúdos irrelevantes. Validação de IDs não comprova que a resposta é correta. Prompt contra injeção reduz risco, mas não oferece garantia; mantenha base revisada e teste o modelo real antes de liberar. O modelo não deve recomendar ações administrativas arriscadas. Para produção, adicionar autenticação, autorização por usuário, recuperação semântica, revisão de respostas, observabilidade sem dados sensíveis, retenção, fila de falhas e deduplicação transacional.

Apenas conteúdo textual do corpo é extraído, incluindo tabelas e abas filhas; imagens, anexos, cabeçalhos e notas não integram a base. Os documentos devem conter texto acessível. Não informe senhas ou tokens nas solicitações.

## Testes

```bash
python -m unittest discover -s tests -v
```

Os testes locais verificam regras e contratos simulados. Integração Google e inferência real exigem credenciais, recursos e homologação conforme o plano; não foram executadas neste ambiente.

## Referências oficiais

- https://developers.google.com/workspace/docs/api/how-tos/tabs
- https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append
- https://developers.google.com/workspace/sheets/api/guides/values
- https://console.groq.com/docs/models
- https://console.groq.com/docs/api-reference

## Alteração para Groq

O adaptador usa a API HTTPS de chat completions com JSON Object Mode. A validação de ação e fontes permanece em `core.py`. HTTP 401/403 (credenciais/acesso), 429 (limite), 5xx, timeout e respostas truncadas ou inválidas provocam encaminhamento para chamado, sem exibir detalhes da credencial. Não há repetição automática de inferência.

`--init-sheet` continua funcionando sem chave Groq. O modo `--demo` também continua independente de credenciais. O arquivo `.env.example` não é carregado automaticamente. Testes mockados verificam o contrato HTTP; a inferência real depende de uma chave nova configurada localmente e não foi executada nesta entrega.

## Licença

Este projeto é distribuído sob a **GNU General Public License, versão 3 (GPL-3.0-only)**. Consulte o texto completo em [LICENSE](LICENSE).

Este programa é software livre: você pode redistribuí-lo e/ou modificá-lo sob os termos da GNU GPL versão 3, publicada pela Free Software Foundation. É distribuído sem qualquer garantia, conforme os termos da licença.
