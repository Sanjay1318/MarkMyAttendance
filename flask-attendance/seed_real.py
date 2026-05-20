"""
seed_real.py
============
Generates a realistic small-scale institute dataset:
  - 1 Admin
  - 3 Academic years / 6 session-terms
  - 8 Classes  (Grade 1 – Grade 8, i.e. Primary school)
  - 16 Arms    (2 per class: A & B)
  - 16 Teachers (one per arm)
  - 210 Students spread across all classes
  - 60 days of attendance history per student (realistic 78–98 % rates)

Run:
    python seed_real.py            # uses SQLite (no MySQL needed)
    python seed_real.py --mysql    # reads .env and uses MySQL
"""

import os, random, sys
from datetime import date, timedelta

# ── allow --mysql flag ──────────────────────────────────────────
USE_MYSQL = '--mysql' in sys.argv

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── minimal Flask app just for db context ──────────────────────
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = 'seed-script-secret'

if USE_MYSQL:
    h  = os.environ.get('DB_HOST',     'localhost')
    p  = os.environ.get('DB_PORT',     '3306')
    u  = os.environ.get('DB_USER',     'root')
    pw = os.environ.get('DB_PASSWORD', '')
    n  = os.environ.get('DB_NAME',     'attendance_db')
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"mysql+pymysql://{u}:{pw}@{h}:{p}/{n}?charset=utf8mb4"
    )
    print(f"[seed] Using MySQL → {h}:{p}/{n}")
else:
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'attendance.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    print(f"[seed] Using SQLite → {db_path}")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ── Models (must match app.py) ──────────────────────────────────
class Admin(db.Model):
    __tablename__ = 'tbladmin'
    Id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    firstName    = db.Column(db.String(50),  nullable=False)
    lastName     = db.Column(db.String(50),  nullable=False)
    emailAddress = db.Column(db.String(100), nullable=False, unique=True)
    password     = db.Column(db.String(255), nullable=False)

class Class(db.Model):
    __tablename__ = 'tblclass'
    Id        = db.Column(db.Integer, primary_key=True, autoincrement=True)
    className = db.Column(db.String(255), nullable=False)

class ClassArm(db.Model):
    __tablename__ = 'tblclassarms'
    Id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    classId      = db.Column(db.String(10),  nullable=False)
    classArmName = db.Column(db.String(255), nullable=False)
    isAssigned   = db.Column(db.String(10),  nullable=False, default='0')

class ClassTeacher(db.Model):
    __tablename__ = 'tblclassteacher'
    Id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    firstName    = db.Column(db.String(255), nullable=False)
    lastName     = db.Column(db.String(255), nullable=False)
    emailAddress = db.Column(db.String(255), nullable=False, unique=True)
    password     = db.Column(db.String(255), nullable=False)
    phoneNo      = db.Column(db.String(50),  nullable=False)
    classId      = db.Column(db.String(10),  nullable=False)
    classArmId   = db.Column(db.String(10),  nullable=False)
    dateCreated  = db.Column(db.String(50),  nullable=False)

class Term(db.Model):
    __tablename__ = 'tblterm'
    Id       = db.Column(db.Integer, primary_key=True, autoincrement=True)
    termName = db.Column(db.String(20), nullable=False)

class SessionTerm(db.Model):
    __tablename__ = 'tblsessionterm'
    Id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sessionName = db.Column(db.String(50), nullable=False)
    termId      = db.Column(db.String(50), nullable=False)
    isActive    = db.Column(db.String(10), nullable=False, default='0')
    dateCreated = db.Column(db.String(50), nullable=False)

class Student(db.Model):
    __tablename__ = 'tblstudents'
    Id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    firstName       = db.Column(db.String(255), nullable=False)
    lastName        = db.Column(db.String(255), nullable=False)
    otherName       = db.Column(db.String(255), nullable=False, default='')
    admissionNumber = db.Column(db.String(255), nullable=False, unique=True)
    password        = db.Column(db.String(255), nullable=False, default='12345')
    classId         = db.Column(db.String(10),  nullable=False)
    classArmId      = db.Column(db.String(10),  nullable=False)
    dateCreated     = db.Column(db.String(50),  nullable=False)

