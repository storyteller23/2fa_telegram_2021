from flask import Flask, render_template, request, session, url_for, redirect
from config import BOT_TOKEN
from key_generate import key_generate
import requests
import hashlib
import sqlite3

DATABASE = "login.db"
app = Flask(__name__)
app.secret_key = "fjafkjhkjfladskfhk"

PASSWORD_SALT = "SALT"


def password_hash_generate(password):
    pswd_hash = hashlib.sha256((password
                                + PASSWORD_SALT).strip().encode()).hexdigest()
    return pswd_hash


def session_hash_generate(username, password):
    session_hash = hashlib.sha256((username
                                   + password).strip().encode()).hexdigest()
    return session_hash


def send_message(chat_id, text):
    method = "sendMessage"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, data=data)


@app.route("/", methods=["POST"])
def bot():
    text = ""
    message_text = request.json["message"]["text"]

    chat_id = request.json["message"]["chat"]["id"]
    if message_text.split()[0] == "/start":
        text = "Бот для двухфакторной аутентификации."
        send_message(chat_id, text)

    if message_text.split()[0] == "/info":
        with sqlite3.connect(DATABASE) as con:
            cursor = con.cursor()
            cursor.execute(f"SELECT username FROM users \
                            WHERE chat_id = {chat_id}")
            searched_user = cursor.fetchone()
            if searched_user:
                text = f"Данный телеграм привязан к учетной записи пользователя: {searched_user[0]}."
            else:
                text = "Данный телеграм не привязан."
            send_message(chat_id, text)

    if len(message_text.split()) > 1:
        command = message_text.split()[0]
        key = message_text.split()[1].upper()
        if command == "/bind":
            with sqlite3.connect(DATABASE) as con:
                cursor = con.cursor()
                cursor.execute(f"SELECT * \
                            FROM users \
                            WHERE telegram_register_key = '{key}'")
                if cursor.fetchone():
                    cursor.execute(f"SELECT * FROM users\
                                    WHERE chat_id = {chat_id}")
                    if cursor.fetchone():
                        text = "Данный телеграм уже привязан."
                    else:
                        cursor.execute(f"UPDATE users \
                            SET chat_id = '{chat_id}', telegram_auth = 'True'\
                            WHERE telegram_register_key = '{key}'")
                        cursor.execute(f"SELECT username FROM users\
                                        WHERE telegram_register_key = '{key}'")
                        text = f"Телеграм успешно привязан к учетной записи {cursor.fetchone()[0]}"
                        cursor.execute(f"UPDATE users \
                            SET telegram_register_key = NULL\
                            WHERE telegram_register_key = '{key}'")
                else:
                    text = "Неправильный код"
            send_message(chat_id, text)

    return {"ok": True}


@app.route("/", methods=["get"])
def homepage():
    if "login" not in session:
        return redirect(url_for("login"))

    user = session["username"]

    return render_template("index.html", user=user)


@app.route('/login/', methods=['post', 'get'])
def login():
    if "login" in session:
        return redirect(url_for("homepage"))
    message = ''
    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']
        password_hash = password_hash_generate(password)
        with sqlite3.connect(DATABASE) as con:
            cursor = con.cursor()
            cursor.execute(f"SELECT * FROM users\
                             WHERE username = '{username}' \
                             AND password = '{password_hash}'")
            result = cursor.fetchone()
            if result is not None:
                print(result[-1])
                # session["login"] = result[-1]
                session["username"] = result[1]
                if result[-3] == "True":
                    return redirect(url_for("auth"))
                else:
                    session["login"] = result[-1]
                return redirect(url_for("homepage"))
            else:
                message = "Неправильный логин или пароль!!!"

    return render_template("login.html", message=message)


@app.route("/register/", methods=["post", "get"])
def register():
    if "login" in session:
        return redirect(url_for("homepage"))
    message = ''
    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']
        confirm = request.form['confirm']
        if password != confirm:
            message = "Пароли не совпадают!!!"
        else:
            password_hash = password_hash_generate(password)
            session_key = session_hash_generate(username, password)
            with sqlite3.connect(DATABASE) as con:
                cursor = con.cursor()
                cursor.execute(f"SELECT username FROM users \
                                WHERE username = '{username}'")
                if cursor.fetchone() is None:
                    cursor.execute("INSERT INTO \
                                    users(username, password, session_key) \
                                    VALUES (?, ?, ?)",
                                   (username, password_hash, session_key))
                    con.commit()
                    message = "Пользователь успешно создан!"
                else:
                    message = "Пользователь с таким именем существует..."

    return render_template("register.html", message=message)


@app.route('/close_session/')
def close_session():
    session.pop("username", None)
    session.pop("login", None)
    return redirect(url_for("login"))


@app.route("/settings/")
def settings():
    telegram_auth = False
    with sqlite3.connect(DATABASE) as con:
        cursor = con.cursor()
        cursor.execute(f"SELECT chat_id \
                        FROM users \
                        WHERE username = '{session['username']}'")
        if cursor.fetchone()[0]:
            telegram_auth = True
    print(telegram_auth)
    return render_template("settings.html", telegram_auth=telegram_auth)


@app.route("/set_auth/")
def set_auth():
    if "login" not in session:
        return redirect(url_for("login"))

    telegram_key = ""
    with sqlite3.connect(DATABASE) as con:
        cursor = con.cursor()
        cursor.execute(f"SELECT chat_id \
                        FROM users WHERE username = '{session['username']}'")
        if not cursor.fetchone()[0]:
            while True:
                telegram_key = key_generate()
                cursor.execute(f"SELECT * FROM users \
                                WHERE telegram_register_key \
                                = '{telegram_key}'")
                if not cursor.fetchone():
                    break
            cursor.execute(f"UPDATE users \
                        SET telegram_register_key = '{telegram_key}'\
                        WHERE username = '{session['username']}'")
        else:
            return redirect(url_for('settings'))

    return render_template("set_auth.html", key=telegram_key)


@app.route("/auth/", methods=["post", "get"])
def auth():
    if "login" in session:
        return redirect(url_for("homepage"))

    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        input_key = request.form["authcode"].upper()
        with sqlite3.connect(DATABASE) as con:
            cursor = con.cursor()
            cursor.execute(f"SELECT auth_code FROM users \
                            WHERE username = '{session['username']}'")
        key = cursor.fetchone()[0]
        if input_key == key:
            session["login"] = ""
            with sqlite3.connect(DATABASE) as con:
                cursor = con.cursor()
                cursor.execute(f"SELECT session_key FROM users \
                                WHERE username = '{session['username']}'")
                session["login"] = cursor.fetchone()[0]
            return redirect(url_for("homepage"))
        else:
            session.pop("username", None)
            return redirect(url_for("error_auth"))

    key = key_generate()

    with sqlite3.connect(DATABASE) as con:
        cursor = con.cursor()
        cursor.execute(f"UPDATE users \
                        SET auth_code = '{key}'\
                        WHERE username = '{session['username']}'")

    chat_id = ""

    with sqlite3.connect(DATABASE) as con:
        cursor = con.cursor()
        cursor.execute(f"SELECT chat_id FROM users \
                        WHERE username = '{session['username']}'")
        chat_id = cursor.fetchone()[0]

    send_message(chat_id, f"Auth code: {key}")

    return render_template("auth.html")


@app.route("/error_auth/")
def error_auth():
    return render_template("error_auth.html")


@app.route("/reset_database/")
def reset():
    with sqlite3.connect(DATABASE) as con:
        cursor = con.cursor()
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
        con.commit()

    return redirect(url_for("close_session"))


@app.route("/about/")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run()
