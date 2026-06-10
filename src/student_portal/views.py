import logging

from django.contrib.auth import authenticate

from rest_framework import generics, views, status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from dashboard.models import (
    Student,
    GroupSubscription,
    Attendance,
    ExamResult,
    Payment,
)
from .serializers import (
    StudentSelfProfileSerializer,
    StudentSelfSubscriptionSerializer,
    StudentSelfAttendanceSerializer,
    StudentSelfExamResultSerializer,
    StudentSelfPaymentSerializer,
)

logger = logging.getLogger(__name__)


# =============================================================================
#  CUSTOM PERMISSIONS
# =============================================================================

class IsStudentUser(IsAuthenticated):
    """
    Grants access only to authenticated users who are linked to a Student record.
    """
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return (
            hasattr(request.user, 'student_profile')
            and request.user.student_profile is not None
        )


# =============================================================================
#  STUDENT VIEWS
# =============================================================================

class StudentLoginView(views.APIView):
    """
    POST /api/v1/student/login/
    Authenticate a student and return an auth token + basic profile info.

    Payload:
    {
        "username": "00163865",
        "password": "00163865"
    }
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        if not username or not password:
            return Response(
                {"error": "يجب إدخال اسم المستخدم وكلمة المرور"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(username=username, password=password)
        if user is None:
            return Response(
                {"error": "اسم المستخدم أو كلمة المرور غير صحيح"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Ensure this user is actually linked to a student
        if not hasattr(user, 'student_profile') or user.student_profile is None:
            return Response(
                {"error": "هذا الحساب ليس حساب طالب"},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)
        student = user.student_profile

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "student_id": student.student_id,
            "full_name": student.full_name,
        }, status=status.HTTP_200_OK)


class StudentSelfProfileView(generics.RetrieveAPIView):
    """
    GET /api/v1/student/profile/
    Return the full profile of the currently logged-in student.
    """
    permission_classes = [IsStudentUser]
    serializer_class = StudentSelfProfileSerializer

    def get_object(self):
        return Student.objects.select_related(
            'academic_year'
        ).prefetch_related(
            'subscriptions__group__subject',
            'subscriptions__group__center',
            'attendance_records__session__group__center',
            'exam_results__exam__group__center',
            'payments'
        ).get(pk=self.request.user.student_profile.student_id)


class StudentSelfAttendanceView(generics.ListAPIView):
    """
    GET /api/v1/student/attendance/
    List the logged-in student's attendance history (paginated).
    """
    permission_classes = [IsStudentUser]
    serializer_class = StudentSelfAttendanceSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['is_present']
    ordering_fields = ['session__session_date']
    ordering = ['-session__session_date']

    def get_queryset(self):
        return Attendance.objects.filter(
            student=self.request.user.student_profile
        ).select_related('session__group__center')


class StudentSelfExamsView(generics.ListAPIView):
    """
    GET /api/v1/student/exams/
    List the logged-in student's exam results (paginated).
    """
    permission_classes = [IsStudentUser]
    serializer_class = StudentSelfExamResultSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ['exam__exam_date', 'student_score']
    ordering = ['-exam__exam_date']

    def get_queryset(self):
        return ExamResult.objects.filter(
            student=self.request.user.student_profile
        ).select_related('exam__group__center')


class StudentSelfPaymentsView(generics.ListAPIView):
    """
    GET /api/v1/student/payments/
    List the logged-in student's payment history (paginated).
    """
    permission_classes = [IsStudentUser]
    serializer_class = StudentSelfPaymentSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ['payment_date', 'amount']
    ordering = ['-payment_date']

    def get_queryset(self):
        return Payment.objects.filter(
            student=self.request.user.student_profile
        )


class StudentSelfSubscriptionsView(generics.ListAPIView):
    """
    GET /api/v1/student/subscriptions/
    List the logged-in student's group subscriptions.
    """
    permission_classes = [IsStudentUser]
    serializer_class = StudentSelfSubscriptionSerializer

    def get_queryset(self):
        return GroupSubscription.objects.filter(
            student=self.request.user.student_profile
        ).select_related('group__subject', 'group__center')
