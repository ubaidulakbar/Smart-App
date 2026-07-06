from django import forms
from django.contrib.auth.models import User
from django.db.models import Q

from .models import (
    ClassRoom,
    ClassSubject,
    ClassSubjectChapter,
    CopyCheckRecord,
    CorrectionRequest,
    Student,
    TeacherCourseAssignment,
    TeacherCourseProgress,
    TeacherProgressCorrectionRequest,
    UserProfile,
)


class SelectCheckForm(forms.Form):
    classroom = forms.ModelChoiceField(queryset=ClassRoom.objects.filter(is_active=True), label='Class / Section')
    class_subject = forms.ModelChoiceField(queryset=ClassSubject.objects.none(), label='Subject')
    chapter = forms.ModelChoiceField(queryset=ClassSubjectChapter.objects.none(), label='Chapter')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        classroom_id = self.data.get('classroom') or self.initial.get('classroom')
        class_subject_id = self.data.get('class_subject') or self.initial.get('class_subject')

        if classroom_id:
            self.fields['class_subject'].queryset = ClassSubject.objects.filter(
                classroom_id=classroom_id,
                is_active=True,
                subject__is_active=True,
            ).select_related('subject', 'classroom')
        else:
            self.fields['class_subject'].queryset = ClassSubject.objects.filter(
                is_active=True,
                subject__is_active=True,
            ).select_related('subject', 'classroom')

        if class_subject_id:
            self.fields['chapter'].queryset = ClassSubjectChapter.objects.filter(
                class_subject_id=class_subject_id,
                is_active=True,
            )
        else:
            self.fields['chapter'].queryset = ClassSubjectChapter.objects.none()

    def clean(self):
        cleaned = super().clean()
        classroom = cleaned.get('classroom')
        class_subject = cleaned.get('class_subject')
        chapter = cleaned.get('chapter')
        if classroom and class_subject and class_subject.classroom_id != classroom.id:
            self.add_error('class_subject', 'This subject is not assigned to the selected class.')
        if class_subject and chapter and chapter.class_subject_id != class_subject.id:
            self.add_error('chapter', 'This chapter is not assigned to the selected subject.')
        return cleaned


class LockRecordForm(forms.Form):
    status = forms.ChoiceField(choices=CopyCheckRecord.STATUS_CHOICES)
    remarks = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    actual_checker_name = forms.CharField(
        max_length=120,
        required=False,
        label='Actual checker name if different',
        help_text='Leave blank when the logged-in checker did the checking.',
    )


class CorrectionRequestForm(forms.ModelForm):
    class Meta:
        model = CorrectionRequest
        fields = ['reason', 'requested_status', 'requested_remarks', 'requested_actual_checker_name']
        labels = {
            'requested_status': 'New status',
            'requested_remarks': 'New remarks',
            'requested_actual_checker_name': 'New actual checker name if different',
        }
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 3}),
            'requested_remarks': forms.Textarea(attrs={'rows': 3}),
        }


class AdminCorrectionReviewForm(forms.Form):
    ACTION_CORRECT = 'correct'
    ACTION_UNLOCK = 'unlock'
    ACTION_REJECT = 'reject'
    ACTION_CHOICES = [
        (ACTION_CORRECT, 'Approve and apply requested values'),
        (ACTION_UNLOCK, 'Approve and unlock only'),
        (ACTION_REJECT, 'Reject request'),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES)
    status = forms.ChoiceField(choices=CopyCheckRecord.STATUS_CHOICES, required=False)
    remarks = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    actual_checker_name = forms.CharField(max_length=120, required=False, label='Actual checker name if different')
    admin_note = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)


class PasswordResetByAdminForm(forms.Form):
    new_password = forms.CharField(widget=forms.TextInput, min_length=4)
    keep_visible_note = forms.BooleanField(required=False, initial=True, help_text='Store this password as an admin-only note.')


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['display_name', 'role', 'is_active_checker']
        labels = {
            'is_active_checker': 'Active user',
        }


class UserDeleteConfirmForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label='Yes, I am sure I want to delete this user',
    )


class UserCreateByAdminForm(forms.Form):
    username = forms.CharField(max_length=150)
    display_name = forms.CharField(max_length=120)
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES)
    password = forms.CharField(widget=forms.TextInput, min_length=4)
    is_active = forms.BooleanField(required=False, initial=True, label='Active user')

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username already exists.')
        return username


class ClassSetupForm(forms.ModelForm):
    class Meta:
        model = ClassRoom
        fields = ['name', 'section', 'is_active']
        labels = {'name': 'Class name', 'section': 'Section'}


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['classroom', 'roll_no', 'full_name', 'is_active']
        labels = {'full_name': 'Student name'}


class StudentImportUploadForm(forms.Form):
    classroom = forms.ModelChoiceField(queryset=ClassRoom.objects.filter(is_active=True), label='Class / Section')
    file = forms.FileField(label='Excel file (.xlsx)')


class TeacherCourseAssignmentForm(forms.ModelForm):
    class Meta:
        model = TeacherCourseAssignment
        fields = ['teacher', 'class_subject', 'is_active']
        labels = {
            'teacher': 'Teacher',
            'class_subject': 'Class / Subject',
            'is_active': 'Active assignment',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].queryset = User.objects.filter(
            is_active=True,
            checker_profile__role=UserProfile.ROLE_TEACHER,
            checker_profile__is_active_checker=True,
        ).select_related('checker_profile').order_by('checker_profile__display_name', 'username')
        self.fields['class_subject'].queryset = ClassSubject.objects.filter(
            is_active=True,
            classroom__is_active=True,
            subject__is_active=True,
        ).select_related('classroom', 'subject').order_by('classroom__name', 'classroom__section', 'subject__name')

    def clean(self):
        cleaned = super().clean()
        class_subject = cleaned.get('class_subject')
        is_active = cleaned.get('is_active')
        qs = TeacherCourseAssignment.objects.filter(class_subject=class_subject, is_active=True)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if class_subject and is_active and qs.exists():
            raise forms.ValidationError('This class-subject already has an active teacher. Deactivate the old assignment first.')
        return cleaned


class TeacherProgressForm(forms.ModelForm):
    class Meta:
        model = TeacherCourseProgress
        fields = ['detail']
        labels = {'detail': 'Week detail'}
        widgets = {'detail': forms.Textarea(attrs={'rows': 3})}


class TeacherProgressCorrectionRequestForm(forms.ModelForm):
    class Meta:
        model = TeacherProgressCorrectionRequest
        fields = ['reason', 'requested_detail', 'requested_status']
        labels = {
            'requested_detail': 'New week detail',
            'requested_status': 'New status',
        }
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 3}),
            'requested_detail': forms.Textarea(attrs={'rows': 3}),
        }


class AdminTeacherProgressCorrectionReviewForm(forms.Form):
    ACTION_APPLY = 'apply'
    ACTION_REJECT = 'reject'
    ACTION_CHOICES = [
        (ACTION_APPLY, 'Approve and apply requested values'),
        (ACTION_REJECT, 'Reject request'),
    ]
    action = forms.ChoiceField(choices=ACTION_CHOICES)
    detail = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    status = forms.ChoiceField(choices=TeacherCourseProgress.STATUS_CHOICES, required=False)
    admin_note = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)


class AdminTeacherProgressEditForm(forms.Form):
    detail = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label='Week detail')
    status = forms.ChoiceField(choices=TeacherCourseProgress.STATUS_CHOICES)
    admin_note = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label='Admin note')
