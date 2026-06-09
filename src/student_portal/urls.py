from django.urls import path
from .views import (
    StudentLoginView,
    StudentSelfProfileView,
    StudentSelfAttendanceView,
    StudentSelfExamsView,
    StudentSelfPaymentsView,
    StudentSelfSubscriptionsView,
)

urlpatterns = [
    path('login/', StudentLoginView.as_view(), name='student-login'),
    path('profile/', StudentSelfProfileView.as_view(), name='student-self-profile'),
    path('attendance/', StudentSelfAttendanceView.as_view(), name='student-self-attendance'),
    path('exams/', StudentSelfExamsView.as_view(), name='student-self-exams'),
    path('payments/', StudentSelfPaymentsView.as_view(), name='student-self-payments'),
    path('subscriptions/', StudentSelfSubscriptionsView.as_view(), name='student-self-subscriptions'),
]
