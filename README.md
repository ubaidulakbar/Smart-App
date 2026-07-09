# Smart Copy Checking

A small Django web app for school copy-checking and teacher course-progress tracking.

This version is ready for:

- Local Windows testing with SQLite
- Local network testing on the same Wi-Fi
- Online deployment with Render + Neon PostgreSQL

## Main modules

### Admin

The admin dashboard is split into three areas:

- **School Setup**: classes, subjects, students, imports, users, teacher assignments, backups, and delete data.
- **Copy Checking**: checking records, attention lists, student profiles, recent records, and Excel exports.
- **Teaching Progress**: issue new week rows, teacher progress by class, teacher progress by teacher, and Excel export.

### Copy Checking

- Checker login
- Class-wise attention list
- Flexible checking entries instead of chapter-wise checking
- Checker selects a class, then adds one or more rows with student, subject, status, and details
- Status options: Complete / Incomplete
- Complete is selected by default
- Details are required only for Incomplete rows
- Batch save is all-or-nothing: if one row has an error, no rows are saved
- Saved checking records are locked and cannot be edited by checkers
- If a mistake happens, enter a new checking row instead of editing the old one
- Admin can view/filter/export records to Excel

### Teacher Progress

- Teacher login
- Teacher dashboard with assigned course cards
- Admin assigns one active teacher to each class-subject
- Admin issues new week rows from Teaching Progress → Issue New Week
- Issue New Week uses each teacher-course assignment's own next week number
- Example: if one course has Week 1 only, the next issued row is Week 2; if another course has no rows, the next issued row is Week 1
- Teachers cannot create or delete week rows
- Teachers only enter detail and mark pending rows as Completed
- Detail is required before completing a week
- Completed rows are locked
- Admin can edit teacher progress rows if needed

## Initial user

Run the seed command to create the first admin account only when the database has no users:

```text
username: admin
password: {SmartChecking2026}
```

Use the braces exactly as written.

The seed command does not recreate deleted users and does not overwrite passwords when users already exist.

To reset only the admin password intentionally:

```bat
python manage.py seed_initial_users --reset-admin-password
```

## Fresh setup on Windows

```bat
cd smart_copy_checking
py -m venv venv
venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_initial_users
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## Local network testing

Run:

```bat
python manage.py runserver 0.0.0.0:8000
```

Find your PC IP:

```bat
ipconfig
```

Checkers and teachers on the same Wi-Fi can open:

```text
http://YOUR-PC-IP:8000/
```

Example:

```text
http://192.168.1.10:8000/
```

If phones cannot open it, allow Python/Django through Windows Firewall or allow port `8000` on the local network.

## Admin setup order

1. Login as admin.
2. Open **School Setup**.
3. Create classes and assign subjects.
4. Add/import students.
5. Create checker and teacher users if needed.
6. Assign teachers to class-subjects from **Teacher Assignments**.
7. Use **Teaching Progress → Issue New Week** to issue week rows.
8. Checkers can start copy-checking.
9. Teachers can complete issued week rows.

## Student import format

Upload `.xlsx` file.

- Column A = Student Name
- Column B = Roll No
- No header required
- The first row is treated as data
- Preview appears before final import
- Duplicate/problem rows are shown and left for manual entry

## Render + Neon deployment

Use Render for the Django web app and Neon for the PostgreSQL database.

### 1. Create Neon database

Create a Neon project and copy the PostgreSQL connection string. It should look similar to:

```text
postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

### 2. Upload project to GitHub

Upload this project folder to a GitHub repository. Do not upload `venv`, `db.sqlite3`, or local backup files.

### 3. Create Render Web Service

On Render, create a new Web Service from the GitHub repository.

The included files are already prepared:

- `requirements.txt`
- `Procfile`
- `build.sh`
- `render.yaml`
- `.env.example`

Suggested Render settings:

```text
Build Command:
bash build.sh

Start Command:
gunicorn smart_copy_checking.wsgi:application
```

### 4. Add Render environment variables

```text
DEBUG=False
SECRET_KEY=your-long-random-secret-key
ALLOWED_HOSTS=.onrender.com,localhost,127.0.0.1
DATABASE_URL=your-neon-postgresql-url
PYTHON_VERSION=3.13.4
```

After deploy, open the Render URL and login with the admin account.

## Backups

The app supports app-level JSON backups from the Backups page.

- Backups can be created manually
- Backups are also triggered after important actions
- Admin can download backup files
- Admin can upload/restore a backup file from the same backup format

For dangerous deletes, create/download a backup first.
