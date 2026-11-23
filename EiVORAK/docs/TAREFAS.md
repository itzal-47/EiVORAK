# Tarefas para o Codex

Dá **uma tarefa de cada vez**, numa branch própria. Depois de cada uma: corre `pytest -q`,
testa localmente e leva o diff para revisão antes do merge.

## Passo 0 — antes do Codex (manual)
- [ ] Criar a branch `refactor`.
- [ ] Trocar o `PAGE_ACCESS_TOKEN`, a chave do Groq e o `VERIFY_TOKEN` (já estiveram no código ou expostos).
- [ ] Garantir que `.env`, `*.db`, `fotos_perfil/` e `relatorio_utilizadores.txt` estão no `.gitignore`.
- [ ] Mover o email, o telefone, as redes sociais e a morada para fora do repositório
      (variável `CREATOR_INFO` no `.env`).
- [ ] Copiar `AGENTS.md` para a raiz e `ARQUITETURA.md` para `docs/`.

---

## Tarefa 1 — Esqueleto modular
**Objetivo:** transformar `eivorak.py` na estrutura de `docs/ARQUITETURA.md`, sem mudar o
comportamento visível do bot no Messenger.

**Pode alterar:** criar a pasta `eivorak/`, `tests/`, `requirements.txt`, `.env.example`, `README.md`.
Manter `eivorak.py` antigo até a tarefa terminar, depois removê-lo.

**Requisitos:**
- `config.py` lê variáveis de ambiente (`VERIFY_TOKEN`, `PAGE_ACCESS_TOKEN`, `META_APP_SECRET`,
  `GROQ_API_KEY`, `ADMIN_PAIRING_SECRET`, `CREATOR_INFO`) e falha no arranque se faltar alguma
  obrigatória. Sem valores por defeito para segredos.
- `models.py` com `IncomingMessage` e `OutgoingMessage`.
- `memory/db.py`: SQLite em modo WAL, `with` em todas as ligações, `init_db()` chamado **uma vez** no arranque.
- Chave de utilizador `canal:id`. Migração das tabelas existentes sem perder dados.
- Remover o código morto (rota `/` duplicada, `wiki_lookup` pode passar para `tools/wikipedia.py`).
- Corrigir o bug do histórico: a mensagem do utilizador não pode aparecer duas vezes no prompt.
- Deixar de guardar foto de perfil, fuso horário e idioma. Remover a geração de `relatorio_utilizadores.txt`.

**Pronto quando:** `pytest -q` passa, `python -m eivorak` arranca com `.env` completo e falha com
mensagem clara sem ele.

---

## Tarefa 2 — Messenger seguro e rápido
**Objetivo:** adaptador do Messenger em `channels/messenger.py` + `gateway.py`.

**Requisitos:**
- Validar `X-Hub-Signature-256` com `META_APP_SECRET`. Pedidos inválidos recebem 403.
- Responder 200 ao webhook imediatamente e processar a mensagem numa fila/thread de trabalho.
- Deduplicar por `mid` (a Meta reenvia se demorar).
- Limite simples de mensagens por utilizador (por exemplo, 20 por minuto), com resposta amigável ao exceder.
- Tratar anexos sem texto com uma mensagem clara.

**Testes:** assinatura válida/inválida, `mid` repetido processado uma só vez, limite excedido.

---

## Tarefa 3 — Humanização e respostas completas
**Objetivo:** acabar com respostas cortadas e deixar o bot mais natural.

**Requisitos:**
- `humanize.py`: dividir o texto por parágrafos/frases em partes que respeitam o `max_len` do canal
  (Messenger 2000), nunca cortando a meio de uma frase.
- Aumentar `max_tokens` e detetar `finish_reason == "length"`: pedir continuação ou terminar em frase completa.
- Enviar `typing_on` antes de cada parte, com pequena pausa proporcional ao tamanho.
- `prompts.py`: prompt do sistema em português de Angola, frases curtas, sem markdown pesado,
  sem emojis em excesso, espelha o jeito de escrever da pessoa, faz perguntas em vez de despejar texto.
  Inclui uma **ficha técnica verdadeira** do bot (modelo Llama via Groq, ferramentas realmente disponíveis).
- Corrigir a frase mista em inglês que existe hoje no prompt ("When não sabes...").

**Testes:** texto longo é dividido sem cortar frases, parte única curta não é dividida,
`finish_reason == "length"` aciona o tratamento.

---

## Próximas (só depois de 1 a 3 aprovadas)
4. Admin por emparelhamento e comandos em código, com registo de auditoria.
5. Adaptador do Telegram.
6. Memória em camadas, 👍/👎 e modo debug real.
7. Modo estudo de informática.
8. Gestão da Página de Facebook com aprovação por botões.

## Modelo de prompt para o Codex
> Lê `AGENTS.md` e `docs/ARQUITETURA.md`. Implementa a **Tarefa N** de `docs/TAREFAS.md`.
> Não alteres nada fora do âmbito dela. Escreve os testes pedidos, corre `pytest -q`
> e no fim lista os ficheiros alterados e o que ficou por fazer.
