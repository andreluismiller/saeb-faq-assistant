import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras


def get_db_connection():
    """Abre uma conexão com o Postgres usando variáveis de ambiente."""
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "saeb_faq"),
        user=os.environ.get("POSTGRES_USER", "saeb_user"),
        password=os.environ.get("POSTGRES_PASSWORD", "saeb_password"),
    )


CREATE_CONVERSATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    course TEXT NOT NULL,
    model TEXT NOT NULL,
    instructions TEXT NOT NULL,
    prompt TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    response_time FLOAT NOT NULL,
    cost FLOAT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
);
"""

CREATE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    source TEXT NOT NULL,
    relevance TEXT,
    explanation TEXT,
    score INTEGER,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
);
"""


def init_db():
    """Cria as tabelas 'conversations' e 'feedback' caso ainda não existam."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_CONVERSATIONS_TABLE)
            cur.execute(CREATE_FEEDBACK_TABLE)
        conn.commit()
    finally:
        conn.close()


def save_conversation(
    question: str,
    answer: str,
    course: str,
    model: str,
    instructions: str,
    prompt: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    response_time: float,
    cost: float,
    timestamp: datetime | None = None,
) -> int:
    """Insere uma nova interação em 'conversations' e retorna o id gerado."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (
                    question, answer, course, model, instructions, prompt,
                    prompt_tokens, completion_tokens, total_tokens,
                    response_time, cost, timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    question,
                    answer,
                    course,
                    model,
                    instructions,
                    prompt,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    response_time,
                    cost,
                    timestamp or datetime.now(timezone.utc),
                ),
            )
            conversation_id = cur.fetchone()[0]
        conn.commit()
        return conversation_id
    finally:
        conn.close()


def save_feedback(
    conversation_id: int,
    score: int,
    source: str = "user",
    relevance: str | None = None,
    explanation: str | None = None,
    timestamp: datetime | None = None,
):
    """
    Insere uma avaliação em 'feedback'.
    score: 1 para thumbs up, -1 para thumbs down.
    source: origem da avaliação (ex.: "user", "llm_judge").
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (
                    conversation_id, source, relevance, explanation, score, timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    conversation_id,
                    source,
                    relevance,
                    explanation,
                    score,
                    timestamp or datetime.now(timezone.utc),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_recent_conversations(limit: int = 20):
    """Retorna as interações mais recentes (útil para depuração/dashboards)."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.*, f.score AS feedback_score
                FROM conversations c
                LEFT JOIN feedback f ON f.conversation_id = c.id
                ORDER BY c.timestamp DESC
                LIMIT %s;
                """,
                (limit,),
            )
            return cur.fetchall()
    finally:
        conn.close()


if __name__ == "__main__":
    # Uso: python -m saeb_faq_assistant.db
    print("Inicializando tabelas no Postgres...")
    init_db()
    print("Tabelas 'conversations' e 'feedback' prontas.")