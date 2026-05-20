"""
Student Attendance Management System
Flask + SQLAlchemy + MySQL (fallback SQLite for dev)
"""

import csv
import hashlib
import io
import logging
import os
from datetime import date, timedelta
from functools import wraps

from flask import (Flask, Response, flash, jsonify, redirect,
                   render_template, request, session, url_for)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

# ── load .env if present ──
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────── APP CONFIG ───────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    app.secret_key = 'dev-only-change-me'
    logging.warning('SECRET_KEY is not set. Using a development-only fallback secret.')

# MySQL URI from env, fallback to SQLite for local dev without MySQL
_db_host = os.environ.get('DB_HOST', 'localhost')
_db_port = os.environ.get('DB_PORT', '3306')
_db_user = os.environ.get('DB_USER', 'root')
_db_pass = os.environ.get('DB_PASSWORD', '')
_db_name = os.environ.get('DB_NAME', 'attendance_db')
_use_mysql = all([_db_host, _db_user, _db_name, os.environ.get('DB_PASSWORD') is not None and os.environ.get('DB_PASSWORD', '') != '']) \
             and os.environ.get('DB_PASSWORD', '') != ''

if _use_mysql:
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"mysql+pymysql://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}"
        "?charset=utf8mb4"
    )
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# ─────────────────────────── MODELS ───────────────────────────

class Admin(db.Model):
    __tablename__ = 'tbladmin'
    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    firstName = db.Column(db.String(50), nullable=False)
    lastName = db.Column(db.String(50), nullable=False)
    emailAddress = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)

class Class(db.Model):
    __tablename__ = 'tblclass'
    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    className = db.Column(db.String(255), nullable=False)

class ClassArm(db.Model):
    __tablename__ = 'tblclassarms'
    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    classId = db.Column(db.String(10), nullable=False)
    classArmName = db.Column(db.String(255), nullable=False)
    isAssigned = db.Column(db.String(10), nullable=False, default='0')

class ClassTeacher(db.Model):
    __tablename__ = 'tblclassteacher'
    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    firstName = db.Column(db.String(255), nullable=False)
    lastName = db.Column(db.String(255), nullable=False)
    emailAddress = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    phoneNo = db.Column(db.String(50), nullable=False)
    classId = db.Column(db.String(10), nullable=False)
    classArmId = db.Column(db.String(10), nullable=False)
    dateCreated = db.Column(db.String(50), nullable=False)

class Term(db.Model):
    __tablename__ = 'tblterm'
    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    termName = db.Column(db.String(20), nullable=False)

class SessionTerm(db.Model):
    __tablename__ = 'tblsessionterm'
    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sessionName = db.Column(db.String(50), nullable=False)
    termId = db.Column(db.String(50), nullable=False)
    isActive = db.Column(db.String(10), nullable=False, default='0')
    dateCreated = db.Column(db.String(50), nullable=False)

class Student(db.Model):
    __tablename__ = 'tblstudents'
    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    firstName = db.Column(db.String(255), nullable=False)
    lastName = db.Column(db.String(255), nullable=False)
    otherName = db.Column(db.String(255), nullable=False, default='')
    admissionNumber = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False, default='12345')
    classId = db.Column(db.String(10), nullable=False)
    classArmId = db.Column(db.String(10), nullable=False)
    dateCreated = db.Column(db.String(50), nullable=False)

class Attendance(db.Model):
    __tablename__ = 'tblattendance'
    Id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    admissionNo = db.Column(db.String(255), nullable=False)
    classId = db.Column(db.String(10), nullable=False)
    classArmId = db.Column(db.String(10), nullable=False)
    sessionTermId = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='0')
    dateTimeTaken = db.Column(db.String(20), nullable=False)

# ─────────────────────────── HELPERS ───────────────────────────

def hash_password(text):
    return generate_password_hash(text)

def check_password(stored, provided):
    """Support Werkzeug hashes plus older PBKDF2/plain/MD5 passwords."""
    if stored.startswith(('scrypt:', 'pbkdf2:sha256:', 'pbkdf2:sha1:')):
        return check_password_hash(stored, provided)
    if stored.startswith('pbkdf2:'):
        dk = hashlib.pbkdf2_hmac('sha256', provided.encode(), b'ams-salt-v1', 200_000)
        return stored == 'pbkdf2:' + dk.hex()
    # plain password (students default '12345')
    if stored == provided:
        return True
    # legacy MD5
    return stored in (
        hashlib.md5(provided.encode()).hexdigest().upper(),
        hashlib.md5(provided.encode()).hexdigest()
    )

def is_legacy_password(stored):
    return not stored.startswith(('scrypt:', 'pbkdf2:sha256:', 'pbkdf2:sha1:'))

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Please log in as Admin.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'teacher':
            flash('Please log in as Teacher.', 'warning')
            return redirect(url_for('teacher_login'))
        return f(*args, **kwargs)
    return decorated

def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'student':
            flash('Please log in as Student.', 'warning')
            return redirect(url_for('student_login'))
        return f(*args, **kwargs)
    return decorated

def get_active_session():
    return SessionTerm.query.filter_by(isActive='1').first()

def attendance_taken_today(classId, classArmId):
    today = str(date.today())
    return Attendance.query.filter_by(
        classId=classId, classArmId=classArmId,
        dateTimeTaken=today, status='1').count() > 0

# ─────────────────────────── SEED ───────────────────────────

