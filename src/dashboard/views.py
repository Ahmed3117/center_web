import logging

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
    GroupSchedule,
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
    ).prefetch_related('schedules').all().order_by('name')
    serializer_class = ClassGroupListSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['academic_year_id', 'subject_id', 'center_id']
    search_fields = ['name', 'subject__name', 'center__name', 'teacher__name']
    ordering_fields = ['created_at', 'name']


class ClassGroupDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/groups/{id}/
    Retrieve group details: schedules, enrolled students, and sessions histories.
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

MODEL_REGISTRY = {
    'ACADEMIC_YEAR': AcademicYear,
    'SUBJECT': Subject,
    'TEACHER': Teacher,
    'ACADEMIC_CENTER': AcademicCenter,
    'CLASS_GROUP': ClassGroup,
    'GROUP_SCHEDULE': GroupSchedule,
    'STUDENT': Student,
    'GROUP_SUBSCRIPTION': GroupSubscription,
    'SESSION': Session,
    'ATTENDANCE': Attendance,
    'EXAM': Exam,
    'EXAM_RESULT': ExamResult,
    'PAYMENT': Payment,
}

FK_FIELD_MAP = {
    'academic_year_id': ('academic_year', AcademicYear),
    'subject_id': ('subject', Subject),
    'center_id': ('center', AcademicCenter),
    'teacher_id': ('teacher', Teacher),
    'group_id': ('group', ClassGroup),
    'session_id': ('session', Session),
    'exam_id': ('exam', Exam),
}

VALID_SUBSCRIPTION_TYPES = {'شهري', 'بالحصة', 'إعفاء'}

# Fields sent by the desktop for student auth that are NOT model columns
STUDENT_AUTH_FIELDS = {'username', 'password'}


def _prefetch_fk_objects(records, fk_payload_field, model_class, pk_field='pk'):
    """
    Batch-fetch all FK objects referenced by `fk_payload_field` in the records list.
    Returns a dict mapping string PK → model instance.
    """
    referenced_ids = {r[fk_payload_field] for r in records if fk_payload_field in r}
    if not referenced_ids:
        return {}
    return {str(obj.pk): obj for obj in model_class.objects.filter(**{f'{pk_field}__in': referenced_ids})}


def _handle_student_user(student_obj, username, password):
    """
    Create or update the Django auth User linked to a Student.
    - If the student already has a user, update username/password.
    - Otherwise, create a new user and link it.
    """
    if student_obj.user:
        user = student_obj.user
        if user.username != username:
            user.username = username
        user.set_password(password)
        user.save()
    else:
        existing_user = User.objects.filter(username=username).first()
        if existing_user:
            if hasattr(existing_user, 'student_profile') and existing_user.student_profile is not None:
                if existing_user.student_profile.student_id != student_obj.student_id:
                    logger.warning(
                        "Username '%s' already belongs to student '%s', cannot assign to '%s'.",
                        username, existing_user.student_profile.student_id, student_obj.student_id
                    )
                    return
            existing_user.set_password(password)
            existing_user.save()
            student_obj.user = existing_user
            student_obj.save(update_fields=['user'])
        else:
            user = User.objects.create_user(username=username, password=password)
            student_obj.user = user
            student_obj.save(update_fields=['user'])


