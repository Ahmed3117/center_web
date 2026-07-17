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
    TeacherPublicSerializer,
    AcademicCenterSerializer,
    StudentListSerializer,
    StudentDetailSerializer,
    ClassGroupListSerializer,
    ClassGroupDetailSerializer,
    SessionAttendanceSerializer,
    ExamListSerializer,
    ExamDetailSerializer,
    TeacherProfileSerializer,
)

logger = logging.getLogger(__name__)


# =============================================================================
#  PERMISSIONS & MIXINS
# =============================================================================

class IsTeacherOrAdmin(IsAuthenticated):
    """
    Allow access if the user is:
    - A superuser (admin)
    - A user linked to a Teacher record
    """
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        return user.is_superuser or hasattr(user, 'teacher_profile')


class TeacherScopedMixin:
    """
    Mixin for dashboard views that auto-filters querysets
    by the logged-in teacher. Superusers see all data and
    can optionally filter by teacher_id/teacher_slug.
    """
    teacher_filter_field = 'teacher'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            # Superusers can optionally filter by teacher
            teacher_id = self.request.query_params.get('teacher_id')
            teacher_slug = self.request.query_params.get('teacher_slug')
            if teacher_id:
                qs = qs.filter(**{f'{self.teacher_filter_field}_id': teacher_id})
            elif teacher_slug:
                qs = qs.filter(**{f'{self.teacher_filter_field}__slug': teacher_slug})
            return qs
        # Teacher user → auto-scope to their data only
        if hasattr(user, 'teacher_profile'):
            return qs.filter(**{self.teacher_filter_field: user.teacher_profile})
        return qs.none()


# =============================================================================
#  PUBLIC VIEWS  (no auth required)
# =============================================================================

class TeacherPublicDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/public/teachers/<str:slug>/
    Retrieve a single teacher's public profile details by their unique slug.
    """
    permission_classes = [AllowAny]
    queryset = Teacher.objects.all()
    serializer_class = TeacherPublicSerializer
    lookup_field = 'slug'



# =============================================================================
#  DASHBOARD / ADMIN VIEWS  (staff-only)
# =============================================================================

class AcademicYearListView(TeacherScopedMixin, generics.ListAPIView):
    """
    GET /api/v1/academic-years/
    List all academic years (grade levels). Auto-scoped by logged-in teacher.
    """
    permission_classes = [IsTeacherOrAdmin]
    queryset = AcademicYear.objects.select_related('teacher').all()
    serializer_class = AcademicYearSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['level']
    search_fields = ['name']
    ordering_fields = ['level', 'name']


class SubjectListView(TeacherScopedMixin, generics.ListAPIView):
    """
    GET /api/v1/subjects/
    List all subjects. Auto-scoped by logged-in teacher.
    """
    permission_classes = [IsTeacherOrAdmin]
    queryset = Subject.objects.select_related('academic_year', 'teacher').all()
    serializer_class = SubjectSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['academic_year_id', 'academic_year__level']
    search_fields = ['name']
    ordering_fields = ['name']


class TeacherListView(generics.ListAPIView):
    """
    GET /api/v1/teachers/
    List all teachers. Superusers see all; teachers see only themselves.
    """
    permission_classes = [IsTeacherOrAdmin]
    serializer_class = TeacherSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'slug']
    ordering_fields = ['name']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Teacher.objects.all()
        if hasattr(user, 'teacher_profile'):
            return Teacher.objects.filter(pk=user.teacher_profile.pk)
        return Teacher.objects.none()


class AcademicCenterListView(TeacherScopedMixin, generics.ListAPIView):
    """
    GET /api/v1/centers/
    List all academic centers. Auto-scoped by logged-in teacher.
    """
    permission_classes = [IsTeacherOrAdmin]
    queryset = AcademicCenter.objects.select_related('teacher').all()
    serializer_class = AcademicCenterSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = []
    search_fields = ['name', 'location']
    ordering_fields = ['name']


class StudentListView(TeacherScopedMixin, generics.ListAPIView):
    """
    GET /api/v1/students/
    List & search students. Auto-scoped by logged-in teacher.
    """
    permission_classes = [IsTeacherOrAdmin]
    queryset = Student.objects.select_related('academic_year', 'teacher').all().order_by('student_id')
    serializer_class = StudentListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'academic_year_id', 'academic_year__level', 'section',
        'subscriptions__group_id', 'subscriptions__group__center_id',
        'subscriptions__group__subject_id', 'subscriptions__subscription_type',
    ]
    search_fields = ['student_id', 'full_name', 'phone_number', 'parent_phone_number']
    ordering_fields = ['created_at', 'full_name', 'student_id']


class StudentDetailView(TeacherScopedMixin, generics.RetrieveAPIView):
    """
    GET /api/v1/students/{pk}/
    Retrieve complete student profile with sub-entities. Auto-scoped by logged-in teacher.
    """
    permission_classes = [IsTeacherOrAdmin]
    queryset = Student.objects.select_related(
        'academic_year', 'teacher'
    ).prefetch_related(
        'subscriptions__group__subject',
        'subscriptions__group__center',
        'attendance_records__session__group__center',
        'exam_results__exam',
        'payments'
    ).all()
    serializer_class = StudentDetailSerializer
    lookup_field = 'pk'


class ClassGroupListView(TeacherScopedMixin, generics.ListAPIView):
    """
    GET /api/v1/groups/
    List all class groups. Auto-scoped by logged-in teacher.
    """
    permission_classes = [IsTeacherOrAdmin]
    queryset = ClassGroup.objects.select_related(
        'academic_year', 'subject', 'center', 'teacher'
    ).all().order_by('name')
    serializer_class = ClassGroupListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'academic_year_id', 'academic_year__level',
        'subject_id', 'center_id',
    ]
    search_fields = ['name', 'subject__name', 'center__name', 'teacher__name']
    ordering_fields = ['created_at', 'name']


class ClassGroupDetailView(TeacherScopedMixin, generics.RetrieveAPIView):
    """
    GET /api/v1/groups/{id}/
    Retrieve group details: enrolled students, and sessions histories. Auto-scoped by logged-in teacher.
    """
    permission_classes = [IsTeacherOrAdmin]
    queryset = ClassGroup.objects.select_related(
        'center', 'subject', 'teacher'
    ).prefetch_related(
        'subscriptions__student',
        'sessions__attendance_records'
    ).all()
    serializer_class = ClassGroupDetailSerializer
    lookup_field = 'id'


class SessionAttendanceView(TeacherScopedMixin, generics.RetrieveAPIView):
    """
    GET /api/v1/sessions/{session_id}/attendance/
    Retrieve session attendance list. Auto-scoped by logged-in teacher.
    """
    permission_classes = [IsTeacherOrAdmin]
    queryset = Session.objects.select_related('group').prefetch_related(
        'attendance_records__student'
    ).all()
    serializer_class = SessionAttendanceSerializer
    lookup_field = 'id'


class ExamListView(TeacherScopedMixin, generics.ListAPIView):
    """
    GET /api/v1/exams/
    List all exams. Auto-scoped by logged-in teacher.
    """
    permission_classes = [IsTeacherOrAdmin]
    queryset = Exam.objects.select_related('group__center', 'teacher').prefetch_related('results').all()
    serializer_class = ExamListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'group_id', 'group__center_id', 'group__subject_id',
        'group__academic_year_id', 'group__academic_year__level',
        'exam_date',
    ]
    search_fields = ['name', 'group__name']
    ordering_fields = ['exam_date', 'name', 'max_score']


class ExamDetailView(TeacherScopedMixin, generics.RetrieveAPIView):
    """
    GET /api/v1/exams/{id}/results/
    Retrieve exam metadata and scores for all students. Auto-scoped by logged-in teacher.
    """
    permission_classes = [IsTeacherOrAdmin]
    queryset = Exam.objects.prefetch_related('results__student').all()
    serializer_class = ExamDetailSerializer
    lookup_field = 'id'


class DashboardStatsView(views.APIView):
    """
    GET /api/v1/dashboard/stats/
    Retrieve overview summary stats for the landing page.
    Auto-scoped by logged-in teacher. Superusers can optionally filter
    via ?teacher_id= or ?teacher_slug=
    """
    permission_classes = [IsTeacherOrAdmin]

    def _get_teacher_scope(self, request):
        """Determine the teacher to scope data by, or None for all data."""
        user = request.user
        if not user.is_superuser and hasattr(user, 'teacher_profile'):
            return user.teacher_profile
        if user.is_superuser:
            teacher_id = request.query_params.get('teacher_id')
            teacher_slug = request.query_params.get('teacher_slug')
            if teacher_id:
                return Teacher.objects.filter(id=teacher_id).first()
            elif teacher_slug:
                return Teacher.objects.filter(slug=teacher_slug).first()
        return None

    def get(self, request, *args, **kwargs):
        teacher = self._get_teacher_scope(request)

        students_qs = Student.objects.all()
        groups_qs = ClassGroup.objects.all()
        centers_qs = AcademicCenter.objects.all()
        sessions_qs = Session.objects.all()

        if teacher:
            students_qs = students_qs.filter(teacher=teacher)
            groups_qs = groups_qs.filter(teacher=teacher)
            centers_qs = centers_qs.filter(teacher=teacher)
            sessions_qs = sessions_qs.filter(teacher=teacher)

        today = timezone.localdate()

        return Response({
            "total_students": students_qs.count(),
            "total_groups": groups_qs.count(),
            "active_centers": centers_qs.count(),
            "today_sessions_count": sessions_qs.filter(session_date__date=today).count()
        })


class DashboardLoginView(views.APIView):
    """
    POST /api/v1/login/
    Authenticate a dashboard user (superuser or teacher) and return JWT tokens.

    Payload:
    {
        "username": "teacher1",
        "password": "password"
    }
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = str(request.data.get('username') or '').strip()
        password = str(request.data.get('password') or '')

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

        # Allow superusers and users linked to a teacher
        is_teacher = hasattr(user, 'teacher_profile') and user.teacher_profile is not None
        if not user.is_superuser and not is_teacher:
            return Response(
                {"error": "هذا الحساب ليس حساب مسؤول أو مدرس"},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)

        response_data = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "username": user.username,
            "is_superuser": user.is_superuser,
        }

        # Include teacher profile info if the user is a teacher
        if is_teacher:
            teacher = user.teacher_profile
            response_data["teacher"] = {
                "id": str(teacher.id),
                "name": teacher.name,
                "slug": teacher.slug,
            }

        return Response(response_data, status=status.HTTP_200_OK)


