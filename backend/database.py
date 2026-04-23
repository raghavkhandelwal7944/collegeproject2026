import logging
import os
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MySQL Configuration
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USERNAME", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "project2026")

# MongoDB Configuration
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "project2026")

def get_mongo_connection():
    """Establish and return a MongoDB database connection."""
    try:
        client = MongoClient(MONGO_HOST, MONGO_PORT)
        db = client[MONGO_DATABASE]
        return db
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {e}")
        return None

def generate_session_title(user_message: str) -> str:
    """Use Gemini to produce a short title (≤8 words) for a new chat session."""
    try:
        import os

        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content(
            f"Summarise this message as a chat title in 5 words or fewer, no quotes:\n{user_message[:300]}"
        )
        title = resp.text.strip().strip('"').strip("'")
        return title[:60] if title else user_message[:40]
    except Exception as e:
        logger.warning(f"Could not generate session title: {e}")
        return user_message[:40]


def save_conversation(username, user_message, bot_response,
                      session_id: str | None = None,
                      session_title: str | None = None):
    """Save one conversation turn to MongoDB, tagged with session_id."""
    try:
        db = get_mongo_connection()
        if db is not None:
            collection = db["conversations"]
            document = {
                "username": username,
                "user_message": user_message,
                "bot_response": bot_response,
                "session_id": session_id or "default",
                "session_title": session_title or user_message[:40],
                "timestamp": datetime.now()
            }
            collection.insert_one(document)
            logger.info(f"Conversation saved for user '{username}' session '{session_id}'.")
    except Exception as e:
        logger.error(f"Error saving conversation to MongoDB: {e}")

def get_user_conversations(username, limit=50):
    """Fetch user conversations from MongoDB."""
    try:
        db = get_mongo_connection()
        if db is not None:
            collection = db["conversations"]
            conversations = list(collection.find({"username": username}, {"_id": 0}).sort("timestamp", -1).limit(limit))
            return conversations
        return []
    except Exception as e:
        logger.error(f"Error fetching conversations from MongoDB: {e}")
        return []


def list_user_sessions(username: str) -> list:
    """Return distinct chat sessions for a user, newest first."""
    try:
        db = get_mongo_connection()
        if db is None:
            return []
        collection = db["conversations"]
        pipeline = [
            {"$match": {"username": username}},
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$session_id",
                "session_title": {"$first": "$session_title"},
                "last_message": {"$first": "$timestamp"},
                "message_count": {"$sum": 1},
            }},
            {"$sort": {"last_message": -1}},
            {"$project": {
                "_id": 0,
                "session_id": "$_id",
                "title": "$session_title",
                "last_message": {"$toString": "$last_message"},
                "message_count": 1,
            }},
        ]
        return list(collection.aggregate(pipeline))
    except Exception as e:
        logger.error(f"Error listing sessions for '{username}': {e}")
        return []


def get_session_messages(username: str, session_id: str) -> list:
    """Return all turns for a specific session as [{role,content}] oldest-first."""
    try:
        db = get_mongo_connection()
        if db is None:
            return []
        collection = db["conversations"]
        docs = list(
            collection.find(
                {"username": username, "session_id": session_id},
                {"_id": 0, "user_message": 1, "bot_response": 1, "timestamp": 1}
            ).sort("timestamp", 1)
        )
        messages = []
        for doc in docs:
            messages.append({"role": "user",      "content": doc["user_message"]})
            messages.append({"role": "assistant", "content": doc["bot_response"]})
        return messages
    except Exception as e:
        logger.error(f"Error fetching session messages for '{username}/{session_id}': {e}")
        return []

def get_db_connection():
    """Establish and return a MySQL database connection."""
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Error connecting to MySQL: {err}")
        # Try to connect without database to create it if it doesn't exist
        if err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            create_database()
            return mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE
            )
        raise

def create_database():
    """Create the database if it doesn't exist."""
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE}")
        conn.close()
        logger.info(f"Database '{MYSQL_DATABASE}' checked/created successfully.")
    except mysql.connector.Error as err:
        logger.critical(f"Failed to create database: {err}")
        raise

