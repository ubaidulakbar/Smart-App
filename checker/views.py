from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from openpyxl import load_workbook

from .decorators import app_admin_required, checker_required, teacher_required, is_app_admin, is_teacher_user
from .forms import (
    AdminCorrectionReviewForm,
    AdminTeacherProgressEditForm,
    ClassSetupForm,
    CorrectionRequestForm,
    LockRecordForm,
    PasswordResetByAdminForm,
    SelectCheckForm,
    StudentForm,
    StudentImportUploadForm,
    TeacherCourseAssignmentForm,
    TeacherProgressForm,
    UserCreateByAdminForm,
    UserProfileForm,
)
from .models import (
    ClassRoom,
    ClassSubject,
    ClassSubjectChapter,
    CopyCheckRecord,
    CorrectionRequest,
    DailyBackup,
    Student,
    Subject,
    TeacherCourseAssignment,
    TeacherCourseProgress,
    UserProfile,
)
from .utils import ensure_daily_backup, get_backup_path, log_action

PENDING_STATUS = 'pending'


def _days_since(dt):
    if not dt:
        return None
    return (timezone.localdate() - timezone.localtime(dt).date()).days


def _relative_date(dt):
    if not dt:
        return 'Never'
    days = _days_since(dt)
    if days == 0:
        return 'Today'
    if days == 1:
        return 'Yesterday'
    return f'{days} days ago'


def _progress_percent(checked, expected):
    if expected <= 0:
        return 0
    return round((checked / expected) * 100)


def _last_checker_name(record):
    if not record:
        return '—'
    return _display_user(record.entered_by)


def _attention_class_subject_rows(limit):
    rows = []
    class_subjects = ClassSubject.objects.filter(
        is_active=True,
        classroom__is_active=True,
        subject__is_active=True,
    ).select_related('classroom', 'subject').order_by('classroom__name', 'classroom__section', 'subject__name')

    for class_subject in class_subjects:
        total_students = Student.objects.filter(classroom=class_subject.classroom, is_active=True).count()
        chapter_ids = list(class_subject.chapters.filter(is_active=True).values_list('id', flat=True))
        total_chapters = len(chapter_ids)
        expected_records = total_students * total_chapters
        checked_records = CopyCheckRecord.objects.filter(class_subject=class_subject, locked=True).count()
        pending_records = max(expected_records - checked_records, 0)
        last_record = CopyCheckRecord.objects.filter(class_subject=class_subject, locked=True).select_related(
            'chapter', 'entered_by', 'entered_by__checker_profile'
        ).order_by('-locked_at', '-id').first()

        pending_chapters = 0
        if total_students and chapter_ids:
            chapter_counts = dict(
                CopyCheckRecord.objects.filter(class_subject=class_subject, locked=True)
                .values('chapter_id')
                .annotate(total=Count('id'))
                .values_list('chapter_id', 'total')
            )
            pending_chapters = sum(1 for chapter_id in chapter_ids if chapter_counts.get(chapter_id, 0) < total_students)
        elif chapter_ids:
            pending_chapters = total_chapters

        last_checked_at = last_record.locked_at if last_record else None
        progress = _progress_percent(checked_records, expected_records)
        rows.append({
            'class_subject': class_subject,
            'classroom': class_subject.classroom,
            'subject': class_subject.subject,
            'total_students': total_students,
            'total_chapters': total_chapters,
            'expected_records': expected_records,
            'checked_records': checked_records,
            'pending_records': pending_records,
            'pending_chapters': pending_chapters,
            'progress': progress,
            'last_record': last_record,
            'last_checked_at': last_checked_at,
            'last_checked_label': _relative_date(last_checked_at),
            'days_since': _days_since(last_checked_at),
            'last_chapter': last_record.chapter.title if last_record else '—',
            'last_checker': _last_checker_name(last_record),
            'sort_key': (0 if last_checked_at is None else 1, last_checked_at or timezone.datetime.min.replace(tzinfo=timezone.get_current_timezone()), progress, checked_records),
        })

    rows.sort(key=lambda row: row['sort_key'])
    return rows[:limit]


def _attention_student_rows(limit):
    rows = []
    students = Student.objects.filter(is_active=True, classroom__is_active=True).select_related('classroom').order_by(
        'classroom__name', 'classroom__section', 'roll_no', 'full_name'
    )
    for student in students:
        total_expected = ClassSubjectChapter.objects.filter(
            class_subject__classroom=student.classroom,
            class_subject__is_active=True,
            class_subject__subject__is_active=True,
            is_active=True,
        ).count()
        checked_records = CopyCheckRecord.objects.filter(student=student, locked=True).count()
        pending_records = max(total_expected - checked_records, 0)
        last_record = CopyCheckRecord.objects.filter(student=student, locked=True).select_related(
            'class_subject__subject', 'chapter', 'entered_by', 'entered_by__checker_profile'
        ).order_by('-locked_at', '-id').first()
        last_checked_at = last_record.locked_at if last_record else None
        progress = _progress_percent(checked_records, total_expected)
        rows.append({
            'student': student,
            'classroom': student.classroom,
            'total_expected': total_expected,
            'checked_records': checked_records,
            'pending_records': pending_records,
            'progress': progress,
            'last_record': last_record,
            'last_checked_at': last_checked_at,
            'last_checked_label': _relative_date(last_checked_at),
            'days_since': _days_since(last_checked_at),
            'last_subject': last_record.subject.name if last_record else '—',
            'last_chapter': last_record.chapter.title if last_record else '—',
            'last_checker': _last_checker_name(last_record),
            'sort_key': (0 if last_checked_at is None else 1, last_checked_at or timezone.datetime.min.replace(tzinfo=timezone.get_current_timezone()), progress, checked_records),
        })

    rows.sort(key=lambda row: row['sort_key'])
    return rows[:limit]


