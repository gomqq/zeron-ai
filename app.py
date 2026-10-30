import os
import sqlite3
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai

# Загрузка настроек
load_dotenv(override=False)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "change-this-secret-before-deploying"
)

DB_PATH = os.getenv("ZERON_DB_PATH", "zeron_jobs.db")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
PORT = int(os.getenv("PORT", "5000"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zeron_ai")


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------
# БАЗА ДАННЫХ
# ------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(jobs)"
            ).fetchall()
        }

        if "error" not in columns:
            conn.execute(
                "ALTER TABLE jobs ADD COLUMN error TEXT"
            )

        if "updated_at" not in columns:
            conn.execute(
                "ALTER TABLE jobs ADD COLUMN updated_at TEXT"
            )

        conn.execute("""
            UPDATE jobs
            SET updated_at = COALESCE(updated_at, created_at)
            WHERE updated_at IS NULL
        """)


# ------------------------------
# ПОДКЛЮЧЕНИЕ GEMINI
# ------------------------------

def get_client():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "Не найден GEMINI_API_KEY. "
            "Проверь файл .env."
        )

    return genai.Client(api_key=api_key)


def ask_gemini(task):
    prompt = f"""
Ты — ZERON AI, умный ИИ-помощник и программист.

Правила:
- Отвечай на русском, если пользователь не попросил другой язык.
- Помогай с программированием, обучением и обычными вопросами.
- Если пользователь просит код, предоставляй готовый код.
- Объясняй сложные вещи простыми словами.
- Не утверждай, что выполнил действия на компьютере,
  если они фактически не выполнялись.

ЗАДАНИЕ ПОЛЬЗОВАТЕЛЯ:
{task}
"""

    client = get_client()

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    answer = (response.text or "").strip()

    if not answer:
        raise RuntimeError("Gemini вернул пустой ответ.")

    return answer


# ------------------------------
# ГЛАВНАЯ СТРАНИЦА
# ------------------------------

@app.get("/")
def home():
    return render_template("index.html")


# ------------------------------
# ПРОВЕРКА СЕРВЕРА
# ------------------------------

@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "app": "ZERON AI",
        "model": MODEL_NAME,
        "api_key_configured": bool(
            os.getenv("GEMINI_API_KEY", "").strip()
        )
    })


# ------------------------------
# СОЗДАНИЕ ЗАДАНИЯ
# ------------------------------

@app.post("/api/jobs")
def create_job():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        data = request.form.to_dict()

    task = (
        data.get("task")
        or data.get("prompt")
        or data.get("message")
        or data.get("text")
        or ""
    )

    task = str(task).strip()

    if not task:
        return jsonify({
            "error": "Напиши задание для ZERON AI."
        }), 400

    if len(task) > 10000:
        return jsonify({
            "error": "Задание слишком длинное. Максимум 10000 символов."
        }), 413

    created_at = utc_now()

    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO jobs (
                task,
                status,
                result,
                error,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            task,
            "running",
            None,
            None,
            created_at,
            created_at
        ))

        job_id = cursor.lastrowid

    try:
        # Отправляем задание Gemini
        answer = ask_gemini(task)

        # Сохраняем результат
        with get_db() as conn:
            conn.execute("""
                UPDATE jobs
                SET status = ?,
                    result = ?,
                    error = NULL,
                    updated_at = ?
                WHERE id = ?
            """, (
                "completed",
                answer,
                utc_now(),
                job_id
            ))

        return jsonify({
            "id": job_id,
            "job_id": job_id,
            "task": task,
            "status": "completed",
            "result": answer,
            "answer": answer,
            "created_at": created_at
        }), 200

    except Exception as exc:
        logger.exception(
            "ZERON AI error for job %s",
            job_id
        )

        error_text = f"{type(exc).__name__}: {exc}"

        with get_db() as conn:
            conn.execute("""
                UPDATE jobs
                SET status = ?,
                    error = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                "failed",
                error_text[:2000],
                utc_now(),
                job_id
            ))

        return jsonify({
            "id": job_id,
            "job_id": job_id,
            "task": task,
            "status": "failed",
            "error": error_text,
            "message": (
                "Не удалось получить ответ от Gemini. "
                "Подробности смотри в терминале VS Code."
            )
        }), 502


# ------------------------------
# ИСТОРИЯ ЗАДАНИЙ
# ------------------------------

@app.get("/api/jobs")
def list_jobs():
    try:
        limit = request.args.get(
            "limit",
            default=50,
            type=int
        )

        limit = max(1, min(limit or 50, 100))

        with get_db() as conn:
            rows = conn.execute("""
                SELECT
                    id,
                    task,
                    status,
                    result,
                    error,
                    created_at,
                    updated_at
                FROM jobs
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()

        jobs = [dict(row) for row in rows]

        return jsonify({
            "jobs": jobs,
            "items": jobs,
            "count": len(jobs)
        })

    except Exception:
        logger.exception(
            "Ошибка загрузки истории заданий"
        )

        return jsonify({
            "error": "Не удалось загрузить историю заданий."
        }), 500


# ------------------------------
# ПОЛУЧЕНИЕ ОДНОГО ЗАДАНИЯ
# ------------------------------

@app.get("/api/jobs/<int:job_id>")
def get_job(job_id):
    try:
        with get_db() as conn:
            row = conn.execute("""
                SELECT
                    id,
                    task,
                    status,
                    result,
                    error,
                    created_at,
                    updated_at
                FROM jobs
                WHERE id = ?
            """, (job_id,)).fetchone()

        if row is None:
            return jsonify({
                "error": "Задание не найдено."
            }), 404

        job = dict(row)
        job["job_id"] = job["id"]
        job["answer"] = job["result"]

        return jsonify(job)

    except Exception:
        logger.exception(
            "Ошибка загрузки задания %s",
            job_id
        )

        return jsonify({
            "error": "Не удалось загрузить задание."
        }), 500


# ------------------------------
# ОБРАБОТКА ОШИБОК
# ------------------------------

@app.errorhandler(404)
def not_found(_error):
    return jsonify({
        "error": "Маршрут не найден."
    }), 404


@app.errorhandler(500)
def internal_error(_error):
    logger.exception(
        "Внутренняя ошибка Flask"
    )

    return jsonify({
        "error": "Внутренняя ошибка сервера."
    }), 500


# ------------------------------
# ЗАПУСК
# ------------------------------

init_db()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=PORT,
        debug=False
    )