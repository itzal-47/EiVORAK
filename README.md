# EiVORAK

Assistente conversacional em português de Angola. Os adaptadores de canal são independentes do cérebro e da memória SQLite.

## Instalação e execução

```bash
pip install -r requirements.txt
cp .env.example .env
# Preenche as variáveis obrigatórias em .env
python -m eivorak
```

O arranque exige `VERIFY_TOKEN`, `PAGE_ACCESS_TOKEN`, `META_APP_SECRET`, `GROQ_API_KEY` e `ADMIN_PAIRING_SECRET`. `CREATOR_INFO` é opcional e pode ficar vazio. O caminho da base pode ser configurado com `DATABASE_PATH`; a porta usa `PORT` (5000 por omissão).

## Persistência com Litestream

O arranque usa modo local quando as quatro variáveis `LITESTREAM_*` estão vazias ou ausentes. Nesse modo não é preciso instalar Litestream. Se começares a configurar a réplica, preenche todas estas variáveis:

- `LITESTREAM_ENDPOINT`: URL HTTPS do endpoint S3 compatível.
- `LITESTREAM_BUCKET`: bucket de destino.
- `LITESTREAM_ACCESS_KEY_ID` e `LITESTREAM_SECRET_ACCESS_KEY`: credenciais do bucket.

O [litestream.yml](litestream.yml) expande as variáveis no arranque e não contém credenciais. Com réplica configurada, `scripts/start.py` tenta restaurar a base quando não existe localmente; a ausência de uma réplica inicial é aceite. Depois o Litestream executa e supervisiona o bot com `replicate -exec`. Erros reais de autenticação ou de rede interrompem o arranque para não criar silenciosamente uma base vazia.

### Render

1. Cria um **Web Service** no Render e escolhe o runtime **Docker**. O `Dockerfile` na raiz instala Litestream e as dependências Python.
2. Usa `python scripts/start.py` como Start Command (ou deixa o `CMD` do Dockerfile).
3. Adiciona as variáveis do bot no painel do Render:
   - Obrigatórias: `VERIFY_TOKEN`, `PAGE_ACCESS_TOKEN`, `META_APP_SECRET`, `GROQ_API_KEY`, `ADMIN_PAIRING_SECRET`.
   - Opcionais: `CREATOR_INFO`, `PORT`, `DATABASE_PATH` (o Dockerfile define `/data/eivorak_brain.db` por omissão).
4. Para replicação, adiciona também `LITESTREAM_ENDPOINT`, `LITESTREAM_BUCKET`, `LITESTREAM_ACCESS_KEY_ID` e `LITESTREAM_SECRET_ACCESS_KEY`. O endpoint deve incluir o esquema, por exemplo `https://...`; a configuração usa a região S3 `us-east-1`.

Não coloques credenciais no Dockerfile nem no `litestream.yml`.

Depois de emparelhar o admin pela Página, troca `ADMIN_PAIRING_SECRET` no Render. O código `/admin <código>` fica visível no histórico desse chat.

Sem as quatro variáveis de Litestream, o container corre o bot em modo local. Nesse modo, uma plataforma com disco efémero pode perder a base nos reinícios; configura uma réplica para restaurar os dados.

## Testes

```bash
pytest -q
```

Os testes usam fornecedores simulados e não contactam serviços externos.
