# AGENTS.md — Regras para o EiVORAK

Lê este ficheiro e `docs/ARQUITETURA.md` antes de qualquer tarefa.

## O que é o projeto
EiVORAK é um assistente de IA que conversa em português de Angola através de vários canais
(Messenger primeiro, depois Telegram e Instagram). O cérebro é independente dos canais.
Foco: ser útil de verdade para angolanos (informática, estudo, documentos, guia local),
e ajudar a gerir uma Página de Facebook de tecnologia/informática/geek/anime.

## Regras obrigatórias
1. **Segredos:** nunca escrever tokens, chaves, emails, telefones ou moradas no código ou em
   prompts versionados. Tudo vem de variáveis de ambiente (`.env`, que está no `.gitignore`).
   Se uma variável obrigatória faltar, a app **falha no arranque** com mensagem clara.
2. **Uma tarefa por vez.** Só mexer nos ficheiros que a tarefa permite. Não refatorar fora do âmbito.
3. **Testes:** toda a lógica nova leva testes (`pytest`). Os modelos de IA e as APIs externas
   são **simulados (mock)** nos testes. Nunca chamar Groq, Meta ou Telegram a sério em testes.
4. **Segurança dos webhooks:** validar sempre a assinatura (`X-Hub-Signature-256` na Meta,
   secret token no Telegram). Responder 200 depressa e processar fora do pedido.
5. **Admin:** comandos de admin são código determinístico. O modelo de IA nunca executa ações
   administrativas nem acede a ficheiros ou ao sistema.
6. **Privacidade:** guardar só o necessário (id do canal, nome, mensagens). Não guardar foto,
   fuso horário nem idioma. Tem de existir forma de o utilizador ver e apagar os seus dados
   (incluindo ficheiros).
7. **Honestidade do bot:** o prompt do sistema descreve com verdade o que o bot é e que
   ferramentas tem. O bot nunca inventa factos sobre si próprio nem informação oficial.
8. **Estilo de resposta do bot:** português de Angola, natural, frases curtas, pouca formatação,
   sem despejar texto. Respostas longas dividem-se em várias mensagens por parágrafo.
9. **Código:** Python 3.11+, tipos nas funções públicas, `logging` (não `print`), ligações
   SQLite com `with` e modo WAL, sem variáveis globais mutáveis.
10. Ao terminar, listar: ficheiros alterados, como correr os testes e o que ficou por fazer.

## Comandos
- Instalar: `pip install -r requirements.txt`
- Testes: `pytest -q`
- Correr localmente: `python -m eivorak`
