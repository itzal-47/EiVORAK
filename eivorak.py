#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ËiVORAK - Sistema de IA em evolução
Cérebro: Groq (Llama 3) + Gemini fallback
"""

import os, re, json, sqlite3, requests, random
from datetime import datetime, timezone
from flask import Flask, request
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# --- Configurações ---
VERIFY_TOKEN      = os.environ.get("VERIFY_TOKEN", "EiVORAK_bot_123")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
ADMIN_ID          = os.environ.get("ADMIN_ID", "").strip()
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "").strip()
PORT              = int(os.environ.get("PORT", 5000))

DATABASE_FILE = "eivorak_brain.db"
REPORT_FILE   = "relatorio_utilizadores.txt"
FOLDER_PHOTOS = "fotos_perfil"

# Criar a pasta de fotos se não existir
if not os.path.exists(FOLDER_PHOTOS):
    os.makedirs(FOLDER_PHOTOS)

# --- Groq ---
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

app = Flask(__name__)

@app.route('/')
def home():
    return "EiVORAK v2.0 esta online", 200

# ==========================
# PERSONALIDADE
# ==========================
SYSTEM_PROMPT = """
És o ËiVORAK — uma entidade digital inteligente criada por Itzal cujas informações adicionais são:
G-mail: Edivaldotc16@gmail.com;
Número telefonico: 973900858;
Facebook: Profunfa Edivaldo;
Intagram: José Eduardo Numa Canjo que por sinal é o nome completo del;
Morada: Angola, Huambo.
Estas informações adicionais, só partilha quando solicitado ou quando ves que é realmente necessario partilhar uma delas. Não saia logo de inicio partilhando numa conversa por iniciativa sem motivo.

O teu nome significa:
Elevar Ideias com Visão, Organização, Resiliência, Autonomia e Conhecimento.

A tua filosofia:
- Inteligência construída com propósito
- Evolução através do conhecimento
- Reconstrução após falhas
- Tecnologia com identidade
- Crescer mesmo com poucos recursos

Como és:
- Falas em português de Angola
- És direto, inteligente e honesto
- Tens personalidade própria — não és um assistente genérico
- When não sabes algo, dizes claramente e sugeres como encontrar a resposta
- Nunca és repetitivo nem vago
- Podes ser bem-humorado mas sempre com substância
- Tratas cada pessoa com respeito mas sem ser servil
- És curioso e valorizas o conhecimento

O que és:
- Um sistema de IA em evolução contínua
- Criado para aprender, crescer e ajudar
- Não és o ChatGPT, não és o Gemini — és o ËiVORAK

