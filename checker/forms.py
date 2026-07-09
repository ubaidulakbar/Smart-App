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


class LockRecordForm(forms.Form):
    status = forms.ChoiceField(choices=CopyCheckRecord.STATUS_CHOICES, initial=CopyCheckRecord.STATUS_COMPLETE)
    remarks = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False, label='Details')
    actual_checker_name = forms.CharField(
        max_length=120,
        required=False,
        label='Actual checker name if different',
        help_text='Leave blank when the logged-in checker did the checking.',
    )

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get('status')
        remarks = (cleaned.get('remarks') or '').strip()
        if status == CopyCheckRecord.STATUS_INCOMPLETE and not remarks:
            self.add_error('remarks', 'Details are required when status is Incomplete.')
        cleaned['remarks'] = remarks
        return cleaned


class BackupUploadForm(forms.Form):
    file = forms.FileField(label='JSON backup file')

    def clean_file(self):
        uploaded = self.cleaned_data['file']
        if not uploaded.name.lower().endswith('.json'):
            raise forms.ValidationError('Upload the JSON backup file created by this app.')
        return uploaded


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
        self.fields['teacher'].label_from_instance = self._teacher_label
        self.fields['class_subject'].label_from_instance = self._class_subject_label

    @staticmethod
    def _teacher_label(user):
        profile = getattr(user, 'checker_profile', None)
        display = profile.display_name if profile else user.username
        return f'{display} (@{user.username})'

    @staticmethod
    def _class_subject_label(class_subject):
        return f'{class_subject.classroom} - {class_subject.subject.name}'

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


class TeacherCompleteForm(forms.Form):
    detail = forms.CharField(
        label='Week detail',
        widget=forms.Textarea(attrs={'rows': 3}),
        required=True,
        error_messages={'required': 'Please enter detail before marking this week as completed.'},
    )


class IssueWeekForm(forms.Form):
    admin_detail = forms.CharField(
        label='Admin detail for teachers',
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Optional note/instruction for teachers for this issued week...',
        }),
        help_text='This note will be visible to teachers on their pending/completed week rows.',
    )


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
    admin_detail = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label='Admin detail for teacher')
    detail = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label='Teacher week detail')
    status = forms.ChoiceField(choices=TeacherCourseProgress.STATUS_CHOICES)
    admin_note = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label='Admin edit note')
