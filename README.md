# KSPU Academic Network

Streamlit-сервіс для обліку та аналізу наукових публікацій викладачів у Neo4j.

## Запуск

```bash
streamlit run app.py
```

## Secrets

```toml
NEO4J_URI = "neo4j+s://..."
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "..."

OPENALEX_API_KEY = "..."
CROSSREF_MAILTO = "you@example.com"
ORCID_CLIENT_ID = "..."
ORCID_CLIENT_SECRET = "..."
```

`NEO4J_DATABASE` необов'язковий. Для Neo4j Aura його краще не вказувати, якщо домашня база вже визначається автоматично.

## Структура проєкту

- `app.py` — точка входу, маршрутизація сторінок і запуск UI.
- `config.py` — читання secrets/env і конфігурація імпорту.
- `views/` — сторінки Streamlit.
- `ui/` — оформлення, компоненти, сайдбар, форматування таблиць.
- `services/neo4j_service.py` — робота з Neo4j, CRUD, аналітика, модерація.
- `services/publication_import.py` — unified import публікацій із зовнішніх джерел.
- `services/publication_sources.py` — низькорівнева логіка пошуку джерел і матчинг.
- `utils/` — мережевий аналіз і побудова графів.
- `data/seed_data.py` — seed-структура факультетів і кафедр.
- `data/loaders.py` — завантаження seed-даних.
- `data/seed_teachers.csv` — seed викладачів.
- `data/import_templates/` — шаблони CSV для ручного імпорту.
- `docs/data_pipeline.md` — нотатки про pipeline імпорту.
- `scripts/scrape_kspu_teachers.py` — допоміжний скрипт збору викладачів KSPU.

## Основні сторінки

- `Дашборд` — ключові метрики та структура.
- `Структура` — факультети, кафедри, викладачі, сервісні дії.
- `Викладачі` — картка викладача, публікації, співавтори.
- `Публікації` — модерація та перегляд робіт.
- `Центр даних` — аудит, проблемні записи, ручне додавання.
- `Граф` — мережеві візуалізації.
- `Аналітика` — рейтинги, centrality, звіти, експорт.