def init_db():
    """Initialize the database and create tables if they don't exist."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Logs Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp VARCHAR(255) NOT NULL,
                user_input TEXT,
                blocked BOOLEAN,
                violation_type VARCHAR(255)
            )
        ''')

        # Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                email VARCHAR(255)
            )
        ''')
        # Migrate existing tables that lack the new columns
        for col, defn in [("first_name", "VARCHAR(100)"), ("last_name", "VARCHAR(100)"), ("email", "VARCHAR(255)")]:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
            except mysql.connector.Error as _col_err:
                if _col_err.errno == 1060:  # Duplicate column — already exists
                    pass
                else:
                    raise

        # Per-user policy flags (0/1)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_policies (
                username       VARCHAR(255) PRIMARY KEY,
                aggressive_pii TINYINT NOT NULL DEFAULT 0,
                semantic_cache TINYINT NOT NULL DEFAULT 1,
                code_block     TINYINT NOT NULL DEFAULT 0
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Database tables initialized.")
    except mysql.connector.Error as err:
        logger.error(f"Error initializing database: {err}")
        raise


def get_user_policies(username: str) -> dict:
    """Return the policy row for *username*, creating defaults if absent."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            'SELECT aggressive_pii, semantic_cache, code_block FROM user_policies WHERE username = %s',
            (username,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {k: bool(v) for k, v in row.items()}
        # First time — insert defaults and return them
        set_user_policies(username, aggressive_pii=False, semantic_cache=True, code_block=False)
        return {"aggressive_pii": False, "semantic_cache": True, "code_block": False}
    except mysql.connector.Error as err:
        logger.error(f"Error fetching policies for '{username}': {err}")
        return {"aggressive_pii": False, "semantic_cache": True, "code_block": False}
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()


def set_user_policies(username: str, aggressive_pii: bool, semantic_cache: bool, code_block: bool) -> None:
    """Upsert policy flags for *username*."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO user_policies (username, aggressive_pii, semantic_cache, code_block)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                aggressive_pii = VALUES(aggressive_pii),
                semantic_cache = VALUES(semantic_cache),
                code_block     = VALUES(code_block)
            ''',
            (username, int(aggressive_pii), int(semantic_cache), int(code_block))
        )
        conn.commit()
        conn.close()
        logger.info(f"Policies updated for '{username}'.")
    except mysql.connector.Error as err:
        logger.error(f"Error setting policies for '{username}': {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()


def get_conversation_history(username: str, limit: int = 20,
                             session_id: str | None = None) -> list:
    """Return last *limit* turns as [{role, content}] for Mistral context (oldest first).
    If session_id is provided, returns only that session's history."""
    try:
        db = get_mongo_connection()
        if db is None:
            return []
        collection = db["conversations"]
        query: dict = {"username": username}
        if session_id:
            query["session_id"] = session_id
        docs = list(
            collection.find(
                query,
                {"_id": 0, "user_message": 1, "bot_response": 1}
            ).sort("timestamp", -1).limit(limit)
        )
        messages = []
        for doc in reversed(docs):
            messages.append({"role": "user",      "content": doc["user_message"]})
            messages.append({"role": "assistant", "content": doc["bot_response"]})
        return messages
    except Exception as e:
        logger.error(f"Error fetching conversation history for '{username}': {e}")
        return []

def create_user(username, hashed_password, first_name=None, last_name=None, email=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (username, hashed_password, first_name, last_name, email) VALUES (%s, %s, %s, %s, %s)',
            (username, hashed_password, first_name, last_name, email)
        )
        conn.commit()
        conn.close()
        logger.info(f"User '{username}' created successfully.")
        return True
    except mysql.connector.Error as err:
        if err.errno == mysql.connector.errorcode.ER_DUP_ENTRY:
            logger.warning(f"Attempt to register existing user: {username}")
            return False
        logger.error(f"Database error creating user: {err}")
        return False
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

def get_user(username):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        conn.close()
        return user
    except mysql.connector.Error as err:
        logger.error(f"Error fetching user '{username}': {err}")
        return None
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

def log_request(user_input: str, blocked: bool, violation_type: str):
    """
    Log every attempt to the database.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO logs (timestamp, user_input, blocked, violation_type)
            VALUES (%s, %s, %s, %s)
        ''', (timestamp, user_input, blocked, violation_type))
        
        conn.commit()
        conn.close()
        logger.info(f"Request logged. Blocked: {blocked}, Violation: {violation_type}")
    except mysql.connector.Error as err:
        logger.error(f"Error logging request: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

def get_recent_logs(limit: int = 20):
    """Fetch the most recent logs."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('''
            SELECT timestamp, user_input, blocked, violation_type 
            FROM logs 
            ORDER BY id DESC 
            LIMIT %s
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        return rows
    except mysql.connector.Error as err:
        logger.error(f"Error fetching logs: {err}")
        return []
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

def get_stats():
    """Calculate and return basic statistics."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total Requests
        cursor.execute('SELECT COUNT(*) FROM logs')
        total_requests = cursor.fetchone()[0]
        
        # Total Blocked
        cursor.execute('SELECT COUNT(*) FROM logs WHERE blocked = 1')
        total_blocked = cursor.fetchone()[0]
        
        conn.close()
        
        percentage_blocked = 0.0
        if total_requests > 0:
            percentage_blocked = (total_blocked / total_requests) * 100
            
        return {
            "total_requests": total_requests,
            "total_blocked": total_blocked,
            "percentage_blocked": round(percentage_blocked, 2)
        }
    except mysql.connector.Error as err:
        logger.error(f"Error fetching stats: {err}")
        return {
            "total_requests": 0,
            "total_blocked": 0,
            "percentage_blocked": 0.0
        }
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()
