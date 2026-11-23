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

## Testes

```bash
pytest -q
```

Os testes usam fornecedores simulados e não contactam serviços externos.