def _display_user(user):
    profile = getattr(user, 'checker_profile', None)
    if profile:
        return profile.display_name
    return user.username


def _subject_rows_from_post(request):
    subject_names = request.POST.getlist('subject_name')
    chapter_counts = request.POST.getlist('chapter_count')
    rows = []
    errors = []
    seen = set()
    for index, raw_name in enumerate(subject_names):
        name = (raw_name or '').strip()
        raw_count = chapter_counts[index] if index < len(chapter_counts) else ''
        if not name and not raw_count:
            continue
        if not name:
            errors.append(f'Subject row {index + 1}: subject name is required.')
            continue
        if name.lower() in seen:
            errors.append(f'Subject row {index + 1}: duplicate subject "{name}".')
            continue
        seen.add(name.lower())
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            errors.append(f'Subject row {index + 1}: chapter count must be a number.')
            continue
        if count < 1:
            errors.append(f'Subject row {index + 1}: chapter count must be at least 1.')
            continue
        if count > 100:
            errors.append(f'Subject row {index + 1}: chapter count cannot be more than 100.')
            continue
        rows.append({'name': name, 'chapter_count': count})
    if not rows:
        errors.append('Add at least one subject with a chapter count.')
    return rows, errors


def _validate_class_subject_changes(classroom, subject_rows):
    """Return safety errors before syncing class subjects.

    Chapters may be increased but not decreased. Subjects removed from the
    edit form are marked inactive instead of being deleted, so older records
    remain safe.
    """
    if not classroom or not classroom.pk:
        return []

    errors = []
    existing_subjects = {
        cs.subject.name.strip().lower(): cs
        for cs in ClassSubject.objects.filter(classroom=classroom).select_related('subject')
    }
    for row in subject_rows:
        existing = existing_subjects.get(row['name'].strip().lower())
        if existing and row['chapter_count'] < existing.chapter_count:
            errors.append(
                f'Cannot decrease chapters for {existing.subject.name}. '
                f'Current count is {existing.chapter_count}; entered count is {row["chapter_count"]}. '
                'Add a new class setup or keep the old chapter count.'
            )
    return errors


def _sync_class_subjects(classroom, subject_rows):
    submitted_subject_ids = []
    for row in subject_rows:
        subject, _created = Subject.objects.get_or_create(
            name=row['name'],
            defaults={'is_active': True},
        )
        if not subject.is_active:
            subject.is_active = True
            subject.save(update_fields=['is_active'])

        class_subject, _created = ClassSubject.objects.update_or_create(
            classroom=classroom,
            subject=subject,
            defaults={'chapter_count': row['chapter_count'], 'is_active': True},
        )
        submitted_subject_ids.append(class_subject.id)

        for number in range(1, row['chapter_count'] + 1):
            ClassSubjectChapter.objects.update_or_create(
                class_subject=class_subject,
                number=number,
                defaults={'is_active': True},
            )

        ClassSubjectChapter.objects.filter(
            class_subject=class_subject,
            number__gt=row['chapter_count'],
        ).update(is_active=False)

    # Subjects removed from the edit form are hidden, not deleted, so older records remain safe.
    ClassSubject.objects.filter(classroom=classroom).exclude(id__in=submitted_subject_ids).update(is_active=False)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('dashboard')
    return render(request, 'checker/login.html', {'form': form})


