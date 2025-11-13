## PrivateInk — Мини-блог на Flask

Полноценное веб‑приложение «Блог с авторизацией» на Flask + SQLite, с поддержкой Markdown, пагинацией, личным кабинетом и темной/светлой темой.

### Возможности
- Регистрация и вход (хэширование паролей, защита от дубликатов логина/email)
- Сессии через Flask `session`, защита приватных маршрутов
- Посты: создание, редактирование и удаление только своими авторами
- Markdown → безопасный HTML (Markdown + Bleach)
- Главная лента с пагинацией по 5 постов (`/page/2` и т. д.)
- Личный кабинет `/profile`
- Чистые HTML/CSS/JS, адаптивная верстка, переключатель темы (localStorage)

### Быстрый старт
1. Установите Python 3.10+
2. Создайте и активируйте виртуальное окружение (рекомендуется):
   - Windows PowerShell:
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   - macOS/Linux:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
3. Установите зависимости:
   ```bash
   pip install flask markdown bleach werkzeug
   ```
4. Запуск (создаст `blog.db` при первом старте):
   ```bash
   python app.py
   ```
   Приложение будет доступно на `http://127.0.0.1:5000`.

Альтернативно, можно инициализировать базу вручную:
```bash
flask --app app init-db
```

### Переменные окружения
- `SECRET_KEY` — ключ для подписи сессии (по умолчанию dev-ключ). Рекомендуется переопределить в проде:
  ```powershell
  $env:SECRET_KEY = "your-strong-secret"
  python app.py
  ```

### Структура
```
app.py
templates/
  base.html
  index.html
  login.html
  register.html
  profile.html
  create.html
  edit.html
static/
  style.css
  script.js
blog.db (создаётся автоматически)
```

### Заметки по безопасности
- Используются параметризованные SQL‑запросы (`sqlite3`)
- Пароли хранятся в виде хеша (`generate_password_hash`/`check_password_hash`)
- HTML из Markdown очищается через `bleach.clean`, ссылки — `bleach.linkify`

### Лицензия
MIT

# PrivateInk
A secure, self-hosted blog with user authentication — built with Flask and SQLite.

Made by Viktoriya Gonchar
