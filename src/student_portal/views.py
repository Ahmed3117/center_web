from django.contrib.auth import authenticate
from rest_framework import generics, views, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from dashboard.models import (
    Student,
    Teacher,
    Attendance,
    ExamResult,
    Payment,
    GroupSubscription,
)
from .serializers import (
    StudentSelfProfileSerializer,
    StudentSelfAttendanceSerializer,
    StudentSelfExamResultSerializer,
    StudentSelfPaymentSerializer,
    StudentSelfSubscriptionSerializer,
)


class IsStudentUser(IsAuthenticated):
    """
    Custom permission that ensures the authenticated user
    is linked to a Student record.
    """
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, 'student_profile') and request.user.student_profile is not None


class StudentLoginView(views.APIView):
    """
    POST /api/v1/student/login/
    Authenticate a student for a specific teacher and return an auth token + basic profile info.

    Payload:
    {
        "teacher_slug": "1234567890",
        "username": "00163865",
        "password": "00163865"
    }
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        teacher_slug = request.data.get('teacher_slug', '').strip()
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        if not teacher_slug:
            return Response(
                {"error": "يجب إدخال رمز المدرس (teacher_slug)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not username or not password:
            return Response(
                {"error": "يجب إدخال اسم المستخدم وكلمة المرور"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify teacher exists
        teacher = Teacher.objects.filter(slug=teacher_slug).first()
        if not teacher:
            return Response(
                {"error": "المدرس غير موجود"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Construct namespaced username: {teacher_slug}_{original_username}
        namespaced_username = f"{teacher_slug}_{username}"

        user = authenticate(username=namespaced_username, password=password)
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
            "teacher_name": teacher.name,
            "teacher_slug": teacher.slug,
        }, status=status.HTTP_200_OK)


class StudentSelfProfileView(generics.RetrieveAPIView):
    """
    GET /api/v1/student/profile/
    Retrieve the full profile of the logged-in student in a single call.
    Data is automatically scoped to the student's teacher.
    """
    permission_classes = [IsStudentUser]
    serializer_class = StudentSelfProfileSerializer

    def get_object(self):
        return Student.objects.select_related(
            'academic_year', 'teacher'
        ).prefetch_related(
            'subscriptions__group__subject',
            'subscriptions__group__center',
            'attendance_records__session__group__center',
            'exam_results__exam__group',
            'payments'
        ).get(pk=self.request.user.student_profile.pk)


class StudentSelfAttendanceView(generics.ListAPIView):
    """
    GET /api/v1/student/attendance/
    Paginated attendance history for the logged-in student.
    """
    permission_classes = [IsStudentUser]
    serializer_class = StudentSelfAttendanceSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['is_present', 'session__group_id', 'session__group__center_id', 'session__group__subject_id']
    ordering_fields = ['session__session_date']
    ordering = ['-session__session_date']

    def get_queryset(self):
        return Attendance.objects.filter(
            student=self.request.user.student_profile
        ).select_related('session__group__center')


class StudentSelfExamsView(generics.ListAPIView):
    """
    GET /api/v1/student/exams/
    Paginated exam results for the logged-in student.
    """
    permission_classes = [IsStudentUser]
    serializer_class = StudentSelfExamResultSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['exam__group_id', 'exam__group__center_id', 'exam__group__subject_id', 'exam__exam_date']
    ordering_fields = ['exam__exam_date', 'student_score']
    ordering = ['-exam__exam_date']

    def get_queryset(self):
        return ExamResult.objects.filter(
            student=self.request.user.student_profile
        ).select_related('exam__group')


class StudentSelfPaymentsView(generics.ListAPIView):
    """
    GET /api/v1/student/payments/
    Paginated payment history for the logged-in student.
    """
    permission_classes = [IsStudentUser]
    serializer_class = StudentSelfPaymentSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['payment_date']
    ordering_fields = ['payment_date', 'amount']
    ordering = ['-payment_date']

    def get_queryset(self):
        return Payment.objects.filter(
            student=self.request.user.student_profile
        )


class StudentSelfSubscriptionsView(generics.ListAPIView):
    """
    GET /api/v1/student/subscriptions/
    List group subscriptions for the logged-in student.
    """
    permission_classes = [IsStudentUser]
    serializer_class = StudentSelfSubscriptionSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['subscription_type', 'group_id', 'group__center_id', 'group__subject_id']
    ordering_fields = ['created_at', 'price']
    ordering = ['-created_at']

    def get_queryset(self):
        return GroupSubscription.objects.filter(
            student=self.request.user.student_profile
        ).select_related('group__subject', 'group__center')
