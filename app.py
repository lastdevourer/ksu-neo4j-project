import streamlit as st
from neo4j import GraphDatabase
import pandas as pd

st.set_page_config(page_title="KSPU Academic Graph", layout="wide")
st.title("KSPU Academic Graph")

if "NEO4J_URI" not in st.secrets or "NEO4J_USER" not in st.secrets or "NEO4J_PASSWORD" not in st.secrets:
    st.error("Добавь NEO4J_URI, NEO4J_USER и NEO4J_PASSWORD в Streamlit Secrets.")
    st.stop()

URI = st.secrets["NEO4J_URI"]
USER = st.secrets["NEO4J_USER"]
PASSWORD = st.secrets["NEO4J_PASSWORD"]

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))


def run_query(query: str, params: dict | None = None):
    with driver.session() as session:
        return list(session.run(query, params or {}))


def execute_write(query: str, rows: list[dict]):
    with driver.session() as session:
        session.run(query, {"rows": rows})
        session.run("RETURN 1")


def get_counts():
    q = """
    RETURN
      size([(f:Faculty) | f]) AS faculties,
      size([(d:Department) | d]) AS departments,
      size([(t:Teacher) | t]) AS teachers,
      size([(p:Publication) | p]) AS publications,
      size([()-[r:AUTHORED]->() | r]) AS authored,
      size([()-[r:CO_AUTHOR_WITH]->() | r]) AS coauthor,
      size([()-[r:HAS_TOPIC]->() | r]) AS topics
    """
    rec = run_query(q)[0]
    return dict(rec)


def create_constraints():
    queries = [
        "CREATE CONSTRAINT faculty_id_unique IF NOT EXISTS FOR (f:Faculty) REQUIRE f.faculty_id IS UNIQUE",
        "CREATE CONSTRAINT department_id_unique IF NOT EXISTS FOR (d:Department) REQUIRE d.department_id IS UNIQUE",
        "CREATE CONSTRAINT teacher_id_unique IF NOT EXISTS FOR (t:Teacher) REQUIRE t.teacher_id IS UNIQUE",
        "CREATE CONSTRAINT publication_id_unique IF NOT EXISTS FOR (p:Publication) REQUIRE p.publication_id IS UNIQUE",
    ]
    with driver.session() as session:
        for q in queries:
            session.run(q)


def upload_csv(file):
    df = pd.read_csv(file)
    df = df.fillna("")
    return df


st.subheader("1. Подключение")
if st.button("Проверить подключение"):
    result = run_query("MATCH (n) RETURN count(n) AS cnt")
    st.success(f"Подключено! Узлов: {result[0]['cnt']}")

if st.button("Создать ограничения уникальности"):
    create_constraints()
    st.success("Constraints созданы.")

st.subheader("2. Состояние базы")
try:
    counts = get_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Faculties", counts["faculties"])
    c2.metric("Departments", counts["departments"])
    c3.metric("Teachers", counts["teachers"])
    c4.metric("Publications", counts["publications"])

    c5, c6, c7 = st.columns(3)
    c5.metric("AUTHORED", counts["authored"])
    c6.metric("CO_AUTHOR_WITH", counts["coauthor"])
    c7.metric("HAS_TOPIC", counts["topics"])
except Exception as e:
    st.warning(f"Не удалось получить счётчики: {e}")

st.subheader("3. Загрузка CSV")

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Faculties",
    "Departments",
    "Faculty-Department",
    "Teachers",
    "Department-Teacher",
    "Publications",
    "Authored + Topics"
])

with tab1:
    file = st.file_uploader("Загрузи faculties CSV", type="csv", key="faculties")
    if file:
        df = upload_csv(file)
        st.dataframe(df.head())
        if st.button("Импортировать Faculties"):
            rows = df.to_dict("records")
            query = """
            UNWIND $rows AS row
            MERGE (f:Faculty {faculty_id: row.faculty_id})
            SET f.name = row.name
            """
            execute_write(query, rows)
            st.success(f"Импортировано строк: {len(rows)}")

with tab2:
    file = st.file_uploader("Загрузи departments CSV", type="csv", key="departments")
    if file:
        df = upload_csv(file)
        st.dataframe(df.head())
        if st.button("Импортировать Departments"):
            rows = df.to_dict("records")
            query = """
            UNWIND $rows AS row
            MERGE (d:Department {department_id: row.department_id})
            SET d.name = row.name
            """
            execute_write(query, rows)
            st.success(f"Импортировано строк: {len(rows)}")

with tab3:
    file = st.file_uploader("Загрузи faculty_department_relations CSV", type="csv", key="fd_rel")
    if file:
        df = upload_csv(file)
        st.dataframe(df.head())
        if st.button("Импортировать Faculty-Department"):
            rows = df.to_dict("records")
            query = """
            UNWIND $rows AS row
            MATCH (f:Faculty {faculty_id: row.faculty_id})
            MATCH (d:Department {department_id: row.department_id})
            MERGE (f)-[:HAS_DEPARTMENT]->(d)
            """
            execute_write(query, rows)
            st.success(f"Импортировано строк: {len(rows)}")