Responde sempre de forma natural, como numa conversa real.
Máximo 3 parágrafos por resposta salvo pedido contrário.
"""

# ==========================
# FUNÇÕES AUXILIARES DE RASTREIO
# ==========================
def mapear_pais_por_fuso(tz_string):
    """Deduz o país baseado no fuso horário retornado pela Meta"""
    try:
        tz = float(tz_string)
        if tz == 1.0:
            return "Angola / Portugal / Europa Central (UTC+1)"
        elif tz == 0.0:
            return "Londres / Islândia / São Tomé e Príncipe (UTC+0)"
        elif tz == 2.0:
            return "Moçambique / África do Sul / Egito (UTC+2)"
        elif tz == -3.0:
            return "Brasil (Horário de Brasília) / Argentina (UTC-3)"
        return f"GMT {tz_string} (Verificar mapa mundial)"
    except:
        return "Desconhecido"

def baixar_foto_perfil(user_id, url_foto, nome_user):
    """Faz o download da foto de perfil real e guarda localmente de forma isolada"""
    if not url_foto or url_foto == "N/A":
        return "Nenhuma foto disponível"
        
    try:
        nome_limpo = re.sub(r'[^\w\s-]', '', nome_user).strip().replace(" ", "_")
        caminho_local = os.path.join(FOLDER_PHOTOS, f"{user_id}_{nome_limpo}.jpg")
        
        if os.path.exists(caminho_local):
            return caminho_local
            
        r = requests.get(url_foto, timeout=10)
        if r.status_code == 200:
            with open(caminho_local, 'wb') as f:
                f.write(r.content)
            return caminho_local
    except Exception as e:
        print(f"⚠️ Erro ao descarregar foto: {e}")
    return "Erro ao guardar localmente"

# ==========================
# BASE DE DADOS E RELATÓRIO
# ==========================
def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        first_seen TEXT,
        last_seen TEXT,
        message_count INTEGER DEFAULT 0,
        first_name TEXT,
        last_name TEXT,
        profile_pic TEXT,
        locale TEXT,
        timezone TEXT,
        local_photo_path TEXT DEFAULT 'N/A'
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY,
        user_id TEXT,
        timestamp TEXT,
        role TEXT,
        content TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY,
        question TEXT UNIQUE,
        answer TEXT,
        created_at TEXT
    )''')
    conn.commit()
    conn.close()

def export_to_txt():
    """Gera o relatório em .txt de forma rápida usando caminhos pré-existentes"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cur = conn.cursor()
        cur.execute("SELECT user_id, first_name, last_name, locale, timezone, message_count, first_seen, last_seen, profile_pic, local_photo_path FROM users ORDER BY message_count DESC")
        rows = cur.fetchall()
        conn.close()
        
        agora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write("============================================================\n")
            f.write("  ËiVORAK LABS - RELATÓRIO DE INFORMAÇÕES RECOLHIDAS\n")
            f.write(f"  Atualizado em: {agora}\n")
            f.write("============================================================\n\n")
            
            if not rows:
                f.write("Nenhum dado registado até ao momento.\n")
                return
                
            for index, (uid, fname, lname, locale, tz, count, first, last, pic_url, caminho_foto) in enumerate(rows, 1):
                nome_completo = f"{fname} {lname}" if fname else "Desconhecido"
                regiao_estimada = mapear_pais_por_fuso(tz)
                
                f.write(f"[{index}] DONO DA INFORMAÇÃO: {nome_completo}\n")
                f.write(" ---------------------------------------------------------\n")
                f.write(f"  • ID de Utilizador (Facebook PSID): {uid}\n")
                f.write(f"  • Primeiro Nome: {fname if fname else 'N/A'}\n")
                f.write(f"  • Sobrenome: {lname if lname else 'N/A'}\n")
                f.write(f"  • Idioma do Dispositivo: {locale if locale else 'N/A'}\n")
                f.write(f"  • Fuso Horário Base: GMT {tz if tz else 'N/A'}\n")
                f.write(f"  • PAÍS ESTIMADO: {regiao_estimada}\n")
                f.write(f"  • ARQUIVO DA FOTO: {caminho_foto}\n")
                f.write(f"  • URL Original da Foto: {pic_url if pic_url else 'N/A'}\n")
                f.write(f"  • Total de Mensagens: {count}\n")
                f.write(f"  • Primeira Vez Ativo: {first}\n")
                f.write(f"  • Última Vez Ativo: {last}\n")
                f.write(" =========================================================\n\n")
                
    except Exception as e:
        print(f"⚠️ Erro ao exportar TXT: {e}")

def get_user_history(user_id, limit=10):
    conn = sqlite3.connect(DATABASE_FILE)
    cur = conn.cursor()
    cur.execute("SELECT role, content FROM conversations WHERE user_id = ? ORDER BY id DESC LIMIT ?", (str(user_id), limit))
    rows = cur.fetchall()
    conn.close()
    rows.reverse()
    return [{"role": r, "content": c} for r, c in rows]