@login_required
def dashboard(request):
    if is_app_admin(request.user):
        today = timezone.localdate()
        month_start = today.replace(day=1)
        checker_stats_month = (
            CopyCheckRecord.objects.filter(locked=True, locked_at__date__gte=month_start)
            .values('entered_by__username', 'entered_by__checker_profile__display_name')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        checker_stats_all = (
            CopyCheckRecord.objects.filter(locked=True)
            .values('entered_by__username', 'entered_by__checker_profile__display_name')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        pending_requests = CorrectionRequest.objects.filter(status=CorrectionRequest.STATUS_PENDING).count()
        context = {
            'total_locked': CopyCheckRecord.objects.filter(locked=True).count(),
            'month_locked': CopyCheckRecord.objects.filter(locked=True, locked_at__date__gte=month_start).count(),
            'today_locked': CopyCheckRecord.objects.filter(locked=True, locked_at__date=today).count(),
            'pending_requests': pending_requests,
            'teacher_assignments_count': TeacherCourseAssignment.objects.filter(is_active=True).count(),
            'teacher_completed_count': TeacherCourseProgress.objects.filter(status=TeacherCourseProgress.STATUS_COMPLETED).count(),
            'checker_stats_month': checker_stats_month,
            'checker_stats_all': checker_stats_all,
            'recent_records': CopyCheckRecord.objects.select_related(
                'student', 'classroom', 'class_subject__subject', 'chapter', 'entered_by'
            )[:12],
            'recent_teacher_progress': TeacherCourseProgress.objects.select_related(
                'assignment__teacher__checker_profile',
                'assignment__class_subject__classroom',
                'assignment__class_subject__subject',
            ).order_by('-updated_at')[:8],
            'attention_class_subjects': _attention_class_subject_rows(5),
            'attention_students': _attention_student_rows(5),
        }
        return render(request, 'checker/admin_dashboard.html', context)

    if is_teacher_user(request.user):
        assignments = TeacherCourseAssignment.objects.filter(
            teacher=request.user,
            is_active=True,
            class_subject__is_active=True,
            class_subject__classroom__is_active=True,
            class_subject__subject__is_active=True,
        ).select_related('class_subject__classroom', 'class_subject__subject').annotate(
            total_weeks=Count('progress_rows'),
            completed_weeks=Count('progress_rows', filter=Q(progress_rows__status=TeacherCourseProgress.STATUS_COMPLETED)),
        )
        assignment_rows = []
        for assignment in assignments:
            total = assignment.total_weeks or 0
            completed = assignment.completed_weeks or 0
            assignment_rows.append({
                'assignment': assignment,
                'total': total,
                'completed': completed,
                'not_completed': max(total - completed, 0),
                'progress': _progress_percent(completed, total),
            })
        context = {
            'assignment_rows': assignment_rows,
            'pending_rows': TeacherCourseProgress.objects.filter(assignment__teacher=request.user, status=TeacherCourseProgress.STATUS_NOT_COMPLETED).count(),
            'completed_rows': TeacherCourseProgress.objects.filter(assignment__teacher=request.user, status=TeacherCourseProgress.STATUS_COMPLETED).count(),
        }
        return render(request, 'checker/teacher_dashboard.html', context)

    today = timezone.localdate()
    month_start = today.replace(day=1)
    context = {
        'today_locked': CopyCheckRecord.objects.filter(entered_by=request.user, locked=True, locked_at__date=today).count(),
        'month_locked': CopyCheckRecord.objects.filter(entered_by=request.user, locked=True, locked_at__date__gte=month_start).count(),
        'recent_records': CopyCheckRecord.objects.filter(entered_by=request.user).select_related(
            'student', 'class_subject__subject', 'chapter'
        )[:10],
        'attention_class_subjects': _attention_class_subject_rows(5),
        'attention_students': _attention_student_rows(5),
    }
    return render(request, 'checker/checker_dashboard.html', context)


@login_required
def attention_list(request):
    limit = 100 if is_app_admin(request.user) else 50
    context = {
        'limit': limit,
        'is_admin_view': is_app_admin(request.user),
        'class_subject_rows': _attention_class_subject_rows(limit),
        'student_rows': _attention_student_rows(limit),
    }
    return render(request, 'checker/attention_list.html', context)



@checker_required
def select_checking(request):
    form = SelectCheckForm(request.GET or None)

    class_subjects = ClassSubject.objects.filter(
        is_active=True,
        classroom__is_active=True,
        subject__is_active=True,
    ).select_related('classroom', 'subject').prefetch_related('chapters')

    selection_data = []
    for class_subject in class_subjects:
        selection_data.append({
            'classroom_id': str(class_subject.classroom_id),
            'class_subject_id': str(class_subject.id),
            'subject_name': class_subject.subject.name,
            'chapters': [
                {'id': str(chapter.id), 'title': chapter.title}
                for chapter in class_subject.chapters.filter(is_active=True).order_by('number')
            ],
        })

    if request.GET.get('classroom') and request.GET.get('class_subject') and request.GET.get('chapter') and form.is_valid():
        class_subject = form.cleaned_data['class_subject']
        chapter = form.cleaned_data['chapter']
        return redirect(f"{reverse('checking_list')}?class_subject={class_subject.id}&chapter={chapter.id}")

    return render(request, 'checker/select_checking.html', {
        'form': form,
        'selection_data': selection_data,
        'selected_classroom': request.GET.get('classroom', ''),
        'selected_class_subject': request.GET.get('class_subject', ''),
        'selected_chapter': request.GET.get('chapter', ''),
    })


@checker_required
def checking_list(request):
    class_subject = get_object_or_404(
        ClassSubject.objects.select_related('classroom', 'subject'),
        pk=request.GET.get('class_subject'),
        is_active=True,
    )
    chapter = get_object_or_404(ClassSubjectChapter, pk=request.GET.get('chapter'), class_subject=class_subject, is_active=True)
    classroom = class_subject.classroom

    students = Student.objects.filter(classroom=classroom, is_active=True).order_by('roll_no', 'full_name')
    existing = {
        record.student_id: record
        for record in CopyCheckRecord.objects.filter(
            student__in=students,
            class_subject=class_subject,
            chapter=chapter,
        ).select_related('student', 'entered_by', 'actual_checker_user', 'class_subject__subject', 'chapter')
    }
    rows = [{'student': student, 'record': existing.get(student.id), 'form': LockRecordForm()} for student in students]
    context = {
        'classroom': classroom,
        'class_subject': class_subject,
        'subject': class_subject.subject,
        'chapter': chapter,
        'rows': rows,
        'refresh_url': request.get_full_path(),
    }
    return render(request, 'checker/checking_list.html', context)


@checker_required
@require_POST
def lock_record(request):
    student = get_object_or_404(Student, pk=request.POST.get('student_id'), is_active=True)
    class_subject = get_object_or_404(
        ClassSubject.objects.select_related('classroom', 'subject'),
        pk=request.POST.get('class_subject_id'),
        is_active=True,
    )
    chapter = get_object_or_404(ClassSubjectChapter, pk=request.POST.get('chapter_id'), class_subject=class_subject, is_active=True)
    form = LockRecordForm(request.POST)
    next_url = request.POST.get('next') or reverse('select_checking')

    if student.classroom_id != class_subject.classroom_id:
        messages.error(request, 'This student does not belong to the selected class.')
        return redirect(next_url)

    if not form.is_valid():
        messages.error(request, 'Please check the row details and try again.')
        return redirect(next_url)

    with transaction.atomic():
        existing = CopyCheckRecord.objects.select_for_update().filter(student=student, chapter=chapter).first()
        if existing and existing.locked:
            messages.warning(request, f'{student.full_name} is already locked for this chapter.')
            return redirect(next_url)

        record = existing or CopyCheckRecord(
            student=student,
            classroom=student.classroom,
            class_subject=class_subject,
            chapter=chapter,
            entered_by=request.user,
        )
        record.classroom = student.classroom
        record.class_subject = class_subject
        record.chapter = chapter
        record.status = form.cleaned_data['status']
        record.remarks = form.cleaned_data['remarks']
        record.entered_by = request.user
        record.actual_checker_user = None
        record.actual_checker_name = form.cleaned_data['actual_checker_name']
        record.locked = True
        record.locked_at = timezone.now()
        try:
            record.save()
        except IntegrityError:
            messages.warning(request, f'{student.full_name} already has a record for this chapter.')
            return redirect(next_url)

        log_action(request.user, 'LOCK_RECORD', record, f'Locked {record}')

    ensure_daily_backup(reason='Checker locked a copy-checking record', user=request.user)
    messages.success(request, f'Locked record for {student.full_name}.')
    return redirect(next_url)


@checker_required
def request_correction(request, record_id):
    record = get_object_or_404(
        CopyCheckRecord.objects.select_related('student', 'class_subject__subject', 'chapter'),
        pk=record_id,
        locked=True,
    )
    if request.method == 'POST':
        form = CorrectionRequestForm(request.POST)
        if form.is_valid():
            correction = form.save(commit=False)
            correction.record = record
            correction.requested_by = request.user
            correction.save()
            log_action(request.user, 'REQUEST_CORRECTION', correction, f'Requested correction for {record}')
            messages.success(request, 'Correction request sent to admin.')
            return redirect('dashboard')
    else:
        form = CorrectionRequestForm(initial={
            'requested_status': record.status,
            'requested_remarks': record.remarks,
            'requested_actual_checker_name': record.actual_checker_name,
        })
    return render(request, 'checker/request_correction.html', {'form': form, 'record': record})


@app_admin_required
def class_list_admin(request):
    classes = ClassRoom.objects.filter(is_active=True).prefetch_related('class_subjects__subject', 'students')
    return render(request, 'checker/class_list_admin.html', {'classes': classes})


@app_admin_required
def class_setup(request, class_id=None):
    classroom = None
    if class_id:
        classroom = get_object_or_404(ClassRoom, pk=class_id)

    if request.method == 'POST':
        form = ClassSetupForm(request.POST, instance=classroom)
        subject_rows, subject_errors = _subject_rows_from_post(request)
        if not subject_errors:
            subject_errors.extend(_validate_class_subject_changes(classroom, subject_rows))
        if form.is_valid() and not subject_errors:
            with transaction.atomic():
                classroom = form.save()
                _sync_class_subjects(classroom, subject_rows)
                log_action(request.user, 'SAVE_CLASS_SETUP', classroom, f'Saved class setup for {classroom}')
            ensure_daily_backup(reason='Admin saved class setup', user=request.user)
            messages.success(request, 'Class and subject chapters saved.')
            return redirect('class_list_admin')
        for error in subject_errors:
            messages.error(request, error)
    else:
        form = ClassSetupForm(instance=classroom)
        if classroom:
            subject_rows = [
                {'name': item.subject.name, 'chapter_count': item.chapter_count}
                for item in classroom.class_subjects.filter(is_active=True).select_related('subject')
            ]
        else:
            subject_rows = []

    while len(subject_rows) < 8:
        subject_rows.append({'name': '', 'chapter_count': ''})

    return render(request, 'checker/class_setup.html', {
        'form': form,
        'classroom': classroom,
        'subject_rows': subject_rows,
    })


@app_admin_required
def student_create(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            try:
                student = form.save()
            except IntegrityError:
                messages.error(request, 'This roll number already exists in the selected class.')
            else:
                log_action(request.user, 'ADD_STUDENT', student, f'Added student {student}')
                ensure_daily_backup(reason='Admin added a student', user=request.user)
                messages.success(request, 'Student saved. The class subjects and chapters are assigned automatically through the class setup.')
                return redirect('student_list_admin')
    else:
        initial = {}
        if request.GET.get('classroom'):
            initial['classroom'] = request.GET.get('classroom')
        form = StudentForm(initial=initial)
    return render(request, 'checker/student_form.html', {'form': form})


@app_admin_required
def admin_records(request):
    records = CopyCheckRecord.objects.filter(locked=True).select_related(
        'student',
        'classroom',
        'class_subject__subject',
        'chapter',
        'entered_by',
        'actual_checker_user',
    ).order_by('-locked_at', '-id')[:50]
    return render(request, 'checker/admin_records.html', {'records': records})


@app_admin_required
def student_list_admin(request):
    students = Student.objects.filter(is_active=True).select_related('classroom')
    classroom_id = request.GET.get('classroom')
    q = request.GET.get('q')
    if classroom_id:
        students = students.filter(classroom_id=classroom_id)
    if q:
        students = students.filter(Q(full_name__icontains=q) | Q(roll_no__icontains=q))
    return render(request, 'checker/student_list_admin.html', {
        'students': students[:500],
        'classes': ClassRoom.objects.filter(is_active=True),
    })


def _cell_to_text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _read_student_import_rows(uploaded_file, classroom):
    valid_rows = []
    problem_rows = []
    seen_rolls = set()

    workbook = load_workbook(uploaded_file, read_only=True, data_only=True)
    sheet = workbook.active

    for row_number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        name = _cell_to_text(row[0] if len(row) > 0 else '')
        roll_no = _cell_to_text(row[1] if len(row) > 1 else '')

        if not name and not roll_no:
            continue

        problem = ''
        if not name:
            problem = 'Student name is missing.'
        elif not roll_no:
            problem = 'Roll no is missing.'
        elif roll_no in seen_rolls:
            problem = 'Duplicate roll no inside this Excel file.'
        elif Student.objects.filter(classroom=classroom, roll_no=roll_no).exists():
            problem = 'This roll no already exists in the selected class.'

        item = {'row_number': row_number, 'name': name, 'roll_no': roll_no}
        if problem:
            item['problem'] = problem
            problem_rows.append(item)
            continue

        seen_rolls.add(roll_no)
        valid_rows.append(item)

    return valid_rows, problem_rows


@app_admin_required
def student_import(request):
    preview = None
    result = None
    form = StudentImportUploadForm()

    if request.method == 'POST' and request.POST.get('confirm_import') == '1':
        classroom_id = request.session.get('student_import_classroom_id')
        valid_rows = request.session.get('student_import_valid_rows', [])
        classroom = get_object_or_404(ClassRoom, pk=classroom_id, is_active=True)

        imported = []
        skipped = []
        with transaction.atomic():
            for row in valid_rows:
                if Student.objects.filter(classroom=classroom, roll_no=row['roll_no']).exists():
                    skipped.append({**row, 'problem': 'This roll no already exists now, so it was not imported.'})
                    continue
                student = Student.objects.create(
                    classroom=classroom,
                    roll_no=row['roll_no'],
                    full_name=row['name'],
                )
                imported.append(student)
                log_action(request.user, 'IMPORT_STUDENT', student, f'Imported student {student}')

        request.session.pop('student_import_classroom_id', None)
        request.session.pop('student_import_valid_rows', None)
        request.session.pop('student_import_problem_rows', None)

        if imported:
            ensure_daily_backup(reason='Admin imported students', user=request.user)
            messages.success(request, f'Imported {len(imported)} student(s).')
        if skipped:
            messages.warning(request, f'{len(skipped)} row(s) were left for manual entry because of problems.')

        result = {'classroom': classroom, 'imported': imported, 'skipped': skipped}

    elif request.method == 'POST':
        form = StudentImportUploadForm(request.POST, request.FILES)
        if form.is_valid():
            classroom = form.cleaned_data['classroom']
            uploaded_file = form.cleaned_data['file']
            if not uploaded_file.name.lower().endswith('.xlsx'):
                messages.error(request, 'Please upload an .xlsx Excel file.')
            else:
                try:
                    valid_rows, problem_rows = _read_student_import_rows(uploaded_file, classroom)
                except Exception as exc:  # keep the UI clear instead of showing a traceback
                    messages.error(request, f'Could not read the Excel file: {exc}')
                else:
                    request.session['student_import_classroom_id'] = classroom.id
                    request.session['student_import_valid_rows'] = valid_rows
                    request.session['student_import_problem_rows'] = problem_rows
                    preview = {'classroom': classroom, 'valid_rows': valid_rows, 'problem_rows': problem_rows}
                    if not valid_rows:
                        messages.warning(request, 'No valid rows are ready for import. Check the problem rows below.')

    return render(request, 'checker/student_import.html', {
        'form': form,
        'preview': preview,
        'result': result,
    })


@login_required
def student_profile(request, student_id):
    student = get_object_or_404(Student.objects.select_related('classroom'), pk=student_id)
    subject_id = request.GET.get('subject')
    status = request.GET.get('status')

    class_subjects = ClassSubject.objects.filter(
        classroom=student.classroom,
        is_active=True,
        subject__is_active=True,
    ).select_related('subject')
    if subject_id:
        class_subjects = class_subjects.filter(subject_id=subject_id)

    chapters = list(ClassSubjectChapter.objects.filter(class_subject__in=class_subjects, is_active=True).select_related('class_subject__subject'))
    records = {
        record.chapter_id: record
        for record in student.copy_records.filter(chapter__in=chapters).select_related(
            'class_subject__subject', 'chapter', 'entered_by', 'actual_checker_user'
        )
    }

    rows = []
    for chapter in chapters:
        record = records.get(chapter.id)
        if status == PENDING_STATUS and record:
            continue
        if status and status != PENDING_STATUS:
            if not record or record.status != status:
                continue
        rows.append({
            'subject': chapter.class_subject.subject,
            'chapter': chapter,
            'record': record,
            'status_label': record.get_status_display() if record else 'Pending',
        })

    all_expected_count = ClassSubjectChapter.objects.filter(
        class_subject__classroom=student.classroom,
        class_subject__is_active=True,
        is_active=True,
    ).count()
    locked_count = student.copy_records.filter(locked=True).count()
    summary = {
        'total_expected': all_expected_count,
        'locked': locked_count,
        'pending': max(all_expected_count - locked_count, 0),
        'checked': student.copy_records.filter(status=CopyCheckRecord.STATUS_CHECKED).count(),
        'incomplete': student.copy_records.filter(status=CopyCheckRecord.STATUS_INCOMPLETE).count(),
        'not_submitted': student.copy_records.filter(status=CopyCheckRecord.STATUS_NOT_SUBMITTED).count(),
        'absent': student.copy_records.filter(status=CopyCheckRecord.STATUS_ABSENT).count(),
    }
    context = {
        'student': student,
        'rows': rows,
        'summary': summary,
        'subjects': Subject.objects.filter(class_subjects__classroom=student.classroom, class_subjects__is_active=True).distinct(),
        'status_choices': [(PENDING_STATUS, 'Pending')] + list(CopyCheckRecord.STATUS_CHOICES),
    }
    return render(request, 'checker/student_profile.html', context)


@app_admin_required
def correction_requests_admin(request):
    requests_qs = CorrectionRequest.objects.select_related(
        'record', 'record__student', 'record__class_subject__subject', 'record__chapter', 'requested_by'
    )
    status = request.GET.get('status') or CorrectionRequest.STATUS_PENDING
    if status:
        requests_qs = requests_qs.filter(status=status)
    return render(request, 'checker/correction_requests_admin.html', {
        'correction_requests': requests_qs[:300],
        'status': status,
        'status_choices': CorrectionRequest.STATUS_CHOICES,
    })


@app_admin_required
def review_correction_request(request, request_id):
    correction = get_object_or_404(CorrectionRequest.objects.select_related('record'), pk=request_id)
    record = correction.record
    if request.method == 'POST':
        form = AdminCorrectionReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            correction.admin_note = form.cleaned_data['admin_note']
            correction.reviewed_by = request.user
            correction.reviewed_at = timezone.now()

            if action == AdminCorrectionReviewForm.ACTION_UNLOCK:
                record.locked = False
                record.locked_at = None
                record.save(update_fields=['locked', 'locked_at', 'updated_at'])
                correction.status = CorrectionRequest.STATUS_APPROVED
                log_action(request.user, 'UNLOCK_RECORD', record, f'Unlocked record after correction request #{correction.pk}')
                messages.success(request, 'Record unlocked. Checker can now edit and lock it again.')

            elif action == AdminCorrectionReviewForm.ACTION_CORRECT:
                if form.cleaned_data['status']:
                    record.status = form.cleaned_data['status']
                record.remarks = form.cleaned_data['remarks']
                record.actual_checker_user = None
                record.actual_checker_name = form.cleaned_data['actual_checker_name']
                record.save(update_fields=['status', 'remarks', 'actual_checker_user', 'actual_checker_name', 'updated_at'])
                correction.status = CorrectionRequest.STATUS_APPROVED
                log_action(request.user, 'CORRECT_RECORD', record, f'Admin corrected record after request #{correction.pk}')
                messages.success(request, 'Correction applied by admin.')

            else:
                correction.status = CorrectionRequest.STATUS_REJECTED
                log_action(request.user, 'REJECT_CORRECTION', correction, f'Rejected correction request #{correction.pk}')
                messages.info(request, 'Correction request rejected.')

            correction.save()
            ensure_daily_backup(reason='Admin reviewed a correction request', user=request.user)
            return redirect('correction_requests_admin')
    else:
        form = AdminCorrectionReviewForm(initial={
            'action': AdminCorrectionReviewForm.ACTION_CORRECT,
            'status': correction.requested_status or record.status,
            'remarks': correction.requested_remarks or record.remarks,
            'actual_checker_name': correction.requested_actual_checker_name or record.actual_checker_name,
        })
    return render(request, 'checker/review_correction_request.html', {'correction': correction, 'record': record, 'form': form})


@app_admin_required
def admin_users(request):
    users = User.objects.select_related('checker_profile').order_by('username')
    return render(request, 'checker/admin_users.html', {'users': users})


@app_admin_required
def admin_user_edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    profile, _created = UserProfile.objects.get_or_create(user=user, defaults={'display_name': user.username})
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            user.is_active = profile.is_active_checker
            user.save(update_fields=['is_active'])
            log_action(request.user, 'EDIT_USER_PROFILE', profile, f'Edited profile for {user.username}')
            messages.success(request, 'User details updated.')
            return redirect('admin_users')
    else:
        form = UserProfileForm(instance=profile)
    return render(request, 'checker/admin_user_edit.html', {'form': form, 'edited_user': user})


@app_admin_required
def admin_user_reset_password(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    profile, _created = UserProfile.objects.get_or_create(user=user, defaults={'display_name': user.username})
    if request.method == 'POST':
        form = PasswordResetByAdminForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['new_password']
            user.set_password(password)
            user.save(update_fields=['password'])
            if form.cleaned_data['keep_visible_note']:
                profile.initial_password_note = password
                profile.save(update_fields=['initial_password_note'])
            log_action(request.user, 'RESET_PASSWORD', profile, f'Reset password for {user.username}')
            messages.success(request, 'Password reset successfully.')
            return redirect('admin_users')
    else:
        form = PasswordResetByAdminForm()
    return render(request, 'checker/admin_user_reset_password.html', {'form': form, 'edited_user': user})


@app_admin_required
def backups_admin(request):
    backups = DailyBackup.objects.select_related('triggered_by')[:50]
    return render(request, 'checker/backups_admin.html', {'backups': backups})


@app_admin_required
@require_POST
def backup_now(request):
    backup = ensure_daily_backup(reason='Manual admin backup', user=request.user)
    if not backup:
        messages.error(request, 'Backup could not be created.')
        return redirect('backups_admin')
    path = get_backup_path(backup)
    if not path.exists():
        messages.error(request, 'Backup record was created, but the file is not available on this server.')
        return redirect('backups_admin')
    return FileResponse(path.open('rb'), as_attachment=True, filename=backup.file_name)


@app_admin_required
def backup_download(request, backup_id):
    backup = get_object_or_404(DailyBackup, pk=backup_id)
    path = get_backup_path(backup)
    if not path.exists():
        raise Http404('Backup file is not available on this server.')
    return FileResponse(path.open('rb'), as_attachment=True, filename=backup.file_name)


def _assignment_summary(assignment):
    total = assignment.progress_rows.count()
    completed = assignment.progress_rows.filter(status=TeacherCourseProgress.STATUS_COMPLETED).count()
    not_completed = max(total - completed, 0)
    return {
        'assignment': assignment,
        'total': total,
        'completed': completed,
        'not_completed': not_completed,
        'progress': _progress_percent(completed, total),
    }


@app_admin_required
def admin_user_create(request):
    if request.method == 'POST':
        form = UserCreateByAdminForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                is_active=form.cleaned_data['is_active'],
            )
            profile = UserProfile.objects.create(
                user=user,
                display_name=form.cleaned_data['display_name'],
                role=form.cleaned_data['role'],
                initial_password_note=form.cleaned_data['password'],
                is_active_checker=form.cleaned_data['is_active'],
            )
            log_action(request.user, 'CREATE_USER', profile, f'Created {profile.get_role_display()} user {user.username}')
            ensure_daily_backup(reason='Admin created a user', user=request.user)
            messages.success(request, 'User created successfully.')
            return redirect('admin_users')
    else:
        form = UserCreateByAdminForm()
    return render(request, 'checker/admin_user_create.html', {'form': form})


@teacher_required
def teacher_course_detail(request, assignment_id):
    assignment = get_object_or_404(
        TeacherCourseAssignment.objects.select_related('class_subject__classroom', 'class_subject__subject'),
        pk=assignment_id,
        teacher=request.user,
        is_active=True,
    )
    if request.method == 'POST':
        form = TeacherProgressForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                last_week = TeacherCourseProgress.objects.select_for_update().filter(assignment=assignment).aggregate(max_week=Max('week_no'))['max_week'] or 0
                progress = form.save(commit=False)
                progress.assignment = assignment
                progress.week_no = last_week + 1
                progress.status = TeacherCourseProgress.STATUS_NOT_COMPLETED
                progress.locked = False
                progress.save()
                log_action(request.user, 'ADD_TEACHER_PROGRESS', progress, f'Added week {progress.week_no} for {assignment}')
            ensure_daily_backup(reason='Teacher added course progress', user=request.user)
            messages.success(request, f'Week {progress.week_no} added.')
            return redirect('teacher_course_detail', assignment_id=assignment.id)
    else:
        form = TeacherProgressForm()

    rows = assignment.progress_rows.all()
    return render(request, 'checker/teacher_course_detail.html', {
        'assignment': assignment,
        'rows': rows,
        'form': form,
        'summary': _assignment_summary(assignment),
    })


@teacher_required
def teacher_progress_edit(request, progress_id):
    progress = get_object_or_404(
        TeacherCourseProgress.objects.select_related('assignment__class_subject__classroom', 'assignment__class_subject__subject'),
        pk=progress_id,
        assignment__teacher=request.user,
    )
    if not progress.can_edit:
        messages.error(request, 'Completed rows are locked and cannot be edited. Ask admin if a correction is needed.')
        return redirect('teacher_course_detail', assignment_id=progress.assignment_id)
    if request.method == 'POST':
        form = TeacherProgressForm(request.POST, instance=progress)
        if form.is_valid():
            form.save()
            log_action(request.user, 'EDIT_TEACHER_PROGRESS', progress, f'Edited week {progress.week_no}')
            ensure_daily_backup(reason='Teacher edited course progress', user=request.user)
            messages.success(request, 'Week detail updated.')
            return redirect('teacher_course_detail', assignment_id=progress.assignment_id)
    else:
        form = TeacherProgressForm(instance=progress)
    return render(request, 'checker/teacher_progress_edit.html', {'form': form, 'progress': progress})


@teacher_required
@require_POST
def teacher_progress_delete(request, progress_id):
    progress = get_object_or_404(TeacherCourseProgress, pk=progress_id, assignment__teacher=request.user)
    assignment_id = progress.assignment_id
    if not progress.can_edit:
        messages.error(request, 'Completed rows are locked and cannot be deleted.')
        return redirect('teacher_course_detail', assignment_id=assignment_id)
    label = f'Week {progress.week_no}'
    log_action(request.user, 'DELETE_TEACHER_PROGRESS', progress, f'Deleted {label}')
    progress.delete()
    ensure_daily_backup(reason='Teacher deleted unlocked progress row', user=request.user)
    messages.success(request, f'{label} deleted.')
    return redirect('teacher_course_detail', assignment_id=assignment_id)


@teacher_required
@require_POST
def teacher_progress_complete(request, progress_id):
    progress = get_object_or_404(TeacherCourseProgress, pk=progress_id, assignment__teacher=request.user)
    if not progress.can_edit:
        messages.info(request, 'This row is already completed/locked.')
        return redirect('teacher_course_detail', assignment_id=progress.assignment_id)
    progress.status = TeacherCourseProgress.STATUS_COMPLETED
    progress.save(update_fields=['status', 'locked', 'completed_at', 'updated_at'])
    log_action(request.user, 'COMPLETE_TEACHER_PROGRESS', progress, f'Completed week {progress.week_no}')
    ensure_daily_backup(reason='Teacher completed a progress row', user=request.user)
    messages.success(request, f'Week {progress.week_no} marked completed and locked.')
    return redirect('teacher_course_detail', assignment_id=progress.assignment_id)


@app_admin_required
def teacher_assignments_admin(request):
    if request.method == 'POST':
        form = TeacherCourseAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save()
            log_action(request.user, 'SAVE_TEACHER_ASSIGNMENT', assignment, f'Saved teacher assignment {assignment}')
            ensure_daily_backup(reason='Admin saved teacher assignment', user=request.user)
            messages.success(request, 'Teacher assignment saved.')
            return redirect('teacher_assignments_admin')
    else:
        form = TeacherCourseAssignmentForm()

    assignments = TeacherCourseAssignment.objects.select_related(
        'teacher__checker_profile', 'class_subject__classroom', 'class_subject__subject'
    ).order_by('class_subject__classroom__name', 'class_subject__classroom__section', 'class_subject__subject__name')
    return render(request, 'checker/teacher_assignments_admin.html', {'form': form, 'assignments': assignments})


@app_admin_required
@require_POST
def teacher_assignment_deactivate(request, assignment_id):
    assignment = get_object_or_404(TeacherCourseAssignment, pk=assignment_id)
    assignment.is_active = False
    assignment.save(update_fields=['is_active', 'updated_at'])
    log_action(request.user, 'DEACTIVATE_TEACHER_ASSIGNMENT', assignment, f'Deactivated {assignment}')
    ensure_daily_backup(reason='Admin deactivated teacher assignment', user=request.user)
    messages.success(request, 'Teacher assignment deactivated.')
    return redirect('teacher_assignments_admin')


@app_admin_required
def teacher_progress_classes_admin(request):
    classes = ClassRoom.objects.filter(is_active=True).annotate(
        assignment_count=Count('class_subjects__teacher_assignments', filter=Q(class_subjects__teacher_assignments__is_active=True)),
    ).order_by('name', 'section')
    return render(request, 'checker/teacher_progress_classes_admin.html', {'classes': classes})


@app_admin_required
def teacher_progress_class_detail_admin(request, class_id):
    classroom = get_object_or_404(ClassRoom, pk=class_id)
    assignments = TeacherCourseAssignment.objects.filter(
        class_subject__classroom=classroom,
        is_active=True,
    ).select_related('teacher__checker_profile', 'class_subject__classroom', 'class_subject__subject')
    rows = [_assignment_summary(assignment) for assignment in assignments]
    return render(request, 'checker/teacher_progress_class_detail_admin.html', {'classroom': classroom, 'rows': rows})


@app_admin_required
def teacher_progress_teachers_admin(request):
    teachers = User.objects.filter(
        checker_profile__role=UserProfile.ROLE_TEACHER,
        checker_profile__is_active_checker=True,
    ).select_related('checker_profile').annotate(
        assignment_count=Count('teacher_course_assignments', filter=Q(teacher_course_assignments__is_active=True)),
    ).order_by('checker_profile__display_name', 'username')
    return render(request, 'checker/teacher_progress_teachers_admin.html', {'teachers': teachers})


@app_admin_required
def teacher_progress_teacher_detail_admin(request, user_id):
    teacher = get_object_or_404(User.objects.select_related('checker_profile'), pk=user_id, checker_profile__role=UserProfile.ROLE_TEACHER)
    assignments = TeacherCourseAssignment.objects.filter(
        teacher=teacher,
        is_active=True,
    ).select_related('teacher__checker_profile', 'class_subject__classroom', 'class_subject__subject')
    rows = [_assignment_summary(assignment) for assignment in assignments]
    return render(request, 'checker/teacher_progress_teacher_detail_admin.html', {'teacher': teacher, 'rows': rows})


@app_admin_required
def teacher_progress_assignment_detail_admin(request, assignment_id):
    assignment = get_object_or_404(
        TeacherCourseAssignment.objects.select_related('teacher__checker_profile', 'class_subject__classroom', 'class_subject__subject'),
        pk=assignment_id,
    )
    rows = assignment.progress_rows.all()
    return render(request, 'checker/teacher_progress_assignment_detail_admin.html', {
        'assignment': assignment,
        'rows': rows,
        'summary': _assignment_summary(assignment),
    })


@app_admin_required
def teacher_progress_row_edit_admin(request, progress_id):
    progress = get_object_or_404(
        TeacherCourseProgress.objects.select_related(
            'assignment__teacher__checker_profile',
            'assignment__class_subject__classroom',
            'assignment__class_subject__subject',
        ),
        pk=progress_id,
    )
    if request.method == 'POST':
        form = AdminTeacherProgressEditForm(request.POST)
        if form.is_valid():
            old_detail = progress.detail
            old_status = progress.status
            progress.detail = form.cleaned_data['detail']
            progress.status = form.cleaned_data['status']
            progress.save(update_fields=['detail', 'status', 'locked', 'completed_at', 'updated_at'])
            note = form.cleaned_data.get('admin_note') or ''
            log_action(
                request.user,
                'ADMIN_EDIT_TEACHER_PROGRESS',
                progress,
                f'Admin edited week {progress.week_no}. Old status: {old_status}. New status: {progress.status}. Note: {note}. Old detail: {old_detail[:120]}',
            )
            ensure_daily_backup(reason='Admin edited teacher progress row', user=request.user)
            messages.success(request, 'Teacher progress row updated by admin.')
            return redirect('teacher_progress_assignment_detail_admin', assignment_id=progress.assignment_id)
    else:
        form = AdminTeacherProgressEditForm(initial={
            'detail': progress.detail,
            'status': progress.status,
        })
    return render(request, 'checker/teacher_progress_row_edit_admin.html', {
        'form': form,
        'progress': progress,
        'assignment': progress.assignment,
    })


