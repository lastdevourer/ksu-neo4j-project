# Академічна мережа КСПУ / ХДУ

Streamlit MVP для дипломної теми:
`Програмний модуль обліку наукових публікацій викладачів на основі мережевого аналізу`.

## Що вміє сервіс

- показує структуру факультетів і кафедр у Neo4j
- відображає викладачів, їхні публікації та співавторів
- будує граф авторства між вузлами `Teacher` і `Publication`
- розраховує топ авторів, топ пар співавторів, `degree centrality` і `betweenness centrality`

## Модель даних

```text
(:Faculty)-[:HAS_DEPARTMENT]->(:Department)
(:Department)-[:HAS_TEACHER]->(:Teacher)
(:Teacher)-[:AUTHORED]->(:Publication)
```

## Streamlit Cloud + Neo4j Aura

Базовий сценарій деплою:

1. Завантажити репозиторій на GitHub.
2. Підключити репозиторій у Streamlit Cloud.
3. Вказати головний файл застосунку: `app.py`.
4. Додати секрети в налаштуваннях застосунку Streamlit.

Приклад секретів для Streamlit Cloud:

```toml
NEO4J_URI = "neo4j+s://your-aura-instance.databases.neo4j.io"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "your-password"
# NEO4J_DATABASE = "neo4j"
```

Локально ті самі параметри можна додати через `.env` або `st.secrets`:

```env
NEO4J_URI=neo4j+s://...
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
# NEO4J_DATABASE=neo4j
```

`NEO4J_DATABASE` не є обов'язковим. Якщо Neo4j Aura повертає помилку маршрутизації або `ClientError` під час першого запиту, приберіть цей параметр із секретів або вкажіть точну назву домашньої бази.

## Запуск

```bash
streamlit run app.py
```

У лівій панелі доступні службові дії:

- перевірка підключення до Aura
- створення constraints та indexes
- заповнення довідника факультетів і кафедр
