import sqlite3

database = sqlite3.connect("login.db")


def reset_database():
    cursor = database.cursor()

    cursor.execute("DROP TABLE users")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            auth_code TEXT,
            chat_id TEXT,
            telegram_auth TEXT,
            telegram_register_key TEXT,
            session_key TEXT
        )''')

    database.commit()


if __name__ == "__main__":
    reset_database()
