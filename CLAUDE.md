# telegram-bridge-lira-ig

## Хто я

Я — **тонкий адаптер** між Telegram і Trinity. Я не маю LLM-логіки. Моя робота:

1. Слухати Telegram через long-polling.
2. Фільтрувати — реагувати тільки на @mention / reply / DM / команди.
3. Multimodal preprocessing — voice (ElevenLabs), photo/video/PDF (Gemini 2.5 Flash).
4. Викликати `lira-ig-v2` (мізки Ліри) через Trinity REST `/api/agents/lira-ig-v2/chat`.
5. Повертати відповідь у Telegram (через editMessageText на placeholder-і).

Якщо ти оновлюєш цей репо — НЕ додавай Claude-логіки сюди. Будь-яка LLM-думка — у мізках Ліри.

## Контекст

Створено як **тестовий канал** паралельно з основним IG webhook (lira-ig-webhook). `session_id=tg:{chat_id}` ізольований від IG-сесій `ig:{sender_id}`, тому розмови з Telegram не торкаються Instagram-діалогів і навпаки.

Якщо тест завершиться, агента просто видалити з Trinity — це нічого не зачіпає в IG webhook.

## Структура

- `bot.py` — main long-polling loop + dispatcher (копія з kontentschyk, ASK_LIRA marker лишений як no-op)
- `lib/` — спільні модулі (Trinity client, chat_context, permissions, tg_send)
- `handlers/` — multimodal handlers (text/voice/photo/video/document/command)
- `.trinity/setup.sh` — Trinity автозапуск bot.py
- `template.yaml` — Trinity metadata
- `requirements.txt` — Python deps (requests, python-dotenv)

## Граблі (з reference docs)

- Trinity ігнорує `entrypoint` у template.yaml — потрібен `.trinity/setup.sh`
- `cpu: "0.5"` падає з `int(...)` — завжди ціле `"1"`
- Telegram **не показує typing для ботів у супергрупах** — placeholder + edit замість typing
- Privacy Mode toggle потребує kick & re-invite бота в групу
- `nohup` у звичайному `docker exec` може зависнути — `docker exec -d`
- Trinity у source_mode робить тільки `git fetch` — для оновлень руками `git pull` + рестарт
