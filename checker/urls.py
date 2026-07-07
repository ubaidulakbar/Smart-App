from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('attention/', views.attention_list, name='attention_list'),
    path('checking-side/', views.admin_checking_side, name='admin_checking_side'),
    path('teaching-side/', views.admin_teaching_side, name='admin_teaching_side'),
    path('delete-data/', views.delete_data_admin, name='delete_data_admin'),

    path('check/select/', views.select_checking, name='select_checking'),
    path('check/list/', views.checking_list, name='checking_list'),
    path('check/lock/', views.lock_record, name='lock_record'),
    path('check/record/<int:record_id>/request-correction/', views.request_correction, name='request_correction'),

    path('teacher/quick-update/', views.teacher_quick_update, name='teacher_quick_update'),
    path('teacher/course/<int:assignment_id>/', views.teacher_course_detail, name='teacher_course_detail'),
    path('teacher/progress/<int:progress_id>/edit/', views.teacher_progress_edit, name='teacher_progress_edit'),
    path('teacher/progress/<int:progress_id>/delete/', views.teacher_progress_delete, name='teacher_progress_delete'),
    path('teacher/progress/<int:progress_id>/complete/', views.teacher_progress_complete, name='teacher_progress_complete'),

    path('classes/', views.class_list_admin, name='class_list_admin'),
    path('classes/add/', views.class_setup, name='class_setup_add'),
    path('classes/<int:class_id>/edit/', views.class_setup, name='class_setup_edit'),
    path('students/add/', views.student_create, name='student_create'),
    path('students/import/', views.student_import, name='student_import'),
    path('students/', views.student_list_admin, name='student_list_admin'),
    path('students/<int:student_id>/', views.student_profile, name='student_profile'),
    path('records/', views.admin_records, name='admin_records'),
    path('corrections/', views.correction_requests_admin, name='correction_requests_admin'),
    path('corrections/<int:request_id>/', views.review_correction_request, name='review_correction_request'),
    path('users/', views.admin_users, name='admin_users'),
    path('users/add/', views.admin_user_create, name='admin_user_create'),
    path('users/<int:user_id>/edit/', views.admin_user_edit, name='admin_user_edit'),
    path('users/<int:user_id>/reset-password/', views.admin_user_reset_password, name='admin_user_reset_password'),
    path('users/<int:user_id>/delete/', views.admin_user_delete, name='admin_user_delete'),

    path('teacher-assignments/', views.teacher_assignments_admin, name='teacher_assignments_admin'),
    path('teacher-progress/issue-week/', views.issue_week_admin, name='issue_week_admin'),
    path('teacher-progress/export/', views.teacher_progress_export, name='teacher_progress_export'),
    path('teacher-assignments/<int:assignment_id>/deactivate/', views.teacher_assignment_deactivate, name='teacher_assignment_deactivate'),
    path('teacher-progress/classes/', views.teacher_progress_classes_admin, name='teacher_progress_classes_admin'),
    path('teacher-progress/classes/<int:class_id>/', views.teacher_progress_class_detail_admin, name='teacher_progress_class_detail_admin'),
    path('teacher-progress/teachers/', views.teacher_progress_teachers_admin, name='teacher_progress_teachers_admin'),
    path('teacher-progress/teachers/<int:user_id>/', views.teacher_progress_teacher_detail_admin, name='teacher_progress_teacher_detail_admin'),
    path('teacher-progress/course/<int:assignment_id>/', views.teacher_progress_assignment_detail_admin, name='teacher_progress_assignment_detail_admin'),
    path('teacher-progress/row/<int:progress_id>/admin-edit/', views.teacher_progress_row_edit_admin, name='teacher_progress_row_edit_admin'),

    path('backups/', views.backups_admin, name='backups_admin'),
    path('backups/create/', views.backup_now, name='backup_now'),
    path('backups/<int:backup_id>/download/', views.backup_download, name='backup_download'),
]
