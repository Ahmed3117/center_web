import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from django.db.models import Count

from rest_framework import generics, views, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import (
    AcademicYear,
    Subject,
    Teacher,
    AcademicCenter,
    ClassGroup,
    Student,
    GroupSubscription,
    Session,
    Attendance,
    Exam,
    ExamResult,
    Payment
)
from .serializers import (
    AcademicYearSerializer,
    SubjectSerializer,
    TeacherSerializer,
    AcademicCenterSerializer,
    StudentListSerializer,
    StudentDetailSerializer,
    ClassGroupListSerializer,
    ClassGroupDetailSerializer,
    SessionAttendanceSerializer,
    ExamListSerializer,
    ExamDetailSerializer,
)

logger = logging.getLogger(__name__)


# =============================================================================
#  DASHBOARD / ADMIN VIEWS  (staff-only)
# =============================================================================

class AcademicYearListView(generics.ListAPIView):
    """
    GET /api/v1/academic-years/
    List all academic years (grade levels).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['level', 'name']


class SubjectListView(generics.ListAPIView):
    """
    GET /api/v1/subjects/
    List all subjects. Allows filtering by academic year.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Subject.objects.select_related('academic_year').all()
    serializer_class = SubjectSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['academic_year_id']
    search_fields = ['name']
    ordering_fields = ['name']


class TeacherListView(generics.ListAPIView):
    """
    GET /api/v1/teachers/
    List all teachers.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']


class AcademicCenterListView(generics.ListAPIView):
    """
    GET /api/v1/centers/
    List all academic centers.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = AcademicCenter.objects.all()
    serializer_class = AcademicCenterSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'location']
    ordering_fields = ['name']


class StudentListView(generics.ListAPIView):
    """
    GET /api/v1/students/
    List & search students. Allows filtering by academic year and enrolled groups.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Student.objects.select_related('academic_year').all().order_by('student_id')
    serializer_class = StudentListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['academic_year_id', 'subscriptions__group_id']
    search_fields = ['student_id', 'full_name', 'phone_number', 'parent_phone_number']
    ordering_fields = ['created_at', 'full_name', 'student_id']


class StudentDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/students/{student_id}/
    Retrieve complete student profile with sub-entities.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Student.objects.select_related(
        'academic_year'
    ).prefetch_related(
        'subscriptions__group__subject',
        'subscriptions__group__center',
        'attendance_records__session__group__center',
        'exam_results__exam',
        'payments'
    ).all()
    serializer_class = StudentDetailSerializer
    lookup_field = 'student_id'


class ClassGroupListView(generics.ListAPIView):
    """
    GET /api/v1/groups/
    List all class groups. Allows filtering by academic year, subject, and physical center.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = ClassGroup.objects.select_related(
        'academic_year', 'subject', 'center', 'teacher'
    ).all().order_by('name')
    serializer_class = ClassGroupListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['academic_year_id', 'subject_id', 'center_id']
    search_fields = ['name', 'subject__name', 'center__name', 'teacher__name']
    ordering_fields = ['created_at', 'name']


class ClassGroupDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/groups/{id}/
    Retrieve group details: enrolled students, and sessions histories.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = ClassGroup.objects.select_related(
        'center', 'subject'
    ).prefetch_related(
        'subscriptions__student',
        'sessions__attendance_records'
    ).all()
    serializer_class = ClassGroupDetailSerializer
    lookup_field = 'id'


class SessionAttendanceView(generics.RetrieveAPIView):
    """
    GET /api/v1/sessions/{session_id}/attendance/
    Retrieve session attendance list.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Session.objects.select_related('group').prefetch_related(
        'attendance_records__student'
    ).all()
    serializer_class = SessionAttendanceSerializer
    lookup_field = 'id'


class ExamListView(generics.ListAPIView):
    """
    GET /api/v1/exams/
    List all exams. Allows filtering by class group.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Exam.objects.select_related('group__center').prefetch_related('results').all()
    serializer_class = ExamListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['group_id']
    search_fields = ['name', 'group__name']
    ordering_fields = ['exam_date', 'name', 'max_score']


class ExamDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/exams/{id}/results/
    Retrieve exam metadata and scores for all students.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Exam.objects.prefetch_related('results__student').all()
    serializer_class = ExamDetailSerializer
    lookup_field = 'id'


class DashboardStatsView(views.APIView):
    """
    GET /api/v1/dashboard/stats/
    Retrieve overview summary stats for the landing page.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, *args, **kwargs):
        total_students = Student.objects.count()
        total_groups = ClassGroup.objects.count()
        active_centers = AcademicCenter.objects.count()

        today = timezone.localdate()
        today_sessions_count = Session.objects.filter(session_date__date=today).count()

        return Response({
            "total_students": total_students,
            "total_groups": total_groups,
            "active_centers": active_centers,
            "today_sessions_count": today_sessions_count
        })


class DashboardLoginView(views.APIView):
    """
    POST /api/v1/login/
    Authenticate a dashboard (admin/staff) user and return an auth token.

    Payload:
    {
        "username": "admin",
        "password": "password"
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

        # Ensure this user has staff/admin status
        if not user.is_staff and not user.is_superuser:
            return Response(
                {"error": "هذا الحساب ليس حساب مسؤول"},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "username": user.username,
            "is_superuser": user.is_superuser,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
        }, status=status.HTTP_200_OK)


