# Arquitetura do EiVORAK v3

## Visão
O cérebro é um só. Cada plataforma é apenas um adaptador que traduz mensagens de entrada e saída.

```
Messenger / Telegram / Instagram
            |
      Adaptadores (um por canal)
            |  mensagem comum
        Gateway
  (valida, deduplica, responde 200 já)
            |
         Cérebro
  (identifica utilizador/admin, escolhe modo,
   monta contexto, chama modelo e ferramentas)
        |            |
    Memória      Ferramentas
 (SQLite/FTS5)   (wikipedia, web, documentos,
                  conhecimento, página Facebook)
            |
      Provedores de modelo
   (Groq principal -> Gemini fallback)
```

## Estrutura de pastas
```
eivorak/
  __main__.py          # arranque
  config.py            # lê variáveis de ambiente, falha se faltar algo
  models.py            # dataclasses: IncomingMessage, OutgoingMessage, User
  gateway.py           # fila, deduplicação, rate limit
  brain.py             # orquestra a resposta
  prompts.py           # prompt do sistema (sem dados pessoais)
  humanize.py          # divide texto em várias mensagens, limites por canal
  admin.py             # emparelhamento e comandos de admin
  channels/
    base.py            # interface Channel
    messenger.py
    telegram.py
  llm/
    base.py            # interface Provider
    groq_provider.py
    gemini_provider.py # fallback
  memory/
    db.py              # SQLite (WAL), migrações simples
    history.py         # histórico e resumos
    knowledge.py       # conhecimento com FTS5
  tools/
    wikipedia.py
    pagina_facebook.py # fase 5: rascunho, aprovação, publicação
tests/
docs/
.env.example
requirements.txt
README.md
```

## Contratos principais
- `IncomingMessage`: `channel`, `user_key` (`canal:id`), `text`, `attachments`, `message_id`, `timestamp`.
- `OutgoingMessage`: `user_key`, `parts` (lista de textos já divididos), `buttons` opcionais.
- `Channel`: `parse_webhook(request) -> list[IncomingMessage]`, `send(OutgoingMessage)`,
  `max_len`, `supports_buttons`, `send_typing(user_key)`.
- `Provider`: `complete(messages, max_tokens) -> Completion(text, finish_reason)`.
  O cérebro tenta o principal e passa ao fallback se falhar.

## Decisões
- **Chave de utilizador composta** `canal:id`, para não haver colisões entre plataformas.
- **Admin por emparelhamento:** `/admin <código>` associa o `user_key` ao admin. O código vem
  de `ADMIN_PAIRING_SECRET`, tem limite de tentativas e nunca é guardado no histórico.
  Todas as ações de admin ficam num registo de auditoria.
- **Respostas longas:** `humanize.py` divide por parágrafos respeitando `max_len` do canal;
  se o modelo parar por limite (`finish_reason == "length"`), a resposta é continuada ou
  termina em frase completa. Envia "a escrever…" entre partes.
- **Debug:** modo ativável pelo admin que regista no log o que realmente correu (modelo usado,
  ferramentas chamadas, tempos). Nunca se pergunta ao modelo o que ele "fez por dentro".
- **Aprovação humana:** nada é publicado na Página sem aprovação do admin por botões.
- **Privacidade:** comando `/meusdados` (ver) e `/apagar` (apagar tudo).

## Ordem de construção
1. Esqueleto, config, modelos e memória.
2. Messenger com assinatura, deduplicação e fila.
3. Humanização e divisão de mensagens.
4. Admin por emparelhamento e comandos.
5. Telegram.
6. Memória em camadas, feedback 👍/👎, debug.
7. Primeiro diferencial: estudo de informática.
8. Gestão da Página de Facebook (rascunhos, aprovação, agendamento, relatório semanal).