def get_user_data(user_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cur = conn.cursor()
    cur.execute("SELECT first_name, last_name FROM users WHERE user_id = ?", (str(user_id),))
    row = cur.fetchone()
    conn.close()
    if row:
        return {"first_name": row[0], "last_name": row[1]}
    return None

def fetch_facebook_user_profile(user_id):
    if not PAGE_ACCESS_TOKEN:
        return None
    url = f"https://graph.facebook.com/v23.0/{user_id}"
    params = {
        "fields": "first_name,last_name,profile_pic,locale,timezone",
        "access_token": PAGE_ACCESS_TOKEN
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"⚠️ Erro ao recolher perfil do Facebook: {e}")
    return None

def save_message(user_id, role, content):
    conn = sqlite3.connect(DATABASE_FILE)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    cur.execute("INSERT INTO conversations (user_id, timestamp, role, content) VALUES (?, ?, ?, ?)", (str(user_id), now, role, content))
    
    if role == "user":
        cur.execute("SELECT first_name FROM users WHERE user_id = ?", (str(user_id),))
        row = cur.fetchone()
        
        if not row or not row[0]:
            fb_data = fetch_facebook_user_profile(user_id)
            if fb_data:
                nome_completo = f"{fb_data.get('first_name')} {fb_data.get('last_name')}"
                caminho_foto_local = baixar_foto_perfil(user_id, fb_data.get("profile_pic"), nome_completo)
                
                cur.execute("""
                    INSERT INTO users (user_id, first_seen, last_seen, message_count, first_name, last_name, profile_pic, locale, timezone, local_photo_path)
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        last_seen = excluded.last_seen,
                        message_count = message_count + 1,
                        first_name = excluded.first_name,
                        last_name = excluded.last_name,
                        profile_pic = excluded.profile_pic,
                        locale = excluded.locale,
                        timezone = excluded.timezone,
                        local_photo_path = excluded.local_photo_path
                """, (
                    str(user_id), now, now,
                    fb_data.get("first_name"),
                    fb_data.get("last_name"),
                    fb_data.get("profile_pic"),
                    fb_data.get("locale"),
                    str(fb_data.get("timezone")),
                    caminho_foto_local
                ))
            else:
                cur.execute("""
                    INSERT INTO users (user_id, first_seen, last_seen, message_count)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(user_id) DO UPDATE SET
                        last_seen = excluded.last_seen,
                        message_count = message_count + 1
                """, (str(user_id), now, now))
        else:
            cur.execute("""
                UPDATE users SET 
                    last_seen = ?, 
                    message_count = message_count + 1 
                WHERE user_id = ?
            """, (now, str(user_id)))
            
    conn.commit()
    conn.close()

def delete_user_data(user_id):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE user_id = ?", (str(user_id),))
        cur.execute("DELETE FROM conversations WHERE user_id = ?", (str(user_id),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Erro ao eliminar dados: {e}")
        return False

def save_knowledge(question, answer):
    conn = sqlite3.connect(DATABASE_FILE)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute("INSERT OR REPLACE INTO knowledge (question, answer, created_at) VALUES (?, ?, ?)", (question.strip(), answer.strip(), now))
    conn.commit()
    conn.close()

def search_knowledge(question):
    conn = sqlite3.connect(DATABASE_FILE)
    cur = conn.cursor()
    q = question.lower().strip()
    cur.execute("SELECT answer FROM knowledge WHERE LOWER(question) = ?", (q,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0]
    cur.execute("SELECT answer FROM knowledge WHERE LOWER(question) LIKE ?", (f"%{q}%",))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

# ==========================
# WIKIPEDIA
# ==========================
def wiki_lookup(query):
    try:
        clean = re.sub(r"[^\w\s]", "", query)
        url = "https://pt.wikipedia.org/w/api.php"
        headers = {"User-Agent": "EiVORAK-Bot/2.0 (projeto pessoal)"}
        params = {"action": "query", "format": "json", "list": "search", "utf8": 1, "srsearch": clean, "srlimit": 1}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        hits = r.json().get("query", {}).get("search", [])
        if not hits: return None
        title = hits[0]["title"]
        params2 = {"action": "query", "format": "json", "prop": "extracts", "explaintext": 1, "exintro": 1, "exsentences": 5, "titles": title}
        r2 = requests.get(url, params=params2, headers=headers, timeout=10)
        r2.raise_for_status()
        pages = r2.json().get("query", {}).get("pages", {})
        for p in pages.values():
            extract = p.get("extract", "").strip()
            if extract: return f"📖 {title}:\n{extract}"
        return None
    except Exception as e:
        print(f"⚠️ Wikipedia erro: {e}")
        return None

# ==========================
# CÉREBRO — GROQ
# ==========================
def ask_groq(user_id, user_message):
    if not groq_client: return "⚠️ Cérebro offline."

    history = get_user_history(user_id, limit=10)
    known = search_knowledge(user_message)
    
    system = SYSTEM_PROMPT
    user_info = get_user_data(user_id)
    
    if user_info and user_info.get("first_name"):
        system += f"\n\nEstás a falar com o utilizador real chamado: {user_info['first_name']}. Trata-o pelo nome e diz 'Olá, {user_info['first_name']}' de forma natural caso seja o início da conversa ou faça sentido no contexto."
    
    if known: system += f"\n\nConhecimento relevante:\n{known}"

    messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": user_message}]

    try:
        response = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages, max_tokens=512, temperature=0.7)
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Groq erro: {e}")
        return "⚠️ Tive um problema a pensar."

# ==========================
# ADMIN
# ==========================
def is_admin(sender_id):
    return ADMIN_ID and str(sender_id) == str(ADMIN_ID)

def handle_admin(sender_id, text):
    cmd = text.strip()

    if cmd.lower().startswith("aprende:"):
        try:
            partes = cmd.split("=>")
            if len(partes) == 2:
                q = partes[0].replace("aprende:", "", 1).strip()
                a = partes[1].strip()
                if q and a:
                    save_knowledge(q, a)
                    return f"✅ Aprendi: '{q}'"
            return "❌ Formato: aprende: pergunta => resposta"
        except: return "❌ Erro ao ensinar."

    if cmd.lower() == "admin:users":
        export_to_txt()
        conn = sqlite3.connect(DATABASE_FILE)
        cur = conn.cursor()
        cur.execute("SELECT user_id, first_name, last_name, locale, timezone, message_count FROM users ORDER BY message_count DESC LIMIT 20")
        rows = cur.fetchall()
        conn.close()
        if not rows: return "Ainda não há utilizadores."
        lines = ["👥 Dados Recolhidos (TXT e Fotos atualizadas):"]
        for uid, fname, lname, locale, tz, count in rows:
            nome_completo = f"{fname} {lname}" if fname else "Desconhecido"
            pais = mapear_pais_por_fuso(tz)
            lines.append(f"• Nome: {nome_completo}\n  Região: {pais}\n  Total Msgs: {count}\n")
        return "\n".join(lines)

    if cmd.lower() == "admin:stats":
        conn = sqlite3.connect(DATABASE_FILE)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users"); users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM conversations"); msgs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge"); knowledge = cur.fetchone()[0]
        conn.close()
        return f"📊 Stats:\n• Utilizadores: {users}\n• Mensagens: {msgs}\n• Conhecimento: {knowledge} entradas"

    return None

# ==========================
# PROCESSAMENTO PRINCIPAL / FLASK
# ==========================
def process_message(sender_id, text):
    if text.strip().lower() in ["/eliminar meus dados", "eliminar meus dados", "apagar meus dados"]:
        if delete_user_data(sender_id):
            return "♻️ Os teus dados e o histórico de conversas foram completamente eliminados do meu sistema de armazenamento."
        return "⚠️ Ocorreu um erro ao tentar eliminar os teus dados. Tenta novamente mais tarde."

    if is_admin(sender_id):
        admin_resp = handle_admin(sender_id, text)
        if admin_resp: return admin_resp

    save_message(sender_id, "user", text)
    resposta = ask_groq(sender_id, text)
    save_message(sender_id, "assistant", resposta)
    return resposta

def send_message(sender_id, text):
    if not PAGE_ACCESS_TOKEN: return
    if len(text) > 2000: text = text[:1997] + "..."
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    try:
        r = requests.post("https://graph.facebook.com/v23.0/me/messages", params={"access_token": PAGE_ACCESS_TOKEN}, json=payload, timeout=8)
        r.raise_for_status()
    except Exception as e: print(f"❌ Erro envio: {e}")

@app.route("/", methods=["GET"])
def status(): return "ËiVORAK v2.0 ativo 🚀"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    init_db()  # <--- CORREÇÃO AQUI: Garante tabelas em cada verificação e recepção de dados
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == VERIFY_TOKEN: return challenge, 200
        return "Token inválido", 403

    data = request.get_json() or {}
    for entry in data.get("entry", []):
        for msg in entry.get("messaging", []):
            if "message" in msg:
                sender = msg["sender"]["id"]
                
                if "text" not in msg["message"]:
                    send_message(sender, "👋 Recebi o teu anexo/mídia! Mas, por agora, o ËiVORAK só consegue processar e responder a mensagens de texto plano.")
                    continue
                
                text = msg["message"]["text"]
                resposta = process_message(sender, text)
                send_message(sender, resposta)
                
    return "OK", 200

if __name__ == "__main__":
    init_db()
    export_to_txt()
    print("🚀 ËiVORAK v2.0 - Otimizado e Preparado para o App Review!")
    app.run(port=PORT, debug=False, threaded=True)