class DashboardChangePasswordView(views.APIView):
    """
    POST /api/v1/dashboard/change-password/
    Allow a logged-in dashboard user (teacher or superuser) to change their password.

    Payload:
    {
        "old_password": "current_password",
        "new_password": "new_password"
    }
    """
    permission_classes = [IsTeacherOrAdmin]

    def post(self, request, *args, **kwargs):
        old_password = request.data.get('old_password', '')
        new_password = request.data.get('new_password', '')

        if not old_password or not new_password:
            return Response(
                {"error": "يجب إدخال كلمة المرور القديمة والجديدة"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(new_password) < 6:
            return Response(
                {"error": "كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        if not user.check_password(old_password):
            return Response(
                {"error": "كلمة المرور القديمة غير صحيحة"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "تم تغيير كلمة المرور بنجاح"},
            status=status.HTTP_200_OK
        )


class TeacherProfileView(generics.RetrieveUpdateAPIView):
    """
    GET /api/v1/teacher/profile/
    PUT/PATCH /api/v1/teacher/profile/
    Retrieve or update the logged-in teacher's profile details.
    """
    permission_classes = [IsTeacherOrAdmin]
    serializer_class = TeacherProfileSerializer

    def get_object(self):
        user = self.request.user
        teacher = getattr(user, 'teacher_profile', None)
        if not teacher:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("هذا الحساب ليس لديه ملف مدرس مرتبط به.")
        return teacher


# =============================================================================
#  DESKTOP SYNC VIEWS  (token-auth)
# =============================================================================

from .sync_utils import MODEL_REGISTRY, run_sync_upsert, _resolve_or_create_teacher


class DesktopSyncUpsertView(views.APIView):
    """
    POST /api/v1/sync/upsert/
    Atomic transactional API to receive batch payloads from the desktop application
    and upsert them in strict dependency order, scoped to a teacher.

    Payload:
    {
        "teacher": {"name": "أحمد عيسى", "slug": "1234567890"},
        "data": { ... }
    }
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

        # Resolve teacher from payload
        teacher_data = request.data.get('teacher')
        teacher, error = _resolve_or_create_teacher(teacher_data)
        if error:
            return Response({
                "status": "failed",
                "error": error
            }, status=status.HTTP_400_BAD_REQUEST)

        payload_data = request.data.get('data', {})

        success, upserted_counts, skipped_records, error_message = run_sync_upsert(
            payload_data, teacher
        )

        if not success:
            return Response({
                "status": "failed",
                "error": error_message
            }, status=status.HTTP_400_BAD_REQUEST)

        response_data = {
            "status": "success",
            "teacher": {
                "name": teacher.name,
                "slug": teacher.slug,
            },
            "upserted_counts": upserted_counts
        }
        if skipped_records:
            response_data["skipped_records"] = skipped_records

        return Response(response_data, status=status.HTTP_200_OK)


class DesktopSyncDeleteView(views.APIView):
    """
    POST /api/v1/sync/delete/
    API to execute batch hard-deletes of records deleted offline on the desktop application.
    Scoped to a teacher.

    Payload:
    {
        "teacher": {"slug": "1234567890"},
        "deleted_records": [...]
    }
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

        # Resolve teacher from payload
        teacher_data = request.data.get('teacher')
        if not teacher_data or not teacher_data.get('slug'):
            return Response({
                "status": "failed",
                "error": "Missing teacher slug in payload"
            }, status=status.HTTP_400_BAD_REQUEST)

        teacher = Teacher.objects.filter(slug=teacher_data['slug']).first()
        if not teacher:
            return Response({
                "status": "failed",
                "error": f"Teacher with slug={teacher_data['slug']} not found"
            }, status=status.HTTP_404_NOT_FOUND)

        deleted_records = request.data.get('deleted_records', [])
        deleted_count = 0
        not_found_records = []

        try:
            with transaction.atomic():
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

                    # Build lookup scoped to teacher
                    if model_key == 'STUDENT':
                        lookup_kwargs = {'teacher': teacher, 'student_id': item_id}
                    else:
                        lookup_kwargs = {'teacher': teacher, 'desktop_id': item_id}

                    deleted_rows, _ = model_class.objects.filter(**lookup_kwargs).delete()
                    if deleted_rows > 0:
                        deleted_count += 1
                    else:
                        not_found_records.append({
                            'record': record,
                            'reason': 'Record not found for this teacher (may have been previously deleted)'
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
        
        # Handle both single payload (dict) and multiple payloads (list)
        if isinstance(payload, list):
            payloads = payload
        else:
            payloads = [payload]
            
        success_count = 0
        total_upserted = {}
        total_skipped = 0
        errors = []
        
        for p in payloads:
            # Resolve teacher from payload
            teacher_data = p.get('teacher')
            teacher, error = _resolve_or_create_teacher(teacher_data)
            if error:
                errors.append(f"مدرس {teacher_data.get('name', 'غير معروف')}: {error}")
                continue
            
            data = p.get('data', {})
            success, upserted_counts, skipped_records, error_message = run_sync_upsert(data, teacher)
            
            if success:
                success_count += 1
                total_skipped += len(skipped_records)
                for k, v in upserted_counts.items():
                    total_upserted[k] = total_upserted.get(k, 0) + v
            else:
                errors.append(f"مدرس {teacher.name}: {error_message}")
        
        if success_count > 0:
            summary = ", ".join([f"{k}: {v}" for k, v in total_upserted.items() if v > 0])
            msg = f"تم استيراد البيانات بنجاح لعدد {success_count} مدرس! السجلات المحدثة/المضافة: {summary or 'لا يوجد جديد'}"
            if total_skipped > 0:
                msg += f" (تنبيه: تم تخطي {total_skipped} سجل)"
            messages.success(request, msg)
            
        if errors:
            messages.error(request, f"بعض الأخطاء حدثت أثناء الاستيراد: {'; '.join(errors)}")
            
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


class DesktopSyncDeleteTeacherView(views.APIView):
    """
    DELETE or POST /api/v1/sync/delete-teacher/<teacher_slug>/
    Hard-deletes a teacher and all of their related data (cascade).
    Also deletes the teacher's auth User account.
    """
    permission_classes = [AllowAny]

    def delete(self, request, teacher_slug, *args, **kwargs):
        return self.post(request, teacher_slug, *args, **kwargs)

    def post(self, request, teacher_slug, *args, **kwargs):
        # 1. Authorize token
        token = request.headers.get('X-Desktop-Sync-Token')
        expected_token = getattr(settings, 'DESKTOP_SYNC_TOKEN', None)
        if not expected_token or token != expected_token:
            return Response(
                {"error": "غير مصرح به - توكن المزامنة غير صحيح"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 2. Validate teacher slug
        teacher_slug = str(teacher_slug or '').strip()
        if not teacher_slug:
            return Response(
                {"error": "يجب إدخال رمز المدرس في الرابط"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Find Teacher
        teacher = Teacher.objects.filter(slug=teacher_slug).first()
        if not teacher:
            return Response(
                {"error": f"المدرس ذو الرمز '{teacher_slug}' غير موجود"},
                status=status.HTTP_404_NOT_FOUND
            )

        # 4. Perform deletion (Teacher cascade + associated User account)
        teacher_user_id = teacher.user_id
        
        # Fetch all user IDs associated with the students of this teacher to bulk delete them later
        student_user_ids = list(
            Student.objects.filter(teacher=teacher, user__isnull=False)
            .values_list('user_id', flat=True)
        )
        
        from django.db import connection
        try:
            with transaction.atomic():
                if connection.vendor == 'postgresql':
                    # Delete child records in reverse dependency order to avoid FK constraint violations
                    # (super fast, executes in milliseconds)
                    tables_to_delete = [
                        'dashboard_examresult',
                        'dashboard_attendance',
                        'dashboard_payment',
                        'dashboard_groupsubscription',
                        'dashboard_student',
                        'dashboard_exam',
                        'dashboard_session',
                        'dashboard_classgroup',
                        'dashboard_subject',
                        'dashboard_academiccenter',
                        'dashboard_academicyear',
                    ]
                    with connection.cursor() as cursor:
                        for table in tables_to_delete:
                            cursor.execute(f"DELETE FROM {table} WHERE teacher_id = %s", [teacher.id])
                        cursor.execute("DELETE FROM dashboard_teacher WHERE id = %s", [teacher.id])
                else:
                    # Fallback for SQLite (no network latency, Django cascade is fast enough)
                    teacher.delete()
                
                # Bulk delete the associated User accounts in one single query
                all_user_ids = list(student_user_ids)
                if teacher_user_id:
                    all_user_ids.append(teacher_user_id)
                
                if all_user_ids:
                    User.objects.filter(id__in=all_user_ids).delete()
        except Exception as e:
            return Response(
                {"error": f"حدث خطأ أثناء مسح المدرس: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"status": "success", "message": "تم حذف المدرس وجميع بياناته بنجاح"},
            status=status.HTTP_200_OK
        )