class Attendance(db.Model):
    __tablename__ = 'tblattendance'
    Id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    admissionNo   = db.Column(db.String(255), nullable=False)
    classId       = db.Column(db.String(10),  nullable=False)
    classArmId    = db.Column(db.String(10),  nullable=False)
    sessionTermId = db.Column(db.String(10),  nullable=False)
    status        = db.Column(db.String(10),  nullable=False, default='0')
    dateTimeTaken = db.Column(db.String(20),  nullable=False)

# ── helpers ─────────────────────────────────────────────────────
def hash_password(text):
    return generate_password_hash(text)

def school_days(start: date, end: date):
    """Return list of weekday date strings between start and end (no weekends)."""
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:   # Mon–Fri
            days.append(str(d))
        d += timedelta(days=1)
    return days

# ── realistic data pools ────────────────────────────────────────
FIRST_NAMES_M = [
    'Arjun','Rahul','Kiran','Vikram','Suresh','Ravi','Anil','Deepak','Manoj',
    'Sanjay','Ajay','Vijay','Nikhil','Rohit','Amit','Pradeep','Rajesh','Naveen',
    'Harish','Sunil','Praveen','Ganesh','Krishna','Ramesh','Dinesh','Girish',
    'Santosh','Lokesh','Mahesh','Naresh','Umesh','Rakesh','Hitesh','Jitesh',
    'Nilesh','Kamlesh','Suresh','Brijesh','Yogesh','Mukesh','Vikas','Sachin',
    'Gaurav','Varun','Tushar','Rohan','Akash','Nitin','Pankaj','Vivek',
]
FIRST_NAMES_F = [
    'Priya','Anita','Sunita','Kavitha','Deepa','Meena','Lakshmi','Radha',
    'Sita','Geeta','Rekha','Usha','Asha','Latha','Padma','Vimala','Sarala',
    'Kamala','Indira','Savitha','Bhavana','Swathi','Sneha','Divya','Pooja',
    'Ritu','Neha','Ankita','Shruti','Aarti','Kinjal','Foram','Hiral','Nisha',
    'Priyanka','Shweta','Sonali','Manasi','Rutuja','Gauri','Tejal','Komal',
    'Pallavi','Rashmi','Madhuri','Archana','Vandana','Sonal','Juhi','Richa',
]
LAST_NAMES = [
    'Sharma','Verma','Singh','Kumar','Patel','Shah','Joshi','Mehta','Gupta',
    'Nair','Pillai','Menon','Reddy','Rao','Naidu','Iyer','Agarwal','Mishra',
    'Pandey','Srivastava','Tiwari','Dubey','Chauhan','Yadav','Saxena','Bose',
    'Chatterjee','Mukherjee','Das','Ghosh','Roy','Banerjee','Dey','Saha',
    'Malhotra','Kapoor','Khanna','Chopra','Sood','Sethi','Anand','Chawla',
    'Bhatia','Arora','Grover','Luthra','Kohli','Walia','Bhatt','Trivedi',
]
TEACHER_FIRST = [
    'Rajendra','Subramaniam','Padmavathi','Lakshminarayan','Venkataraman',
    'Saraswathi','Chandrasekar','Bhagyalakshmi','Venkateswara','Meenakshi',
    'Narasimhan','Vijayalakshmi','Krishnamurthy','Parameswari','Raghunathan',
    'Soundarya','Thirumurthy','Kamakshi','Balasubramanian','Shanthi',
]
TEACHER_LAST = [
    'Iyer','Pillai','Nair','Menon','Krishnan','Varma','Rajan','Suresh',
    'Ramachandran','Natarajan','Sundaram','Muthukrishnan','Annamalai','Subramanian',
    'Venkatesan','Ramaswamy','Govindasamy','Thiruvenkatam','Parthasarathy','Seshadri',
]

random.seed(42)  # reproducible

def rand_phone():
    return f"9{random.randint(100000000,999999999)}"

def rand_name_m():
    return random.choice(FIRST_NAMES_M), random.choice(LAST_NAMES)

def rand_name_f():
    return random.choice(FIRST_NAMES_F), random.choice(LAST_NAMES)

def rand_name():
    return rand_name_m() if random.random() < 0.55 else rand_name_f()