def seed_db():
    if Admin.query.first():
        return
    today_str = str(date.today())
    db.session.add(Admin(Id=1, firstName='Admin', lastName='User',
                         emailAddress='admin@mail.com', password=hash_password('admin123')))
    db.session.add_all([
        Class(Id=1, className='Seven'),
        Class(Id=3, className='Eight'),
        Class(Id=4, className='Nine'),
    ])
    db.session.add_all([
        ClassArm(Id=2, classId='1', classArmName='S1', isAssigned='1'),
        ClassArm(Id=4, classId='1', classArmName='S2', isAssigned='1'),
        ClassArm(Id=5, classId='3', classArmName='E1', isAssigned='1'),
        ClassArm(Id=6, classId='4', classArmName='N1', isAssigned='1'),
    ])
    db.session.add_all([
        Term(Id=1, termName='First'),
        Term(Id=2, termName='Second'),
        Term(Id=3, termName='Third'),
    ])
    db.session.add_all([
        SessionTerm(Id=1, sessionName='2024/2025', termId='1', isActive='1', dateCreated=today_str),
        SessionTerm(Id=2, sessionName='2024/2025', termId='2', isActive='0', dateCreated=today_str),
    ])
    tp = hash_password('teacher123')
    db.session.add_all([
        ClassTeacher(Id=1, firstName='Will',   lastName='Kibagendi', emailAddress='teacher2@mail.com', password=tp, phoneNo='09089898999', classId='1', classArmId='2', dateCreated=today_str),
        ClassTeacher(Id=4, firstName='Demola', lastName='Ade',       emailAddress='teacher3@gmail.com',password=tp, phoneNo='09672002882', classId='1', classArmId='4', dateCreated=today_str),
        ClassTeacher(Id=5, firstName='Ryan',   lastName='Mbeche',    emailAddress='teacher4@mail.com', password=tp, phoneNo='7014560000',  classId='3', classArmId='5', dateCreated=today_str),
        ClassTeacher(Id=6, firstName='John',   lastName='Keroche',   emailAddress='teacher@mail.com',  password=tp, phoneNo='0100000030', classId='4', classArmId='6', dateCreated=today_str),
    ])
    db.session.add_all([
        Student(Id=1,  firstName='Thomas',  lastName='Omari',    admissionNumber='AMS005', classId='1', classArmId='2', dateCreated=today_str),
        Student(Id=3,  firstName='Samuel',  lastName='Ondieki',  admissionNumber='AMS007', classId='1', classArmId='2', dateCreated=today_str),
        Student(Id=4,  firstName='Milagros',lastName='Oloo',     admissionNumber='AMS011', classId='1', classArmId='2', dateCreated=today_str),
        Student(Id=5,  firstName='Luis',    lastName='Ayo',      admissionNumber='AMS012', classId='1', classArmId='4', dateCreated=today_str),
        Student(Id=6,  firstName='Sandra',  lastName='Sagero',   admissionNumber='AMS015', classId='1', classArmId='4', dateCreated=today_str),
        Student(Id=7,  firstName='Smith',   lastName='Makori',   otherName='Mack', admissionNumber='AMS017', classId='1', classArmId='4', dateCreated=today_str),
        Student(Id=8,  firstName='Juliana', lastName='Kerubo',   admissionNumber='AMS019', classId='3', classArmId='5', dateCreated=today_str),
        Student(Id=9,  firstName='Richard', lastName='Semo',     admissionNumber='AMS021', classId='3', classArmId='5', dateCreated=today_str),
        Student(Id=10, firstName='Jon',     lastName='Mbeeka',   admissionNumber='AMS110', classId='4', classArmId='6', dateCreated=today_str),
        Student(Id=11, firstName='Aida',    lastName='Moraa',    admissionNumber='AMS133', classId='4', classArmId='6', dateCreated=today_str),
        Student(Id=12, firstName='Miguel',  lastName='Bush',     admissionNumber='AMS135', classId='4', classArmId='6', dateCreated=today_str),
        Student(Id=13, firstName='Sergio',  lastName='Hammons',  admissionNumber='AMS144', classId='4', classArmId='6', dateCreated=today_str),
        Student(Id=14, firstName='Lyn',     lastName='Rogers',   admissionNumber='AMS148', classId='4', classArmId='6', dateCreated=today_str),
        Student(Id=15, firstName='James',   lastName='Dominick', admissionNumber='AMS151', classId='4', classArmId='6', dateCreated=today_str),
        Student(Id=16, firstName='Ethel',   lastName='Quin',     admissionNumber='AMS159', classId='4', classArmId='6', dateCreated=today_str),
        Student(Id=17, firstName='Roland',  lastName='Estrada',  admissionNumber='AMS161', classId='4', classArmId='6', dateCreated=today_str),
    ])
    db.session.commit()

# ─────────────────────────── CONTEXT PROCESSOR ───────────────────────────

@app.context_processor
def inject_globals():
    return dict(
        active_session_global=get_active_session(),
        today=str(date.today())
    )

# ─────────────────────────── ERROR HANDLERS ───────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500

# ─────────────────────────── INDEX ───────────────────────────

@app.route('/')
def index():
    role = session.get('role')
    if role == 'admin':   return redirect(url_for('admin_dashboard'))
    if role == 'teacher': return redirect(url_for('teacher_dashboard'))
    if role == 'student': return redirect(url_for('student_dashboard'))
    return render_template('landing.html')

