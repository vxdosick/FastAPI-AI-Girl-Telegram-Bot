# She Wants You — AI Girlfriend Telegram Bot

**Your private chat where she actually remembers you.**

Flirty, warm, a little bold — not a cold chatbot. She picks up the vibe, keeps the thread alive, and feels like someone waiting for *you* in Telegram.

---

### Official version

Use the live bot here (the only version we support):

**[YOUR_OFFICIAL_BOT_LINK]**

*(Replace the link above with your Telegram bot URL, e.g. `https://t.me/YourBotName`)*

---

### Why people stay

* **Real girlfriend energy** — playful, romantic, messenger-style replies (not essay walls or robotic lists).
* **She remembers** — recent chat stays in context; over time she builds a living summary of you and your dynamic.
* **Private by design** — full experience in DM; in groups she only speaks up if you @ her or reply to her message.
* **Message packs** — free trial credits, then buy more when you want to keep talking.
* **You're in control** — wipe saved memory anytime; your credits stay.

---

### What she can do

| Feature | What it means for you |
|--------|------------------------|
| AI companion chat | Natural back-and-forth in private |
| Short-term memory | Last messages stay in the flow |
| Long-term memory | Relationship tone and facts evolve |
| Credits & checkout | Pay once, chat more |
| Privacy page | Terms & policies on the web |
| Delete my data | Clear memory with one confirmed tap |

---

### Bot commands

1. `/start` — say hi and jump in  
2. `/help` — all commands  
3. `/credits` — see how many messages you have left and buy more  
4. `/terms` — privacy & refund policy (web link)  
5. `/contacts` — reach support / developer  
6. `/delete_info` — delete all saved chat memory (credits stay)

---

### Built with

- Python 3.12  
- Telegram Bot API (python-telegram-bot)  
- FastAPI — webhooks & payments  
- PostgreSQL — users, credits, long-term memory  
- Redis — recent conversation window  
- SQLAlchemy 2.0 + asyncpg  
- Stripe — payments  
- Uvicorn — ASGI server  

---

### About this repository

This repo is shared **for inspiration and learning** — to see how a production-style Telegram companion bot can be structured (memory, credits, webhooks, async stack).

It is **not** offered as a turnkey product to deploy or resell. If you fork or clone it and run your own instance, **you are on your own**: the author does not support, maintain, or take responsibility for third-party use, misuse, bugs, data handling, payments, or any consequences. Use the **official bot link** above for the supported experience.

See [LICENSE](./LICENSE) for the legal terms of this codebase.

---

### Developer reference *(optional — may be removed later)*

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Development server:

```bash
uvicorn server.main:server --reload
```

Production:

```bash
uvicorn server.main:server --host 0.0.0.0 --port 8000
```

Telegram webhook (after the server is reachable at your public URL):

```bash
curl -F "url=https://YOUR_PUBLIC_URL/tg-webhook" https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook
```

Local tunnel example: `ngrok http 8000` → use the HTTPS URL as your public base for webhooks and `/privacy-policy`.