# ── Institute structure ─────────────────────────────────────────
#  Greenfield Public School
#  Grades 1–8, two sections (A & B) each
#  ~14 students per section  →  ~224 students total

CLASSES = [
    'Grade 1', 'Grade 2', 'Grade 3', 'Grade 4',
    'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8',
]
ARMS = ['A', 'B']           # two sections per grade
STUDENTS_PER_ARM = 14       # 14 × 2 × 8 = 224 students

SESSIONS = [
    ('2022/2023', '1', '0'),
    ('2022/2023', '2', '0'),
    ('2022/2023', '3', '0'),
    ('2023/2024', '1', '0'),
    ('2023/2024', '2', '0'),
    ('2024/2025', '1', '1'),   # ← ACTIVE
]

# Date ranges for past attendance (school-day only)
SESSION_DATE_RANGES = {
    '2022/2023-1': (date(2022, 6, 13), date(2022, 10, 7)),
    '2022/2023-2': (date(2022, 10, 24), date(2023, 2, 17)),
    '2022/2023-3': (date(2023, 2, 27), date(2023, 4, 28)),
    '2023/2024-1': (date(2023, 6, 12), date(2023, 10, 6)),
    '2023/2024-2': (date(2023, 10, 23), date(2024, 2, 16)),
    '2024/2025-1': (date(2024, 6, 10), date(2024, 9, 30)),
}
# Only seed the last 60 school days of each past session (keeps DB manageable)
MAX_DAYS_PER_SESSION = 60