class DesktopSyncUpsertView(views.APIView):
    """
    POST /api/v1/sync/upsert/
    Atomic transactional API to receive batch payloads from the desktop application
    and upsert them in strict dependency order.

    For STUDENT records, the desktop can optionally send:
        "username": "custom_username"   (defaults to student_id if not sent)
        "password": "plain_text_pass"   (defaults to student_id if not sent)
    A Django auth User will be created/updated and linked to the Student.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, *args, **kwargs):
        payload_data = request.data.get('data', {})
        center_id = request.data.get('center_id')

        upserted_counts = {model_name: 0 for model_name in MODEL_REGISTRY.keys()}
        skipped_records = []

        sync_sequence = [
            'ACADEMIC_YEAR',
            'SUBJECT',
            'ACADEMIC_CENTER',
            'TEACHER',
            'CLASS_GROUP',
            'GROUP_SCHEDULE',
            'STUDENT',
            'GROUP_SUBSCRIPTION',
            'SESSION',
            'ATTENDANCE',
            'EXAM',
            'EXAM_RESULT',
            'PAYMENT',
        ]

        try:
            with transaction.atomic():
                for model_key in sync_sequence:
                    records = payload_data.get(model_key, [])
                    if not records:
                        continue

                    model_class = MODEL_REGISTRY[model_key]
                    pk_field = 'student_id' if model_key == 'STUDENT' else 'id'

                    fk_caches = {}
                    for fk_payload_field, (orm_field, fk_model) in FK_FIELD_MAP.items():
                        if fk_payload_field == 'student_id' and model_key == 'STUDENT':
                            continue
                        if any(fk_payload_field in r for r in records):
                            fk_caches[fk_payload_field] = _prefetch_fk_objects(
                                records, fk_payload_field, fk_model
                            )

                    if model_key != 'STUDENT' and any('student_id' in r for r in records):
                        student_ids = {r['student_id'] for r in records if 'student_id' in r}
                        fk_caches['student_id'] = {
                            str(s.pk): s for s in Student.objects.filter(pk__in=student_ids)
                        }

                    for record in records:
                        pk_val = record.get(pk_field)
                        if not pk_val:
                            skipped_records.append({
                                'model': model_key,
                                'record': record,
                                'reason': f'Missing primary key field: {pk_field}'
                            })
                            continue

                        if model_key == 'GROUP_SUBSCRIPTION':
                            sub_type = record.get('subscription_type', '')
                            if sub_type and sub_type not in VALID_SUBSCRIPTION_TYPES:
                                skipped_records.append({
                                    'model': model_key,
                                    'record': record,
                                    'reason': f'Invalid subscription_type: {sub_type}. Must be one of: {VALID_SUBSCRIPTION_TYPES}'
                                })
                                continue

                        upsert_data = record.copy()

                        # For STUDENT: extract auth fields before DB upsert
                        student_username = None
                        student_password = None
                        if model_key == 'STUDENT':
                            student_username = upsert_data.pop('username', pk_val)
                            student_password = upsert_data.pop('password', pk_val)
                            upsert_data.pop('user', None)

                        # Resolve FK fields
                        fk_resolved = True
                        for fk_payload_field, (orm_field, fk_model) in FK_FIELD_MAP.items():
                            if fk_payload_field in upsert_data:
                                if fk_payload_field == 'student_id' and model_key == 'STUDENT':
                                    continue
                                fk_val = str(upsert_data.pop(fk_payload_field))
                                cache = fk_caches.get(fk_payload_field, {})
                                fk_obj = cache.get(fk_val)
                                if fk_obj is None:
                                    skipped_records.append({
                                        'model': model_key,
                                        'record': record,
                                        'reason': f'Referenced {orm_field} with id={fk_val} does not exist'
                                    })
                                    fk_resolved = False
                                    break
                                upsert_data[orm_field] = fk_obj

                        if not fk_resolved:
                            continue

                        if 'student_id' in upsert_data and model_key != 'STUDENT':
                            student_val = str(upsert_data.pop('student_id'))
                            student_cache = fk_caches.get('student_id', {})
                            student_obj = student_cache.get(student_val)
                            if student_obj is None:
                                skipped_records.append({
                                    'model': model_key,
                                    'record': record,
                                    'reason': f'Referenced student with id={student_val} does not exist'
                                })
                                continue
                            upsert_data['student'] = student_obj

                        kwargs = {pk_field: pk_val}
                        obj, created = model_class.objects.update_or_create(
                            **kwargs,
                            defaults=upsert_data
                        )
                        upserted_counts[model_key] += 1

                        if model_key == 'STUDENT' and student_username is not None:
                            _handle_student_user(obj, student_username, student_password)

                if center_id and not AcademicCenter.objects.filter(pk=center_id).exists():
                    logger.warning(
                        "Sync payload center_id=%s does not match any AcademicCenter record.",
                        center_id
                    )

            response_data = {
                "status": "success",
                "upserted_counts": upserted_counts
            }
            if skipped_records:
                response_data["skipped_records"] = skipped_records

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Sync upsert failed: %s", str(e))
            return Response({
                "status": "failed",
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class DesktopSyncDeleteView(views.APIView):
    """
    POST /api/v1/sync/delete/
    API to execute batch hard-deletes of records deleted offline on the desktop application.
    Student deletions also clean up the linked auth User (via post_delete signal).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, *args, **kwargs):
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