# =============================================================================
#  DESKTOP SYNC VIEWS  (staff-only)
# =============================================================================

from .sync_utils import MODEL_REGISTRY, run_sync_upsert


class DesktopSyncUpsertView(views.APIView):
    """
    POST /api/v1/sync/upsert/
    Atomic transactional API to receive batch payloads from the desktop application
    and upsert them in strict dependency order.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # Validate desktop sync token
        token = request.headers.get('X-Desktop-Sync-Token')
        expected_token = getattr(settings, 'DESKTOP_SYNC_TOKEN', None)
        if not expected_token or token != expected_token:
            return Response(
                {"error": "غير مصرح به - توكن المزامنة غير صحيح"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        payload_data = request.data.get('data', {})
        center_id = request.data.get('center_id')

        success, upserted_counts, skipped_records, error_message = run_sync_upsert(
            payload_data, center_id
        )

        if not success:
            return Response({
                "status": "failed",
                "error": error_message
            }, status=status.HTTP_400_BAD_REQUEST)

        response_data = {
            "status": "success",
            "upserted_counts": upserted_counts
        }
        if skipped_records:
            response_data["skipped_records"] = skipped_records

        return Response(response_data, status=status.HTTP_200_OK)


class DesktopSyncDeleteView(views.APIView):
    """
    POST /api/v1/sync/delete/
    API to execute batch hard-deletes of records deleted offline on the desktop application.
    Student deletions also clean up the linked auth User (via post_delete signal).
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        token = request.headers.get('X-Desktop-Sync-Token')
        expected_token = getattr(settings, 'DESKTOP_SYNC_TOKEN', None)
        if not expected_token or token != expected_token:
            return Response(
                {"error": "غير مصرح به - توكن المزامنة غير صحيح"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        deleted_records = request.data.get('deleted_records', [])
        center_id = request.data.get('center_id')
        deleted_count = 0
        not_found_records = []

        try:
            with transaction.atomic():
                if center_id and not AcademicCenter.objects.filter(pk=center_id).exists():
                    logger.warning(
                        "Delete payload center_id=%s does not match any AcademicCenter record.",
                        center_id
                    )

                for record in deleted_records:
                    model_key = record.get('model_name')
                    item_id = record.get('deleted_item_id')

                    if not model_key or not item_id:
                        not_found_records.append({
                            'record': record,
                            'reason': 'Missing model_name or deleted_item_id'
                        })
                        continue

                    model_class = MODEL_REGISTRY.get(model_key)
                    if not model_class:
                        not_found_records.append({
                            'record': record,
                            'reason': f'Unknown model_name: {model_key}'
                        })
                        continue

                    if model_key == 'STUDENT':
                        lookup_kwargs = {'student_id': item_id}
                    else:
                        lookup_kwargs = {'id': item_id}

                    deleted_rows, _ = model_class.objects.filter(**lookup_kwargs).delete()
                    if deleted_rows > 0:
                        deleted_count += 1
                    else:
                        not_found_records.append({
                            'record': record,
                            'reason': 'Record not found in database (may have been previously deleted)'
                        })

            response_data = {
                "status": "success",
                "deleted_count": deleted_count
            }
            if not_found_records:
                response_data["not_found_records"] = not_found_records

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Sync delete failed: %s", str(e))
            return Response({
                "status": "failed",
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
import json

@staff_member_required
def admin_import_dummy_data_view(request):
    if request.method == 'POST':
        json_file = request.FILES.get('json_file')
        if not json_file:
            messages.error(request, "لم يتم رفع أي ملف تجريبي.")
            return redirect('/admin/')
        
        try:
            file_content = json_file.read().decode('utf-8')
            payload = json.loads(file_content)
        except Exception as e:
            messages.error(request, f"خطأ في قراءة ملف JSON: {str(e)}")
            return redirect('/admin/')
        
        data = payload.get('data') if 'data' in payload else payload
        center_id = payload.get('center_id')
        
        success, upserted_counts, skipped_records, error_message = run_sync_upsert(data, center_id)
        
        if success:
            summary = ", ".join([f"{k}: {v}" for k, v in upserted_counts.items() if v > 0])
            msg = f"تم استيراد البيانات التجريبية بنجاح! السجلات المحدثة/المضافة: {summary or 'لا يوجد جديد'}"
            if skipped_records:
                msg += f" (تنبيه: تم تخطي {len(skipped_records)} سجل بسبب أخطاء تعارض أو نقص بيانات)"
            messages.success(request, msg)
        else:
            messages.error(request, f"فشل استيراد البيانات التجريبية: {error_message}")
            
        return redirect('/admin/')

    context = {
        'opts': {
            'app_label': 'dashboard',
            'app_config': {
                'verbose_name': 'لوحة التحكم',
            },
            'verbose_name_plural': 'المجموعات الدراسية',
        },
        'title': 'استيراد بيانات تجريبية (Import Dummy Data)',
        'has_permission': True,
        'is_popup': False,
        'site_header': 'إدارة السنتر التعليمي',
        'site_title': 'لوحة الإدارة',
        'user': request.user,
    }
    return render(request, 'admin/dashboard/import_dummy_data.html', context)