def run():
    with app.app_context():
        print("[seed] Creating tables...")
        db.create_all()

        # ── Wipe existing data ──────────────────────────────────
        print("[seed] Clearing existing data...")
        Attendance.query.delete()
        Student.query.delete()
        ClassTeacher.query.delete()
        ClassArm.query.delete()
        Class.query.delete()
        SessionTerm.query.delete()
        Term.query.delete()
        Admin.query.delete()
        db.session.commit()

        today_str = str(date.today())

        # ── Admin ───────────────────────────────────────────────
        print("[seed] Creating admin...")
        db.session.add(Admin(
            firstName='Principal', lastName='Admin',
            emailAddress='admin@greenfieldschool.in',
            password=hash_password('admin123')
        ))
        db.session.flush()

        # ── Terms ───────────────────────────────────────────────
        t1 = Term(termName='First');  db.session.add(t1)
        t2 = Term(termName='Second'); db.session.add(t2)
        t3 = Term(termName='Third');  db.session.add(t3)
        db.session.flush()
        term_id_map = {'1': str(t1.Id), '2': str(t2.Id), '3': str(t3.Id)}

        # ── Sessions ─────────────────────────────────────────────
        print("[seed] Creating sessions...")
        session_objs = {}
        for sname, tid_str, is_active in SESSIONS:
            s = SessionTerm(sessionName=sname, termId=term_id_map[tid_str],
                            isActive=is_active, dateCreated=today_str)
            db.session.add(s)
            db.session.flush()
            key = f"{sname}-{tid_str}"
            session_objs[key] = s
        db.session.flush()

        active_session = next(s for s in session_objs.values() if s.isActive == '1')

        # ── Classes + Arms + Teachers ────────────────────────────
        print("[seed] Creating classes, arms, teachers...")
        teacher_pool = list(zip(TEACHER_FIRST, TEACHER_LAST))
        random.shuffle(teacher_pool)
        teacher_idx = 0
        teacher_pwd = hash_password('teacher123')

        class_map = {}   # className -> Class obj
        arm_map   = {}   # (classId, armName) -> ClassArm obj

        for cls_name in CLASSES:
            cls_obj = Class(className=cls_name)
            db.session.add(cls_obj)
            db.session.flush()
            class_map[cls_name] = cls_obj

            for arm_name in ARMS:
                arm_obj = ClassArm(classId=str(cls_obj.Id),
                                   classArmName=arm_name, isAssigned='1')
                db.session.add(arm_obj)
                db.session.flush()
                arm_map[(str(cls_obj.Id), arm_name)] = arm_obj

                # one teacher per arm
                tf, tl = teacher_pool[teacher_idx % len(teacher_pool)]
                teacher_idx += 1
                grade_num  = CLASSES.index(cls_name) + 1
                t_email    = f"teacher.g{grade_num}{arm_name.lower()}@greenfieldschool.in"
                db.session.add(ClassTeacher(
                    firstName=tf, lastName=tl,
                    emailAddress=t_email,
                    password=teacher_pwd,
                    phoneNo=rand_phone(),
                    classId=str(cls_obj.Id),
                    classArmId=str(arm_obj.Id),
                    dateCreated=today_str,
                ))
        db.session.flush()

        # ── Students ─────────────────────────────────────────────
        print("[seed] Creating 224 students...")
        adm_counter = 1001
        student_objs = []   # list of (Student, classId_str, armId_str)

        for cls_name in CLASSES:
            cls_obj  = class_map[cls_name]
            grade_num = CLASSES.index(cls_name) + 1
            for arm_name in ARMS:
                arm_obj = arm_map[(str(cls_obj.Id), arm_name)]
                for _ in range(STUDENTS_PER_ARM):
                    fn, ln = rand_name()
                    adm_no = f"GFS{adm_counter:04d}"
                    adm_counter += 1
                    enrolled = str(date(2022, 6, 1) + timedelta(days=random.randint(0, 60)))
                    s = Student(
                        firstName=fn, lastName=ln, otherName='',
                        admissionNumber=adm_no,
                        password=hash_password('12345'),
                        classId=str(cls_obj.Id),
                        classArmId=str(arm_obj.Id),
                        dateCreated=enrolled,
                    )
                    db.session.add(s)
                    db.session.flush()
                    student_objs.append((s, str(cls_obj.Id), str(arm_obj.Id)))

        db.session.commit()
        print(f"[seed] Created {len(student_objs)} students")

        # ── Attendance history ────────────────────────────────────
        print("[seed] Generating attendance history (this takes ~30s)...")
        att_batch = []
        BATCH_SIZE = 2000

        def flush_batch():
            if att_batch:
                db.session.bulk_insert_mappings(Attendance, att_batch)
                db.session.commit()
                att_batch.clear()

        for sess_key, sess_obj in session_objs.items():
            if sess_obj.isActive == '1':
                # Active session: only seed up to yesterday so teachers can "take today"
                date_range = SESSION_DATE_RANGES.get(sess_key)
                if not date_range:
                    continue
                days = school_days(date_range[0], date_range[1])
                days = [d for d in days if d < today_str]
            else:
                date_range = SESSION_DATE_RANGES.get(sess_key)
                if not date_range:
                    continue
                days = school_days(date_range[0], date_range[1])

            # Limit to last MAX_DAYS_PER_SESSION days per session
            days = days[-MAX_DAYS_PER_SESSION:]

            for s, cid, aid in student_objs:
                # Each student has an individual attendance rate 72%–98%
                rate = random.uniform(0.72, 0.98)
                for d in days:
                    status = '1' if random.random() < rate else '0'
                    att_batch.append({
                        'admissionNo':   s.admissionNumber,
                        'classId':       cid,
                        'classArmId':    aid,
                        'sessionTermId': str(sess_obj.Id),
                        'status':        status,
                        'dateTimeTaken': d,
                    })
                    if len(att_batch) >= BATCH_SIZE:
                        flush_batch()
                        print(f"  ...flushed {BATCH_SIZE} attendance rows")

        flush_batch()

        # ── Summary ───────────────────────────────────────────────
        print("\n✅  Seed complete!")
        print(f"   Students  : {Student.query.count()}")
        print(f"   Teachers  : {ClassTeacher.query.count()}")
        print(f"   Classes   : {Class.query.count()}")
        print(f"   Arms      : {ClassArm.query.count()}")
        print(f"   Sessions  : {SessionTerm.query.count()}")
        print(f"   Attendance: {Attendance.query.count()} rows")
        print()
        print("── LOGIN CREDENTIALS ──────────────────────────────")
        print("  Admin   : admin@greenfieldschool.in  /  admin123")
        print("  Teachers: teacher.g1a@greenfieldschool.in  /  teacher123")
        print("            teacher.g1b@greenfieldschool.in  /  teacher123")
        print("            ... (g1a–g8b, 16 teachers total)")
        print("  Students: GFS1001 – GFS1224  /  12345")
        print("───────────────────────────────────────────────────")


if __name__ == '__main__':
    run()
