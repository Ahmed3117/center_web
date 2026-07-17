from django.urls import path
from .views import (
    # Public views
    TeacherPublicDetailView,
    # Dashboard / Admin views
    DashboardLoginView,
    DashboardChangePasswordView,
    TeacherProfileView,
    AcademicYearListView,
    SubjectListView,
    TeacherListView,
    AcademicCenterListView,
    StudentListView,
    StudentDetailView,
    ClassGroupListView,
    ClassGroupDetailView,
    SessionAttendanceView,
    ExamListView,
    ExamDetailView,
    DashboardStatsView,
    # Desktop Sync views
    DesktopSyncUpsertView,
    DesktopSyncDeleteView,
    DesktopSyncDeleteTeacherView,
)

urlpatterns = [
    # Public Endpoints (no auth required)
    path('public/teachers/<str:slug>/', TeacherPublicDetailView.as_view(), name='teacher-public-detail'),

    # Dashboard Authentication
    path('login/', DashboardLoginView.as_view(), name='dashboard-login'),
    path('dashboard/change-password/', DashboardChangePasswordView.as_view(), name='dashboard-change-password'),
    path('teacher/profile/', TeacherProfileView.as_view(), name='teacher-profile'),

    # Dashboard Overview Stats
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),

    # Directory Lookup Endpoints
    path('academic-years/', AcademicYearListView.as_view(), name='academic-year-list'),
    path('subjects/', SubjectListView.as_view(), name='subject-list'),
    path('teachers/', TeacherListView.as_view(), name='teacher-list'),
    path('centers/', AcademicCenterListView.as_view(), name='center-list'),

    # Students Directory
    path('students/', StudentListView.as_view(), name='student-list'),
    path('students/<str:pk>/', StudentDetailView.as_view(), name='student-detail'),

    # Groups Directory
    path('groups/', ClassGroupListView.as_view(), name='group-list'),
    path('groups/<str:id>/', ClassGroupDetailView.as_view(), name='group-detail'),

    # Session Attendance Detail
    path('sessions/<str:id>/attendance/', SessionAttendanceView.as_view(), name='session-attendance'),

    # Exams Directory
    path('exams/', ExamListView.as_view(), name='exam-list'),
    path('exams/<str:id>/results/', ExamDetailView.as_view(), name='exam-results'),

    # Desktop Sync Endpoints
    path('sync/upsert/', DesktopSyncUpsertView.as_view(), name='sync-upsert'),
    path('sync/delete/', DesktopSyncDeleteView.as_view(), name='sync-delete'),
    path('sync/delete-teacher/<str:teacher_slug>/', DesktopSyncDeleteTeacherView.as_view(), name='sync-delete-teacher'),
]
