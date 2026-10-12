# ABOUTME: Fixe des variables d'env factices pour que veille.py s'importe en test.
# ABOUTME: Les tests unitaires n'appellent ni Notion, ni Telegram, ni Claude.

import os

for key in ("NOTION_TOKEN", "NOTION_DATABASE_ID", "TELEGRAM_TOKEN",
            "TELEGRAM_CHAT_ID", "ANTHROPIC_API_KEY"):
    os.environ.setdefault(key, "test")
