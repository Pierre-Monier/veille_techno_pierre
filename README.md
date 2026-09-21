# 📡 Veille automatique

Chaque lundi matin : lecture des flux RSS et des nouvelles versions d'apps concurrentes,
résumé en français par Claude, ajout dans la base Notion « 📡 Veille Tech & Auto »,
puis digest envoyé sur Telegram avec des liens cliquables.

## Mise en place (une seule fois)

1. **Repo GitHub** : crée un repo privé et pousse ces fichiers (y compris `.github/`).

2. **chat_id Telegram** : envoie un message à ton bot, puis ouvre
   `https://api.telegram.org/bot<TON_TOKEN>/getUpdates` dans un navigateur.
   Le chat_id est la valeur `"chat":{"id": ...}`.

3. **Intégration Notion** : sur https://www.notion.so/profile/integrations, crée une
   intégration interne et copie son secret. Puis, dans la base Notion :
   menu `•••` → **Connexions** → ajoute ton intégration (sinon elle n'a pas accès).

4. **Clé API Claude** : sur https://console.anthropic.com.

5. **Secrets GitHub** (Settings → Secrets and variables → Actions) :

   | Secret | Valeur |
   |---|---|
   | `TELEGRAM_TOKEN` | token donné par BotFather |
   | `TELEGRAM_CHAT_ID` | ton chat_id |
   | `NOTION_TOKEN` | secret de l'intégration Notion |
   | `NOTION_DATABASE_ID` | `ea38a14a74ae45729dfd1961e6cd0a97` |
   | `ANTHROPIC_API_KEY` | ta clé API |

6. **Premier lancement** : onglet Actions → « Veille hebdo » → **Run workflow**.

## Personnaliser

- **Sources et apps concurrentes** : `config.yaml`.
- **Fréquence** : la ligne `cron` du workflow (`0 6 * * *` = tous les jours).
- **Test local sans rien écrire** : `DRY_RUN=1 python veille.py` (avec les variables d'env).
- **Modèle** : variable `CLAUDE_MODEL` (Haiku par défaut, quelques centimes par semaine).

Les doublons sont évités en vérifiant le lien dans Notion : tu peux relancer sans risque.