# ─────────────────────────── ADMIN AUTH ───────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('role') == 'admin': return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        admin = Admin.query.filter_by(emailAddress=request.form.get('email','').strip()).first()
        if admin and check_password(admin.password, request.form.get('password','')):
            if is_legacy_password(admin.password):
                admin.password = hash_password(request.form.get('password',''))
                db.session.commit()
            session.clear()
            session.update({'userId': admin.Id, 'userName': f"{admin.firstName} {admin.lastName}".strip(), 'role': 'admin'})
            flash(f'Welcome back, {admin.firstName}!', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('admin_login.html')

# ─────────────────────────── TEACHER AUTH ───────────────────────────

@app.route('/teacher/login', methods=['GET', 'POST'])
def teacher_login():
    if session.get('role') == 'teacher': return redirect(url_for('teacher_dashboard'))
    if request.method == 'POST':
        teacher = ClassTeacher.query.filter_by(emailAddress=request.form.get('email','').strip()).first()
        if teacher and check_password(teacher.password, request.form.get('password','')):
            if is_legacy_password(teacher.password):
                teacher.password = hash_password(request.form.get('password',''))
                db.session.commit()
            session.clear()
            session.update({'userId': teacher.Id,
                            'userName': f"{teacher.firstName} {teacher.lastName}".strip(),
                            'classId': teacher.classId,
                            'classArmId': teacher.classArmId,
                            'role': 'teacher'})
            flash(f'Welcome back, {teacher.firstName}!', 'success')
            return redirect(url_for('teacher_dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('teacher_login.html')

# ─────────────────────────── STUDENT AUTH ───────────────────────────

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if session.get('role') == 'student': return redirect(url_for('student_dashboard'))
    if request.method == 'POST':
        adm_no = request.form.get('admissionNumber', '').strip()
        pwd    = request.form.get('password', '')
        student = Student.query.filter_by(admissionNumber=adm_no).first()
        if student and check_password(student.password, pwd):
            if is_legacy_password(student.password):
                student.password = hash_password(pwd)
                db.session.commit()
            session.clear()
            session.update({
                'userId':          student.Id,
                'userName':        f"{student.firstName} {student.lastName}".strip(),
                'admissionNumber': student.admissionNumber,
                'classId':         student.classId,
                'classArmId':      student.classArmId,
                'role':            'student'
            })
            flash(f'Welcome, {student.firstName}!', 'success')
            return redirect(url_for('student_dashboard'))
        flash('Invalid admission number or password.', 'danger')
    return render_template('student_login.html')

# ─────────────────────────── SHARED LOGOUT ───────────────────────────

@app.route('/logout')
def logout():
    role = session.get('role')
    session.clear()
    flash('You have been logged out.', 'info')
    if role == 'admin':   return redirect(url_for('admin_login'))
    if role == 'teacher': return redirect(url_for('teacher_login'))
    return redirect(url_for('student_login'))

# ═══════════════════════════════════════════════════════════════════
#  STUDENT PORTAL
# ═══════════════════════════════════════════════════════════════════

@app.route('/student/dashboard')
@student_required
def student_dashboard():
    student  = Student.query.get(session['userId'])
    cls      = Class.query.get(int(student.classId))
    arm      = ClassArm.query.get(int(student.classArmId))
    adm_no   = student.admissionNumber
    classId  = student.classId
    armId    = student.classArmId

    # Overall stats
    total   = Attendance.query.filter_by(admissionNo=adm_no, classId=classId, classArmId=armId).count()
    present = Attendance.query.filter_by(admissionNo=adm_no, classId=classId, classArmId=armId, status='1').count()
    absent  = total - present
    pct     = round(present / total * 100, 1) if total > 0 else 0

    # Today status
    today     = str(date.today())
    today_rec = Attendance.query.filter_by(admissionNo=adm_no, classId=classId, classArmId=armId, dateTimeTaken=today).first()

    # Weekly chart (last 7 days)
    weekly_labels, weekly_status = [], []
    for i in range(6, -1, -1):
        d = str(date.today() - timedelta(days=i))
        weekly_labels.append(d[5:])
        rec = Attendance.query.filter_by(admissionNo=adm_no, classId=classId, classArmId=armId, dateTimeTaken=d).first()
        weekly_status.append(1 if rec and rec.status == '1' else 0)

    # Recent 5 records
    recent = (Attendance.query
              .filter_by(admissionNo=adm_no, classId=classId, classArmId=armId)
              .order_by(Attendance.dateTimeTaken.desc())
              .limit(5).all())

    # Class rank by attendance %
    classmates = Student.query.filter_by(classId=classId, classArmId=armId).all()
    rank_list = []
    for s in classmates:
        t = Attendance.query.filter_by(admissionNo=s.admissionNumber, classId=classId, classArmId=armId).count()
        p = Attendance.query.filter_by(admissionNo=s.admissionNumber, classId=classId, classArmId=armId, status='1').count()
        rank_list.append((s.admissionNumber, round(p/t*100,1) if t > 0 else 0))
    rank_list.sort(key=lambda x: x[1], reverse=True)
    my_rank = next((i+1 for i, r in enumerate(rank_list) if r[0] == adm_no), None)

    return render_template('student_dashboard.html',
        student=student, cls=cls, arm=arm,
        total=total, present=present, absent=absent, pct=pct,
        today=today, today_rec=today_rec,
        weekly_labels=weekly_labels, weekly_status=weekly_status,
        recent=recent, my_rank=my_rank, class_size=len(classmates))


@app.route('/student/my-attendance')
@student_required
def student_my_attendance():
    student  = Student.query.get(session['userId'])
    cls      = Class.query.get(int(student.classId))
    arm      = ClassArm.query.get(int(student.classArmId))
    adm_no   = student.admissionNumber
    classId  = student.classId
    armId    = student.classArmId

    # Optional session filter
    filter_session = request.args.get('session_id')
    q = Attendance.query.filter_by(admissionNo=adm_no, classId=classId, classArmId=armId)
    if filter_session:
        q = q.filter_by(sessionTermId=filter_session)
    records = q.order_by(Attendance.dateTimeTaken.desc()).all()

    total   = len(records)
    present = sum(1 for r in records if r.status == '1')
    absent  = total - present
    pct     = round(present / total * 100, 1) if total > 0 else 0

    all_sessions = (db.session.query(SessionTerm, Term)
                    .join(Term, Term.Id == db.cast(SessionTerm.termId, db.Integer))
                    .order_by(SessionTerm.sessionName).all())

    return render_template('student_my_attendance.html',
        student=student, cls=cls, arm=arm,
        records=records, total=total, present=present,
        absent=absent, pct=pct,
        all_sessions=all_sessions,
        filter_session=filter_session)


@app.route('/student/my-attendance/export')
@student_required
def student_export_csv():
    student = Student.query.get(session['userId'])
    adm_no  = student.admissionNumber
    records = (Attendance.query
               .filter_by(admissionNo=adm_no, classId=student.classId, classArmId=student.classArmId)
               .order_by(Attendance.dateTimeTaken).all())
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Admission No', 'Name', 'Status'])
    for r in records:
        writer.writerow([r.dateTimeTaken, adm_no,
                         f"{student.firstName} {student.lastName}",
                         'Present' if r.status == '1' else 'Absent'])
    output.seek(0)
    return Response(output, mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=my_attendance_{adm_no}.csv'})


@app.route('/student/change-password', methods=['GET', 'POST'])
@student_required
def student_change_password():
    if request.method == 'POST':
        student  = Student.query.get(session['userId'])
        cur      = request.form.get('current_password', '')
        new_pwd  = request.form.get('new_password', '')
        confirm  = request.form.get('confirm_password', '')
        if not check_password(student.password, cur):
            flash('Current password is incorrect.', 'danger')
        elif len(new_pwd) < 6:
            flash('New password must be at least 6 characters.', 'danger')
        elif new_pwd != confirm:
            flash('New passwords do not match.', 'danger')
        else:
            student.password = hash_password(new_pwd)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('student_dashboard'))
    return render_template('student_change_password.html')


@app.route('/student/profile')
@student_required
def student_profile():
    student = Student.query.get(session['userId'])
    cls     = Class.query.get(int(student.classId))
    arm     = ClassArm.query.get(int(student.classArmId))
    teacher = ClassTeacher.query.filter_by(classId=student.classId, classArmId=student.classArmId).first()
    return render_template('student_profile.html', student=student, cls=cls, arm=arm, teacher=teacher)

# ═══════════════════════════════════════════════════════════════════
#  ADMIN ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    today_str = str(date.today())
    students_count  = Student.query.count()
    classes_count   = Class.query.count()
    teachers_count  = ClassTeacher.query.count()
    sessions_count  = SessionTerm.query.count()
    active_session  = get_active_session()
    attendance_today = Attendance.query.filter_by(dateTimeTaken=today_str, status='1').count()

    weekly_labels, weekly_present, weekly_absent = [], [], []
    for i in range(6, -1, -1):
        d = str(date.today() - timedelta(days=i))
        weekly_labels.append(d[5:])
        weekly_present.append(Attendance.query.filter_by(dateTimeTaken=d, status='1').count())
        weekly_absent.append(Attendance.query.filter_by(dateTimeTaken=d, status='0').count())

    class_summary = []
    for cls in Class.query.all():
        for arm in ClassArm.query.filter_by(classId=str(cls.Id)).all():
            total   = Student.query.filter_by(classId=str(cls.Id), classArmId=str(arm.Id)).count()
            present = Attendance.query.filter_by(classId=str(cls.Id), classArmId=str(arm.Id),
                                                  dateTimeTaken=today_str, status='1').count()
            if total > 0:
                class_summary.append({'class': cls.className, 'arm': arm.classArmName,
                                       'total': total, 'present': present,
                                       'absent': total - present,
                                       'pct': round(present / total * 100, 1)})
    return render_template('admin_dashboard.html',
        students=students_count, classes=classes_count,
        teachers=teachers_count, sessions=sessions_count,
        active_session=active_session, attendance_today=attendance_today,
        weekly_labels=weekly_labels, weekly_present=weekly_present, weekly_absent=weekly_absent,
        class_summary=class_summary)


@app.route('/admin/classes', methods=['GET', 'POST'])
@admin_required
def admin_classes():
    msg = None; edit_row = None
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'delete':
            c = db.session.get(Class, request.form.get('Id'))
            if not c:
                flash('Class not found.', 'warning')
            elif (ClassArm.query.filter_by(classId=str(c.Id)).count()
                  or Student.query.filter_by(classId=str(c.Id)).count()
                  or ClassTeacher.query.filter_by(classId=str(c.Id)).count()
                  or Attendance.query.filter_by(classId=str(c.Id)).count()):
                flash('Class is still in use and cannot be deleted.', 'danger')
            else:
                db.session.delete(c); db.session.commit(); flash('Class deleted.', 'success')
            return redirect(url_for('admin_classes'))
        if action == 'save':
            name = request.form['className'].strip()
            if Class.query.filter_by(className=name).first():
                msg = ('danger', 'Class already exists!')
            else:
                db.session.add(Class(className=name)); db.session.commit()
                flash('Class created!', 'success'); return redirect(url_for('admin_classes'))
        elif action == 'update':
            c = db.session.get(Class, request.form['Id'])
            if c: c.className = request.form['className'].strip(); db.session.commit()
            flash('Class updated!', 'success'); return redirect(url_for('admin_classes'))
    if request.args.get('action') == 'edit':
        edit_row = db.session.get(Class, request.args.get('Id'))
    return render_template('admin_classes.html', classes=Class.query.all(), msg=msg, edit_row=edit_row)


@app.route('/admin/class-arms', methods=['GET', 'POST'])
@admin_required
def admin_class_arms():
    msg = None; edit_row = None
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'delete':
            arm = db.session.get(ClassArm, request.form.get('Id'))
            if not arm:
                flash('Class arm not found.', 'warning')
            elif (Student.query.filter_by(classArmId=str(arm.Id)).count()
                  or ClassTeacher.query.filter_by(classArmId=str(arm.Id)).count()
                  or Attendance.query.filter_by(classArmId=str(arm.Id)).count()):
                flash('Class arm is still in use and cannot be deleted.', 'danger')
            else:
                db.session.delete(arm); db.session.commit(); flash('Arm deleted.', 'success')
            return redirect(url_for('admin_class_arms'))
        if action == 'save':
            cid, name = request.form['classId'], request.form['classArmName'].strip()
            if ClassArm.query.filter_by(classArmName=name, classId=cid).first():
                msg = ('danger', 'Class arm already exists!')
            else:
                db.session.add(ClassArm(classId=cid, classArmName=name, isAssigned='0')); db.session.commit()
                flash('Class arm created!', 'success'); return redirect(url_for('admin_class_arms'))
        elif action == 'update':
            arm = db.session.get(ClassArm, request.form['Id'])
            if arm: arm.classId = request.form['classId']; arm.classArmName = request.form['classArmName'].strip(); db.session.commit()
            flash('Class arm updated!', 'success'); return redirect(url_for('admin_class_arms'))
    if request.args.get('action') == 'edit':
        edit_row = db.session.get(ClassArm, request.args.get('Id'))
    arms = (db.session.query(ClassArm, Class)
            .join(Class, Class.Id == db.cast(ClassArm.classId, db.Integer))
            .order_by(Class.className, ClassArm.classArmName).all())
    return render_template('admin_class_arms.html', arms=arms,
                           classes=Class.query.order_by(Class.className).all(), msg=msg, edit_row=edit_row)


@app.route('/admin/sessions', methods=['GET', 'POST'])
@admin_required
def admin_sessions():
    msg = None; edit_row = None
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'delete':
            s = db.session.get(SessionTerm, request.form.get('Id'))
            if not s:
                flash('Session not found.', 'warning')
            elif Attendance.query.filter_by(sessionTermId=str(s.Id)).count():
                flash('Session has attendance records and cannot be deleted.', 'danger')
            else:
                db.session.delete(s); db.session.commit(); flash('Session deleted.', 'success')
            return redirect(url_for('admin_sessions'))
        if action == 'activate':
            SessionTerm.query.update({'isActive': '0'})
            s = db.session.get(SessionTerm, request.form.get('Id'))
            if s: s.isActive = '1'; db.session.commit(); flash(f'"{s.sessionName}" is now active!', 'success')
            return redirect(url_for('admin_sessions'))
        if action == 'save':
            sname, tid = request.form['sessionName'].strip(), request.form['termId']
            if SessionTerm.query.filter_by(sessionName=sname, termId=tid).first():
                msg = ('danger', 'This session+term already exists!')
            else:
                db.session.add(SessionTerm(sessionName=sname, termId=tid, isActive='0', dateCreated=str(date.today()))); db.session.commit()
                flash('Session created!', 'success'); return redirect(url_for('admin_sessions'))
        elif action == 'update':
            s = db.session.get(SessionTerm, request.form['Id'])
            if s: s.sessionName = request.form['sessionName'].strip(); s.termId = request.form['termId']; db.session.commit()
            flash('Session updated!', 'success'); return redirect(url_for('admin_sessions'))
    if request.args.get('action') == 'edit':
        edit_row = db.session.get(SessionTerm, request.args.get('Id'))
    sessions = (db.session.query(SessionTerm, Term)
                .join(Term, Term.Id == db.cast(SessionTerm.termId, db.Integer))
                .order_by(SessionTerm.sessionName).all())
    return render_template('admin_sessions.html', sessions=sessions, terms=Term.query.all(), msg=msg, edit_row=edit_row)


@app.route('/admin/teachers', methods=['GET', 'POST'])
@admin_required
def admin_teachers():
    msg = None; edit_row = None
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'delete':
            t = db.session.get(ClassTeacher, request.form.get('Id'))
            if t:
                arm = db.session.get(ClassArm, int(t.classArmId))
                if arm: arm.isAssigned = '0'
                db.session.delete(t); db.session.commit(); flash('Teacher deleted.', 'success')
            else:
                flash('Teacher not found.', 'warning')
            return redirect(url_for('admin_teachers'))
        if action == 'save':
            email = request.form['emailAddress'].strip()
            if ClassTeacher.query.filter_by(emailAddress=email).first():
                msg = ('danger', 'Email already exists!')
            else:
                arm = db.session.get(ClassArm, int(request.form['classArmId']))
                if arm: arm.isAssigned = '1'
                db.session.add(ClassTeacher(
                    firstName=request.form['firstName'].strip(), lastName=request.form['lastName'].strip(),
                    emailAddress=email, password=hash_password(request.form['password']),
                    phoneNo=request.form['phoneNo'].strip(),
                    classId=request.form['classId'], classArmId=request.form['classArmId'],
                    dateCreated=str(date.today())))
                db.session.commit(); flash('Teacher created!', 'success'); return redirect(url_for('admin_teachers'))
        elif action == 'update':
            t = db.session.get(ClassTeacher, request.form['Id'])
            if t:
                old_arm_id = t.classArmId
                t.firstName=request.form['firstName'].strip(); t.lastName=request.form['lastName'].strip()
                t.emailAddress=request.form['emailAddress'].strip(); t.phoneNo=request.form['phoneNo'].strip()
                t.classId=request.form['classId']; t.classArmId=request.form['classArmId']
                if request.form.get('password'): t.password = hash_password(request.form['password'])
                if old_arm_id != t.classArmId:
                    old_arm = db.session.get(ClassArm, int(old_arm_id))
                    new_arm = db.session.get(ClassArm, int(t.classArmId))
                    if old_arm: old_arm.isAssigned = '0'
                    if new_arm: new_arm.isAssigned = '1'
                db.session.commit(); flash('Teacher updated!', 'success'); return redirect(url_for('admin_teachers'))
    if request.args.get('action') == 'edit':
        edit_row = db.session.get(ClassTeacher, request.args.get('Id'))
    teachers = ClassTeacher.query.order_by(ClassTeacher.firstName).all()
    classes  = Class.query.order_by(Class.className).all()
    arms     = ClassArm.query.all()
    return render_template('admin_teachers.html', teachers=teachers, classes=classes, arms=arms,
        class_map={str(c.Id): c.className for c in classes},
        arm_map={str(a.Id): a.classArmName for a in arms}, msg=msg, edit_row=edit_row)


@app.route('/admin/students', methods=['GET', 'POST'])
@admin_required
def admin_students():
    msg = None; edit_row = None
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        if action == 'delete':
            s = db.session.get(Student, request.form.get('Id'))
            if s:
                Attendance.query.filter_by(admissionNo=s.admissionNumber).delete()
                db.session.delete(s); db.session.commit(); flash('Student deleted.', 'success')
            else:
                flash('Student not found.', 'warning')
            return redirect(url_for('admin_students'))
        if action == 'save':
            admNo = request.form['admissionNumber'].strip()
            if Student.query.filter_by(admissionNumber=admNo).first():
                msg = ('danger', 'Admission number already exists!')
            else:
                db.session.add(Student(
                    firstName=request.form['firstName'].strip(), lastName=request.form['lastName'].strip(),
                    otherName=request.form.get('otherName','').strip(), admissionNumber=admNo,
                    password=hash_password('12345'), classId=request.form['classId'], classArmId=request.form['classArmId'],
                    dateCreated=str(date.today())))
                db.session.commit(); flash('Student created!', 'success'); return redirect(url_for('admin_students'))
        elif action == 'update':
            s = db.session.get(Student, request.form['Id'])
            if s:
                s.firstName=request.form['firstName'].strip(); s.lastName=request.form['lastName'].strip()
                s.otherName=request.form.get('otherName','').strip()
                s.admissionNumber=request.form['admissionNumber'].strip()
                s.classId=request.form['classId']; s.classArmId=request.form['classArmId']
                db.session.commit(); flash('Student updated!', 'success'); return redirect(url_for('admin_students'))
    if request.args.get('action') == 'edit':
        edit_row = db.session.get(Student, request.args.get('Id'))
    students = Student.query.order_by(Student.lastName).all()
    classes  = Class.query.order_by(Class.className).all()
    arms     = ClassArm.query.all()
    return render_template('admin_students.html', students=students, classes=classes, arms=arms,
        class_map={str(c.Id): c.className for c in classes},
        arm_map={str(a.Id): a.classArmName for a in arms}, msg=msg, edit_row=edit_row)


@app.route('/admin/attendance-report', methods=['GET', 'POST'])
@admin_required
def admin_attendance_report():
    records = []; filters = {}
    classes = Class.query.order_by(Class.className).all()
    arms    = ClassArm.query.all()
    if request.method == 'POST':
        df  = request.form.get('date_from')
        dt  = request.form.get('date_to')
        cid = request.form.get('classId')
        aid = request.form.get('classArmId')
        filters = dict(date_from=df, date_to=dt, classId=cid, classArmId=aid)
        q = (db.session.query(Student, Attendance)
             .join(Attendance, Attendance.admissionNo == Student.admissionNumber)
             .filter(Attendance.dateTimeTaken >= df, Attendance.dateTimeTaken <= dt))
        if cid: q = q.filter(Attendance.classId == cid)
        if aid: q = q.filter(Attendance.classArmId == aid)
        records = q.order_by(Attendance.dateTimeTaken.desc(), Student.lastName).all()
    return render_template('admin_attendance_report.html', records=records, filters=filters,
        classes=classes, arms=arms,
        class_map={str(c.Id): c.className for c in classes},
        arm_map={str(a.Id): a.classArmName for a in arms})


@app.route('/admin/attendance-report/export')
@admin_required
def export_attendance_csv():
    df  = request.args.get('date_from', str(date.today()))
    dt  = request.args.get('date_to',   str(date.today()))
    cid = request.args.get('classId')
    aid = request.args.get('classArmId')
    arms    = ClassArm.query.all()
    classes = Class.query.all()
    arm_map   = {str(a.Id): a.classArmName for a in arms}
    class_map = {str(c.Id): c.className for c in classes}
    q = (db.session.query(Student, Attendance)
         .join(Attendance, Attendance.admissionNo == Student.admissionNumber)
         .filter(Attendance.dateTimeTaken >= df, Attendance.dateTimeTaken <= dt))
    if cid: q = q.filter(Attendance.classId == cid)
    if aid: q = q.filter(Attendance.classArmId == aid)
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['Date','Admission No','First Name','Last Name','Class','Arm','Status'])
    for s, a in q.order_by(Attendance.dateTimeTaken, Student.lastName).all():
        writer.writerow([a.dateTimeTaken, s.admissionNumber, s.firstName, s.lastName,
                         class_map.get(a.classId, a.classId), arm_map.get(a.classArmId, a.classArmId),
                         'Present' if a.status == '1' else 'Absent'])
    output.seek(0)
    return Response(output, mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=attendance_{df}_to_{dt}.csv'})


@app.route('/admin/change-password', methods=['GET', 'POST'])
@admin_required
def admin_change_password():
    if request.method == 'POST':
        admin = db.session.get(Admin, session['userId'])
        cur, new_pwd, conf = (request.form.get('current_password',''),
                              request.form.get('new_password',''),
                              request.form.get('confirm_password',''))
        if not check_password(admin.password, cur):  flash('Current password is incorrect.', 'danger')
        elif len(new_pwd) < 6:                        flash('Minimum 6 characters required.', 'danger')
        elif new_pwd != conf:                         flash('Passwords do not match.', 'danger')
        else:
            admin.password = hash_password(new_pwd); db.session.commit()
            flash('Password changed!', 'success'); return redirect(url_for('admin_dashboard'))
    return render_template('admin_change_password.html')

# ─── AJAX ───

@app.route('/ajax/class-arms/<class_id>')
def ajax_class_arms(class_id):
    arms = ClassArm.query.filter_by(classId=class_id).order_by(ClassArm.classArmName).all()
    return jsonify([{'Id': a.Id, 'classArmName': a.classArmName, 'isAssigned': a.isAssigned} for a in arms])

@app.route('/ajax/free-arms/<class_id>')
def ajax_free_arms(class_id):
    arms = ClassArm.query.filter_by(classId=class_id, isAssigned='0').order_by(ClassArm.classArmName).all()
    return jsonify([{'Id': a.Id, 'classArmName': a.classArmName} for a in arms])

# ═══════════════════════════════════════════════════════════════════
#  TEACHER ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.route('/teacher/dashboard')
@teacher_required
def teacher_dashboard():
    teacher  = db.session.get(ClassTeacher, session['userId'])
    cls      = db.session.get(Class, int(session['classId']))
    arm      = db.session.get(ClassArm, int(session['classArmId']))
    classId, classArmId = session['classId'], session['classArmId']
    today_str = str(date.today())
    students_count = Student.query.filter_by(classId=classId, classArmId=classArmId).count()
    taken_today    = attendance_taken_today(classId, classArmId)
    present_today  = Attendance.query.filter_by(classId=classId, classArmId=classArmId, dateTimeTaken=today_str, status='1').count()
    total_att      = Attendance.query.filter_by(classId=classId, classArmId=classArmId).count()
    present_att    = Attendance.query.filter_by(classId=classId, classArmId=classArmId, status='1').count()
    overall_pct    = round(present_att / total_att * 100, 1) if total_att > 0 else 0
    weekly_labels, weekly_present, weekly_absent = [], [], []
    for i in range(6, -1, -1):
        d = str(date.today() - timedelta(days=i))
        weekly_labels.append(d[5:])
        weekly_present.append(Attendance.query.filter_by(classId=classId, classArmId=classArmId, dateTimeTaken=d, status='1').count())
        weekly_absent.append( Attendance.query.filter_by(classId=classId, classArmId=classArmId, dateTimeTaken=d, status='0').count())
    return render_template('teacher_dashboard.html', teacher=teacher, cls=cls, arm=arm,
        students_count=students_count, taken_today=taken_today, present_today=present_today,
        overall_pct=overall_pct, weekly_labels=weekly_labels,
        weekly_present=weekly_present, weekly_absent=weekly_absent)


@app.route('/teacher/take-attendance', methods=['GET', 'POST'])
@teacher_required
def take_attendance():
    active_session = get_active_session()
    if not active_session:
        flash('No active session/term. Contact the administrator.', 'warning')
        return redirect(url_for('teacher_dashboard'))
    today_str = str(date.today())
    classId, classArmId = session['classId'], session['classArmId']
    if Attendance.query.filter_by(classId=classId, classArmId=classArmId, dateTimeTaken=today_str).count() == 0:
        for st in Student.query.filter_by(classId=classId, classArmId=classArmId).all():
            db.session.add(Attendance(admissionNo=st.admissionNumber, classId=classId, classArmId=classArmId,
                                      sessionTermId=str(active_session.Id), status='0', dateTimeTaken=today_str))
        db.session.commit()
    already_taken = attendance_taken_today(classId, classArmId)
    if request.method == 'POST':
        action = request.form.get('form_action', 'submit')
        if action == 'reset':
            Attendance.query.filter_by(classId=classId, classArmId=classArmId, dateTimeTaken=today_str).update({'status': '0'})
            db.session.commit(); flash('Attendance reset. You can re-submit.', 'info')
            return redirect(url_for('take_attendance'))
        elif not already_taken:
            checked = request.form.getlist('check')
            for admNo in request.form.getlist('admissionNo'):
                rec = Attendance.query.filter_by(admissionNo=admNo, classId=classId, classArmId=classArmId, dateTimeTaken=today_str).first()
                if rec: rec.status = '1' if admNo in checked else '0'
            db.session.commit(); flash('Attendance submitted!', 'success')
            return redirect(url_for('take_attendance'))
    students = (db.session.query(Student, Attendance)
        .join(Attendance, (Attendance.admissionNo == Student.admissionNumber) &
              (Attendance.classId == classId) & (Attendance.classArmId == classArmId) &
              (Attendance.dateTimeTaken == today_str))
        .filter(Student.classId == classId, Student.classArmId == classArmId)
        .order_by(Student.lastName).all())
    present_count = sum(1 for _, a in students if a and a.status == '1')
    return render_template('take_attendance.html', students=students, already_taken=already_taken,
        today=today_str, present_count=present_count, total_count=len(students))


@app.route('/teacher/view-attendance', methods=['GET', 'POST'])
@teacher_required
def view_attendance():
    records = []; selected_date = None
    classId, classArmId = session['classId'], session['classArmId']
    cls = db.session.get(Class, int(classId)); arm = db.session.get(ClassArm, int(classArmId))
    dates_taken = [d[0] for d in db.session.query(Attendance.dateTimeTaken)
                   .filter_by(classId=classId, classArmId=classArmId).distinct()
                   .order_by(Attendance.dateTimeTaken.desc()).all()]
    if request.method == 'POST':
        selected_date = request.form['date']
        records = (db.session.query(Student, Attendance)
            .join(Attendance, (Attendance.admissionNo == Student.admissionNumber) &
                  (Attendance.classId == classId) & (Attendance.classArmId == classArmId) &
                  (Attendance.dateTimeTaken == selected_date))
            .filter(Student.classId == classId, Student.classArmId == classArmId)
            .order_by(Student.lastName).all())
    present = sum(1 for _, a in records if a and a.status == '1')
    return render_template('view_attendance.html', records=records, selected_date=selected_date,
        cls=cls, arm=arm, dates_taken=dates_taken, present=present, absent=len(records)-present)


@app.route('/teacher/view-students')
@teacher_required
def view_students():
    classId, classArmId = session['classId'], session['classArmId']
    students = Student.query.filter_by(classId=classId, classArmId=classArmId).order_by(Student.lastName).all()
    cls = db.session.get(Class, int(classId)); arm = db.session.get(ClassArm, int(classArmId))
    student_stats = []
    for s in students:
        total   = Attendance.query.filter_by(admissionNo=s.admissionNumber, classId=classId, classArmId=classArmId).count()
        present = Attendance.query.filter_by(admissionNo=s.admissionNumber, classId=classId, classArmId=classArmId, status='1').count()
        pct     = round(present / total * 100, 1) if total > 0 else 0
        student_stats.append({'student': s, 'total': total, 'present': present, 'absent': total-present, 'pct': pct})
    return render_template('view_students.html', student_stats=student_stats, cls=cls, arm=arm)


@app.route('/teacher/student-attendance/<admission_no>')
@teacher_required
def student_attendance(admission_no):
    classId, classArmId = session['classId'], session['classArmId']
    student = Student.query.filter_by(
        admissionNumber=admission_no,
        classId=classId,
        classArmId=classArmId
    ).first_or_404()
    records = Attendance.query.filter_by(admissionNo=admission_no, classId=classId, classArmId=classArmId)\
                              .order_by(Attendance.dateTimeTaken.desc()).all()
    total   = len(records)
    present = sum(1 for r in records if r.status == '1')
    return render_template('student_attendance.html', student=student, records=records,
        total=total, present=present, absent=total-present,
        pct=round(present/total*100, 1) if total else 0)


@app.route('/teacher/change-password', methods=['GET', 'POST'])
@teacher_required
def teacher_change_password():
    if request.method == 'POST':
        teacher = db.session.get(ClassTeacher, session['userId'])
        cur, new_pwd, conf = (request.form.get('current_password',''),
                              request.form.get('new_password',''),
                              request.form.get('confirm_password',''))
        if not check_password(teacher.password, cur):  flash('Current password is incorrect.', 'danger')
        elif len(new_pwd) < 6:                          flash('Minimum 6 characters required.', 'danger')
        elif new_pwd != conf:                           flash('Passwords do not match.', 'danger')
        else:
            teacher.password = hash_password(new_pwd); db.session.commit()
            flash('Password changed!', 'success'); return redirect(url_for('teacher_dashboard'))
    return render_template('teacher_change_password.html')


@app.route('/teacher/export-attendance')
@teacher_required
def teacher_export_csv():
    classId, classArmId = session['classId'], session['classArmId']
    cls = db.session.get(Class, int(classId)); arm = db.session.get(ClassArm, int(classArmId))
    rows = (db.session.query(Student, Attendance)
        .join(Attendance, Attendance.admissionNo == Student.admissionNumber)
        .filter(Attendance.classId == classId, Attendance.classArmId == classArmId)
        .order_by(Attendance.dateTimeTaken, Student.lastName).all())
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['Date','Admission No','First Name','Last Name','Status'])
    for s, a in rows:
        writer.writerow([a.dateTimeTaken, s.admissionNumber, s.firstName, s.lastName,
                         'Present' if a.status == '1' else 'Absent'])
    output.seek(0)
    return Response(output, mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=attendance_{cls.className}_{arm.classArmName}.csv'})

# ─────────────────────────── ENTRY POINT ───────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_db()
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(debug=debug, port=5000)
