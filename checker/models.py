from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_CHECKER = 'checker'
    ROLE_TEACHER = 'teacher'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_CHECKER, 'Checker'),
        (ROLE_TEACHER, 'Teacher'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='checker_profile')
    display_name = models.CharField(max_length=120)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CHECKER)
    # Admin-only note for the initial/demo password. Real login passwords are hashed by Django.
    initial_password_note = models.CharField(max_length=120, blank=True)
    is_active_checker = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return f'{self.display_name} ({self.get_role_display()})'


class ClassRoom(models.Model):
    name = models.CharField(max_length=80)
    section = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name', 'section']
        constraints = [
            models.UniqueConstraint(fields=['name', 'section'], name='unique_class_section')
        ]

    def __str__(self):
        return f'{self.name} - {self.section}' if self.section else self.name


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ClassSubject(models.Model):
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='class_subjects')
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='class_subjects')
    chapter_count = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['classroom__name', 'classroom__section', 'subject__name']
        constraints = [
            models.UniqueConstraint(fields=['classroom', 'subject'], name='unique_subject_per_class')
        ]

    def __str__(self):
        return f'{self.classroom} - {self.subject.name}'


class ClassSubjectChapter(models.Model):
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='chapters')
    number = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['class_subject__classroom__name', 'class_subject__classroom__section', 'class_subject__subject__name', 'number']
        constraints = [
            models.UniqueConstraint(fields=['class_subject', 'number'], name='unique_chapter_number_per_class_subject')
        ]

    @property
    def title(self):
        return f'Chapter {self.number}'

    @property
    def subject(self):
        return self.class_subject.subject

    @property
    def classroom(self):
        return self.class_subject.classroom

    def __str__(self):
        return f'{self.class_subject.classroom} - {self.class_subject.subject.name} - Chapter {self.number}'


class Student(models.Model):
    classroom = models.ForeignKey(ClassRoom, on_delete=models.PROTECT, related_name='students')
    roll_no = models.CharField(max_length=30)
    full_name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['classroom__name', 'classroom__section', 'roll_no', 'full_name']
        constraints = [
            models.UniqueConstraint(fields=['classroom', 'roll_no'], name='unique_roll_no_per_class')
        ]

    def __str__(self):
        return f'{self.roll_no} - {self.full_name}'


class CopyCheckRecord(models.Model):
    STATUS_COMPLETE = 'complete'
    STATUS_INCOMPLETE = 'incomplete'
    # Legacy status names are kept as aliases so old data/backups do not break.
    STATUS_CHECKED = STATUS_COMPLETE
    STATUS_NOT_CHECKED = 'not_checked'
    STATUS_ABSENT = 'absent'
    STATUS_NOT_SUBMITTED = 'not_submitted'
    STATUS_CHOICES = [
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_INCOMPLETE, 'Incomplete'),
    ]

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='copy_records')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.PROTECT, related_name='copy_records')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.PROTECT, related_name='copy_records')
    # Legacy chapter field. New checking records do not use chapters.
    chapter = models.ForeignKey(
        ClassSubjectChapter,
        on_delete=models.PROTECT,
        related_name='copy_records',
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_COMPLETE)
    remarks = models.TextField(blank=True)

    entered_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='entered_copy_records')
    actual_checker_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='actual_copy_records',
        help_text='Use this when the actual checker has a login account.',
    )
    actual_checker_name = models.CharField(
        max_length=120,
        blank=True,
        help_text='Use this when someone else checked the copy or has no login account.',
    )

    locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-locked_at', '-created_at', 'student__full_name']

    @property
    def subject(self):
        return self.class_subject.subject

    def save(self, *args, **kwargs):
        if self.student_id and not self.classroom_id:
            self.classroom = self.student.classroom
        if self.chapter_id and not self.class_subject_id:
            self.class_subject = self.chapter.class_subject
        if self.locked and self.locked_at is None:
            self.locked_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def actual_checker_display(self):
        if self.actual_checker_user_id:
            profile = getattr(self.actual_checker_user, 'checker_profile', None)
            if profile:
                return profile.display_name
            return self.actual_checker_user.username
        if self.actual_checker_name:
            return self.actual_checker_name
        profile = getattr(self.entered_by, 'checker_profile', None)
        if profile:
            return profile.display_name
        return self.entered_by.username

    def __str__(self):
        return f'{self.student.full_name} | {self.subject.name} | {self.get_status_display()}'


class CorrectionRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    record = models.ForeignKey(CopyCheckRecord, on_delete=models.CASCADE, related_name='correction_requests')
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='correction_requests')
    reason = models.TextField()
    requested_status = models.CharField(max_length=30, choices=CopyCheckRecord.STATUS_CHOICES, blank=True)
    requested_remarks = models.TextField(blank=True)
    requested_actual_checker_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='reviewed_correction_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.record} - {self.get_status_display()}'


class TeacherCourseAssignment(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.PROTECT, related_name='teacher_course_assignments')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.PROTECT, related_name='teacher_assignments')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['class_subject__classroom__name', 'class_subject__classroom__section', 'class_subject__subject__name']
        constraints = [
            models.UniqueConstraint(
                fields=['class_subject'],
                condition=models.Q(is_active=True),
                name='unique_active_teacher_per_class_subject',
            )
        ]

    @property
    def classroom(self):
        return self.class_subject.classroom

    @property
    def subject(self):
        return self.class_subject.subject

    @property
    def teacher_display(self):
        profile = getattr(self.teacher, 'checker_profile', None)
        if profile:
            return profile.display_name
        return self.teacher.username

    def __str__(self):
        return f'{self.classroom} - {self.subject.name} - {self.teacher_display}'


class TeacherCourseProgress(models.Model):
    STATUS_NOT_COMPLETED = 'not_completed'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_NOT_COMPLETED, 'Not Completed'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    assignment = models.ForeignKey(TeacherCourseAssignment, on_delete=models.PROTECT, related_name='progress_rows')
    week_no = models.PositiveIntegerField()
    admin_detail = models.TextField(blank=True)
    detail = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_NOT_COMPLETED)
    locked = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['assignment__class_subject__classroom__name', 'assignment__class_subject__classroom__section', 'assignment__class_subject__subject__name', 'week_no']
        constraints = [
            models.UniqueConstraint(fields=['assignment', 'week_no'], name='unique_week_no_per_teacher_course')
        ]

    @property
    def can_edit(self):
        return self.status == self.STATUS_NOT_COMPLETED and not self.locked

    def save(self, *args, **kwargs):
        if self.status == self.STATUS_COMPLETED:
            self.locked = True
            if self.completed_at is None:
                self.completed_at = timezone.now()
        elif self.status == self.STATUS_NOT_COMPLETED:
            self.locked = False
            self.completed_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.assignment} - Week {self.week_no}'


class TeacherProgressCorrectionRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    progress = models.ForeignKey(TeacherCourseProgress, on_delete=models.CASCADE, related_name='correction_requests')
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='teacher_progress_correction_requests')
    reason = models.TextField()
    requested_detail = models.TextField()
    requested_status = models.CharField(max_length=30, choices=TeacherCourseProgress.STATUS_CHOICES, default=TeacherCourseProgress.STATUS_NOT_COMPLETED)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='reviewed_teacher_progress_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.progress} - {self.get_status_display()}'


class ActionLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=80)
    model_name = models.CharField(max_length=80, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} @ {self.created_at:%Y-%m-%d %H:%M}'


class DailyBackup(models.Model):
    backup_date = models.DateField(unique=True)
    file_name = models.CharField(max_length=255)
    reason = models.CharField(max_length=200, blank=True)
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-backup_date']

    def __str__(self):
        return f'{self.backup_date} - {self.file_name}'
