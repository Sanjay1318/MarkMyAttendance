# Student Attendance Management System

A Flask-based Student Attendance Management System with separate Admin, Teacher, and Student portals. It supports class and section management, teacher assignment, student records, daily attendance, attendance reports, dashboards, password changes, and CSV exports.

The app is built to run locally with SQLite by default and can be configured for MySQL in production.

## Features

### Admin Portal

- Admin login and role-protected dashboard
- Manage classes and class arms/sections
- Manage academic sessions and active terms
- Manage teachers and class assignments
- Manage students
- View attendance reports by date range, class, and arm
- Export attendance reports as CSV
- Change admin password

### Teacher Portal

- Teacher login and role-protected dashboard
- View assigned class and arm
- Take daily attendance
- Reset and correct same-day attendance
- View attendance by date
- View student attendance percentages
- Export class attendance as CSV
- Change teacher password

### Student Portal

- Student login using admission number and password
- View attendance dashboard
- View full attendance history
- Filter attendance by session/term
- View profile information
- Export own attendance as CSV
- Change student password

## Security Notes

- Forms are protected with CSRF using Flask-WTF.
- Passwords are hashed using Werkzeug security helpers.
- Older plain, MD5, and legacy PBKDF2 passwords are still accepted for compatibility and are upgraded after successful login.
- Admin delete and activation actions use POST requests with CSRF protection.
- Session cookies use `HttpOnly` and `SameSite=Lax`.
- Keep `.env`, SQLite databases, and the `instance/` folder out of Git.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend | Python, Flask |
| ORM | Flask-SQLAlchemy |
| Database | SQLite for local development, MySQL for production |
| Forms / CSRF | Flask-WTF |
| MySQL Driver | PyMySQL |
| Frontend | HTML, CSS, Bootstrap, JavaScript |
| Charts / Tables | Chart.js, DataTables |
| Config | python-dotenv |

## Project Structure

```text
flask-attendance/
|-- app.py
|-- requirements.txt
|-- .env.example
|-- .gitignore
|-- MYSQL_SETUP.md
|-- seed_real.py
|-- attendance_db.sql
|-- static/
|   `-- css/
|       `-- style.css
`-- templates/
    |-- base.html
    |-- macros.html
    |-- landing.html
    |-- admin_*.html
    |-- teacher_*.html
    |-- student_*.html
    `-- errors/
        |-- 403.html
        |-- 404.html
        `-- 500.html
```

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/your-repository-name.git
cd your-repository-name/flask-attendance
```

If your repository root is already `flask-attendance`, just run:

```bash
cd flask-attendance
```

### 2. Create and activate a virtual environment

Windows:

```powershell
python -m venv venv
.\venv\Scripts\activate
```

macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your environment file

Copy `.env.example` to `.env`.

Windows:

```powershell
copy .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

Update `.env`:

```env
SECRET_KEY=replace-this-with-a-long-random-secret

DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=attendance_db

FLASK_DEBUG=1
```

For local SQLite development, leave `DB_PASSWORD` blank. If `DB_PASSWORD` is set, the app will try to connect to MySQL.

### 5. Run the app

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

On first run, the app creates the database tables and seeds demo data.

## Demo Credentials

### Admin

| Email | Password |
| --- | --- |
| `admin@mail.com` | `admin123` |

### Teachers

| Email | Password | Class | Arm |
| --- | --- | --- | --- |
| `teacher@mail.com` | `teacher123` | Nine | N1 |
| `teacher2@mail.com` | `teacher123` | Seven | S1 |
| `teacher3@gmail.com` | `teacher123` | Seven | S2 |
| `teacher4@mail.com` | `teacher123` | Eight | E1 |

### Students

| Admission Number | Password | Class |
| --- | --- | --- |
| `AMS005` | `12345` | Seven / S1 |
| `AMS019` | `12345` | Eight / E1 |
| `AMS110` | `12345` | Nine / N1 |

New students created by the admin receive the default password `12345`. Students should change it after first login.

## MySQL Setup

SQLite is enough for local development. For MySQL, create a database first:

```sql
CREATE DATABASE attendance_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Then update `.env`:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=attendance_db
```

Run the app again:

```bash
python app.py
```

## Realistic Seed Data

The project includes `seed_real.py` for generating a larger demo dataset.

SQLite:

```bash
python seed_real.py
```

MySQL:

```bash
python seed_real.py --mysql
```

This script clears existing data before seeding, so use it only for development or demos.

## Deployment

Before deploying:

- Set `FLASK_DEBUG=0`.
- Set a strong unique `SECRET_KEY`.
- Use MySQL or another production database instead of the local SQLite file.
- Do not commit `.env`, `instance/`, database files, or virtual environments.
- Change demo credentials after deployment.

Example production environment:

```env
SECRET_KEY=your-long-random-production-secret
FLASK_DEBUG=0

DB_HOST=your-db-host
DB_PORT=3306
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_NAME=attendance_db
```

Run with Flask for a simple internal deployment:

```bash
python app.py
```

For a Linux server, you can run the app behind a production WSGI server such as Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

Then place Nginx, Apache, or your hosting provider's reverse proxy in front of it.

## GitHub Checklist

Before pushing this project to GitHub:

- Confirm `.env` is not committed.
- Confirm database files are not committed.
- Confirm `venv/` is not committed.
- Keep `.env.example` committed so others know what variables are needed.
- Add screenshots to a `screenshots/` folder if you want a more visual README.
- Replace the clone URL in this README with your real repository URL.

Recommended commands:

```bash
git init
git add .
git status
git commit -m "Initial Flask attendance system"
git branch -M main
git remote add origin https://github.com/your-username/your-repository-name.git
git push -u origin main
```

## Common Commands

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python app.py
```

Check Python syntax:

```bash
python -m py_compile app.py seed_real.py
```

## Requirements

```text
flask>=2.3.0
flask-sqlalchemy>=3.1.0
flask-wtf>=1.2.0
pymysql>=1.1.0
cryptography>=41.0.0
python-dotenv>=1.0.0
```

## License

This project is open for learning, customization, and deployment. Add your preferred license file before publishing if needed.
