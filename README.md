# telegram-bridge-lira-ig

**Тонкий long-polling Telegram-адаптер** для `lira-ig-v2` (мізки Ліри) — **тестовий канал** паралельно з IG webhook.

> Зроблено з шаблону `telegram-bridge-kontentschyk`. Логіка та ризики ідентичні; зміни лише в назвах і `TARGET_AGENT`.

## Що робить

- Слухає Telegram через `getUpdates` long-polling (без webhook, без публічного URL).
- DM + group режим, фільтр `@mention | reply | DM | command`.
- Multimodal preprocessing:
  - **Voice** — ElevenLabs Scribe v2 → `[голосове 0:30]: {text}`
  - **Photo** — Gemini 2.5 Flash → `[фото]: {опис}`
  - **Video** — Gemini 2.5 Flash → `[відео 0:45]: {опис + speech}`
  - **Video note** — Gemini → `[кружечок]: {опис}`
  - **PDF** — Gemini multimodal → `[файл PDF: name.pdf]: {витяжка}`
- Викликає мізки через Trinity REST `/api/agents/lira-ig-v2/chat` з `session_id=tg:{chat_id}`.
- Закрите-by-default permissions — fail-fast якщо `ALLOWED_*_USER_IDS` не сконфігуровано.

## Чому це безпечно для IG

- session_id `tg:{chat_id}` ≠ `ig:{sender_id}` — історії не змішуються
- Bridge — окремий Trinity-контейнер; не змінює `lira-ig-v2`
- IG webhook продовжує працювати незалежно

## Архітектура

```
Telegram → telegram-bridge-lira-ig (цей репо, long-polling)
                       ↓
   POST /api/agents/lira-ig-v2/chat (180s timeout)
                       ↓
        lira-ig-v2 (Ліра, Opus 4.7)
        github.com/volosovd-fun/agent-lira-ig

Instagram → lira-ig-webhook → POST /api/public/chat/{token}
                       ↓
                  lira-ig-v2 (та сама Ліра, інша сесія)
```

## Setup

1. **BotFather:** `/newbot` → новий токен. `/setprivacy → DISABLE` (для груп). `/setjoingroups → ENABLE`.
2. **Trinity create:** `POST /api/agents` з `template:"github:volosovd-fun/telegram-bridge-lira-ig"`.
3. **Inject credentials:** `TELEGRAM_BOT_TOKEN`, `ALLOWED_DM_USER_IDS`, `ALLOWED_GROUP_USER_IDS`, `ADMIN_USER_IDS`, `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`.
4. **Permissions hygiene:** дати `telegram-bridge-lira-ig` право викликати `lira-ig-v2` у Trinity UI.
5. **Verify:** `docker exec agent-telegram-bridge-lira-ig tail logs/bot.log` → `Bot @... is ready!`.
6. **Smoke test:** написати боту в DM або `@bot привіт` у групі.

## Граблі (успадковані з kontentschyk)

- Trinity ігнорує `entrypoint` — використовуємо `.trinity/setup.sh`.
- Privacy toggle у BotFather потребує kick & re-invite бота.
- Telegram **не показує typing для ботів у супергрупах** — використовуємо 🤓 reaction + placeholder edit.
- При оновленнях: `docker exec agent-telegram-bridge-lira-ig git -C /home/developer pull` + рестарт bot.py.
