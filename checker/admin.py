from django.contrib import admin

from .models import (
    ActionLog,
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
    TeacherProgressCorrectionRequest,
    UserProfile,
)


class ClassSubjectChapterInline(admin.TabularInline):
    model = ClassSubjectChapter
    extra = 0
    fields = ('number', 'is_active')


class ClassSubjectInline(admin.TabularInline):
    model = ClassSubject
    extra = 1
    fields = ('subject', 'chapter_count', 'is_active')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'role', 'is_active_checker', 'initial_password_note')
    list_filter = ('role', 'is_active_checker')
    search_fields = ('display_name', 'user__username')


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'section', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'section')
    inlines = [ClassSubjectInline]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('roll_no', 'full_name', 'classroom', 'is_active')
    list_filter = ('classroom', 'is_active')
    search_fields = ('full_name', 'roll_no')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(ClassSubject)
class ClassSubjectAdmin(admin.ModelAdmin):
    list_display = ('classroom', 'subject', 'chapter_count', 'is_active')
    list_filter = ('classroom', 'subject', 'is_active')
    search_fields = ('classroom__name', 'classroom__section', 'subject__name')
    inlines = [ClassSubjectChapterInline]


@admin.register(ClassSubjectChapter)
class ClassSubjectChapterAdmin(admin.ModelAdmin):
    list_display = ('class_subject', 'number', 'is_active')
    list_filter = ('class_subject__classroom', 'class_subject__subject', 'is_active')
    search_fields = ('class_subject__classroom__name', 'class_subject__subject__name')


@admin.register(CopyCheckRecord)
class CopyCheckRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'classroom', 'subject_name', 'chapter', 'status', 'entered_by', 'actual_checker_name', 'locked', 'locked_at')
    list_filter = ('classroom', 'class_subject__subject', 'status', 'locked')
    search_fields = ('student__full_name', 'student__roll_no', 'remarks', 'actual_checker_name')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Subject')
    def subject_name(self, obj):
        return obj.subject.name


@admin.register(CorrectionRequest)
class CorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ('record', 'requested_by', 'status', 'created_at', 'reviewed_by')
    list_filter = ('status',)
    search_fields = ('record__student__full_name', 'reason', 'admin_note')


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'model_name', 'object_id')
    search_fields = ('action', 'description', 'actor__username')
    readonly_fields = ('actor', 'action', 'model_name', 'object_id', 'description', 'created_at')


@admin.register(DailyBackup)
class DailyBackupAdmin(admin.ModelAdmin):
    list_display = ('backup_date', 'file_name', 'reason', 'triggered_by', 'updated_at')
    readonly_fields = ('backup_date', 'file_name', 'reason', 'triggered_by', 'created_at', 'updated_at')


@admin.register(TeacherCourseAssignment)
class TeacherCourseAssignmentAdmin(admin.ModelAdmin):
    list_display = ('class_subject', 'teacher', 'is_active', 'updated_at')
    list_filter = ('is_active', 'class_subject__classroom', 'class_subject__subject')
    search_fields = ('teacher__username', 'teacher__checker_profile__display_name', 'class_subject__classroom__name', 'class_subject__subject__name')


@admin.register(TeacherCourseProgress)
class TeacherCourseProgressAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'week_no', 'status', 'locked', 'updated_at')
    list_filter = ('status', 'locked', 'assignment__class_subject__classroom', 'assignment__class_subject__subject')
    search_fields = ('detail', 'assignment__teacher__username', 'assignment__class_subject__subject__name')
    readonly_fields = ('created_at', 'updated_at', 'completed_at')


@admin.register(TeacherProgressCorrectionRequest)
class TeacherProgressCorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ('progress', 'requested_by', 'status', 'created_at', 'reviewed_by')
    list_filter = ('status',)
    search_fields = ('progress__detail', 'requested_detail', 'reason', 'admin_note')
