# Smart Copy Checking

A small Django web app for school copy-checking and teacher course-progress tracking.

This version is ready for:

- Local Windows testing with SQLite
- Local network testing on the same Wi-Fi
- Online deployment with Render + Neon PostgreSQL

## Main modules

### Copy Checking

- Checker login
- Class → Subject → Chapter selection
- Student list for selected class/chapter
- Locked copy-checking records
- Correction requests with requested new values
- Admin review can approve and apply values automatically
- Attention List for neglected class-subjects and students

### Teacher Progress

- Teacher login
- Teacher dashboard with assigned courses
- Admin assigns one active teacher to each class-subject
- Teacher opens a course and adds rows with automatic **Week No** values
- New rows start as **Not Completed**
- Not Completed rows can be edited or deleted by the teacher
- Completed rows are locked and cannot be edited/deleted by the teacher
- No teacher-side correction request button
- Admin can still edit a teacher progress row if correction is needed
- Admin can view progress class-wise or teacher-wise

### Admin highlights

- Pending copy correction requests are shown with a star and highlighted button.
- Admin does not need to open the correction page to know if requests are pending.

## Initial users

Run the seed command to create missing users:

Passwords are stored by Django as secure hashes for login. The app also keeps an admin-visible password note because that was requested for school account management.

Important: `seed_initial_users` now creates missing initial users only. It does not overwrite existing user passwords on redeploy. To intentionally reset them, run:

```bat
python manage.py seed_initial_users --reset-passwords
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
2. Create classes with subjects and chapter counts.
3. Add/import students.
4. Add users if needed: checker or teacher.
5. Assign teacher courses from **Teacher Assignments**.
6. Checkers can start copy-checking.
7. Teachers can start course-progress entry.

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

Upload this project folder to a GitHub repository.

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
./build.sh

Start Command:
gunicorn smart_copy_checking.wsgi:application
```

### 4. Add Render environment variables

Add these in Render:

```text
DEBUG=False
SECRET_KEY=<generate a long random secret>
DATABASE_URL=<your Neon connection string>
ALLOWED_HOSTS=.onrender.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://YOUR-RENDER-SERVICE-NAME.onrender.com
```

After the first deploy, replace `YOUR-RENDER-SERVICE-NAME` with the real Render URL.

### 5. First deploy

During build, Render will run:

```text
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py seed_initial_users
```

The seed command is safe on redeploy because it will not reset existing passwords unless `--reset-passwords` is used.

## Backup rule

The app creates/updates one JSON backup file per active day after successful important changes, including:

- copy-checking lock
- copy correction approval
- class setup change
- student add/import
- user create/reset/edit
- teacher assignment change
- teacher progress add/edit/delete/complete
- admin teacher-progress edit

Only active days create backups. The app keeps the latest 10 active-day backups.

### Important online backup note

On local Windows, backup files are saved in the project folder.

On Render free hosting, files inside the app folder should not be treated as permanent storage. For online use, the admin should open **Backups** and click **Create & Download Backup Now** regularly.

The actual live data is stored in Neon PostgreSQL. The backup download is an extra school-side copy.