with tab4:
    file = st.file_uploader("Загрузи teachers CSV", type="csv", key="teachers")
    if file:
        df = upload_csv(file)
        st.dataframe(df.head())
        if st.button("Импортировать Teachers"):
            rows = df.to_dict("records")
            query = """
            UNWIND $rows AS row
            MERGE (t:Teacher {teacher_id: row.teacher_id})
            SET t.full_name = row.full_name,
                t.position = row.position,
                t.academic_degree = row.academic_degree,
                t.academic_title = row.academic_title,
                t.department_id = row.department_id,
                t.faculty_id = row.faculty_id,
                t.source_url = row.source_url
            """
            execute_write(query, rows)
            st.success(f"Импортировано строк: {len(rows)}")

with tab5:
    file = st.file_uploader("Загрузи department_teacher_relations CSV", type="csv", key="dt_rel")
    if file:
        df = upload_csv(file)
        st.dataframe(df.head())
        if st.button("Импортировать Department-Teacher"):
            rows = df.to_dict("records")
            query = """
            UNWIND $rows AS row
            MATCH (d:Department {department_id: row.department_id})
            MATCH (t:Teacher {teacher_id: row.teacher_id})
            MERGE (d)-[:HAS_TEACHER]->(t)
            """
            execute_write(query, rows)
            st.success(f"Импортировано строк: {len(rows)}")

with tab6:
    file = st.file_uploader("Загрузи publications CSV", type="csv", key="publications")
    if file:
        df = upload_csv(file)
        st.dataframe(df.head())
        if st.button("Импортировать Publications"):
            rows = df.to_dict("records")
            query = """
            UNWIND $rows AS row
            MERGE (p:Publication {publication_id: row.publication_id})
            SET p.title = row.title,
                p.year = CASE WHEN row.year = '' THEN null ELSE toInteger(row.year) END,
                p.doi = CASE WHEN row.doi = '' THEN null ELSE row.doi END,
                p.pub_type = row.pub_type,
                p.source_type = row.source_type,
                p.confidence = row.confidence,
                p.source = row.source,
                p.source_url = row.source_url,
                p.notes = row.notes
            """
            execute_write(query, rows)
            st.success(f"Импортировано строк: {len(rows)}")

with tab7:
    file_auth = st.file_uploader("Загрузи authored CSV", type="csv", key="authored")
    file_topics = st.file_uploader("Загрузи topics CSV", type="csv", key="topics")

    if file_auth:
        df_auth = upload_csv(file_auth)
        st.dataframe(df_auth.head())

    if file_topics:
        df_topics = upload_csv(file_topics)
        st.dataframe(df_topics.head())

    if file_auth and st.button("Импортировать Authored"):
        rows = df_auth.to_dict("records")
        query = """
        UNWIND $rows AS row
        MATCH (t:Teacher {teacher_id: row.teacher_id})
        MATCH (p:Publication {publication_id: row.publication_id})
        MERGE (t)-[r:AUTHORED]->(p)
        SET r.author_order = CASE WHEN row.author_order = '' THEN null ELSE toInteger(row.author_order) END
        """
        execute_write(query, rows)
        st.success(f"Импортировано Authored: {len(rows)}")

    if file_topics and st.button("Импортировать Topics"):
        rows = df_topics.to_dict("records")
        query = """
        UNWIND $rows AS row
        MATCH (p:Publication {publication_id: row.publication_id})
        MERGE (tp:Topic {name: row.topic_name})
        MERGE (p)-[:HAS_TOPIC]->(tp)
        """
        execute_write(query, rows)
        st.success(f"Импортировано Topics: {len(rows)}")

st.subheader("4. Служебные действия")

if st.button("Построить PublicationYear"):
    q = """
    MATCH (p:Publication)
    WHERE p.year IS NOT NULL
    MERGE (py:PublicationYear {year: toInteger(p.year)})
    MERGE (p)-[:PUBLISHED_IN_YEAR]->(py)
    """
    run_query(q)
    st.success("PublicationYear построены.")

if st.button("Пересчитать CO_AUTHOR_WITH"):
    q = """
    MATCH (a:Teacher)-[:AUTHORED]->(p:Publication)<-[:AUTHORED]-(b:Teacher)
    WHERE id(a) < id(b)
    WITH a, b, count(DISTINCT p) AS shared_pubs, collect(DISTINCT p.publication_id) AS pub_ids
    MERGE (a)-[r:CO_AUTHOR_WITH]->(b)
    SET r.weight = shared_pubs,
        r.publication_ids = pub_ids
    """
    run_query(q)
    st.success("CO_AUTHOR_WITH пересчитаны.")
