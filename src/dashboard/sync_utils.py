import logging
from django.db import transaction
from django.contrib.auth.models import User
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

logger = logging.getLogger(__name__)

MODEL_REGISTRY = {
    'ACADEMIC_YEAR': AcademicYear,
    'SUBJECT': Subject,
    'ACADEMIC_CENTER': AcademicCenter,
    'CLASS_GROUP': ClassGroup,
    'STUDENT': Student,
    'GROUP_SUBSCRIPTION': GroupSubscription,
    'SESSION': Session,
    'ATTENDANCE': Attendance,
    'EXAM': Exam,
    'EXAM_RESULT': ExamResult,
    'PAYMENT': Payment,
}

# Maps payload FK field → (ORM field name, model class, lookup field on the FK model)
# All FK lookups are scoped by teacher + desktop_id (or student_id for Student)
FK_FIELD_MAP = {
    'academic_year_id': ('academic_year', AcademicYear, 'desktop_id'),
    'subject_id': ('subject', Subject, 'desktop_id'),
    'center_id': ('center', AcademicCenter, 'desktop_id'),
    'group_id': ('group', ClassGroup, 'desktop_id'),
    'session_id': ('session', Session, 'desktop_id'),
    'exam_id': ('exam', Exam, 'desktop_id'),
}

VALID_SUBSCRIPTION_TYPES = {'شهري', 'بالحصة', 'إعفاء'}


def _prefetch_fk_objects_scoped(records, fk_payload_field, model_class, teacher, lookup_field='desktop_id'):
    """
    Batch-fetch all FK objects referenced by `fk_payload_field` in the records list,
    scoped to a specific teacher.
    Returns a dict mapping string desktop_id → model instance.
    """
    referenced_ids = {str(r[fk_payload_field]) for r in records if fk_payload_field in r}
    if not referenced_ids:
        return {}
    return {
        str(getattr(obj, lookup_field)): obj
        for obj in model_class.objects.filter(teacher=teacher, **{f'{lookup_field}__in': referenced_ids})
    }


def _handle_student_user(student_obj, teacher, username, password):
    """
    Create or update the Django auth User linked to a Student.
    Usernames are namespaced by teacher slug: {teacher_slug}_{original_username}
    """
    namespaced_username = f"{teacher.slug}_{username}"

    if student_obj.user:
        user = student_obj.user
        if user.username != namespaced_username:
            user.username = namespaced_username
        user.set_password(password)
        user.save()
    else:
        existing_user = User.objects.filter(username=namespaced_username).first()
        if existing_user:
            if hasattr(existing_user, 'student_profile') and existing_user.student_profile is not None:
                if existing_user.student_profile.pk != student_obj.pk:
                    logger.warning(
                        "Username '%s' already belongs to another student '%s', cannot assign to '%s'.",
                        namespaced_username, existing_user.student_profile.student_id, student_obj.student_id
                    )
                    return
            existing_user.set_password(password)
            existing_user.save()
            student_obj.user = existing_user
            student_obj.save(update_fields=['user'])
        else:
            user = User.objects.create_user(username=namespaced_username, password=password)
            student_obj.user = user
            student_obj.save(update_fields=['user'])


def _resolve_or_create_teacher(teacher_data):
    """
    Get or create a Teacher from the payload's teacher field.
    teacher_data can have: name (required), slug (optional).
    If slug is provided, match by slug. Otherwise create new.
    """
    if not teacher_data or not teacher_data.get('name'):
        return None, "Missing teacher data or teacher name in payload"

    slug = teacher_data.get('slug', '').strip()
    name = teacher_data['name'].strip()

    if slug:
        teacher, created = Teacher.objects.update_or_create(
            slug=slug,
            defaults={'name': name}
        )
    else:
        # No slug provided — create new teacher with auto-generated slug
        teacher = Teacher(name=name)
        teacher.save()  # save() auto-generates slug

    return teacher, None


def run_sync_upsert(payload_data, teacher):
    """
    Core sync transactional upsert logic, scoped to a teacher.
    Returns (success: bool, upserted_counts: dict, skipped_records: list, error_message: str)
    """
    upserted_counts = {model_name: 0 for model_name in MODEL_REGISTRY.keys()}
    skipped_records = []

    # Teacher is no longer in the sync sequence — it's resolved from the payload
    sync_sequence = [
        'ACADEMIC_YEAR',
        'SUBJECT',
        'ACADEMIC_CENTER',
        'CLASS_GROUP',
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

                # Determine the desktop identifier field
                if model_key == 'STUDENT':
                    desktop_id_field = 'student_id'
                else:
                    desktop_id_field = 'id'

                # Pre-fetch FK objects scoped to this teacher
                fk_caches = {}
                for fk_payload_field, (orm_field, fk_model, fk_lookup) in FK_FIELD_MAP.items():
                    if any(fk_payload_field in r for r in records):
                        fk_caches[fk_payload_field] = _prefetch_fk_objects_scoped(
                            records, fk_payload_field, fk_model, teacher, fk_lookup
                        )

                # Pre-fetch student FK objects (for non-Student models that reference students)
                if model_key != 'STUDENT' and any('student_id' in r for r in records):
                    student_ids = {str(r['student_id']) for r in records if 'student_id' in r}
                    fk_caches['student_id'] = {
                        str(s.student_id): s
                        for s in Student.objects.filter(teacher=teacher, student_id__in=student_ids)
                    }

                for record in records:
                    desktop_id_val = record.get(desktop_id_field)
                    if not desktop_id_val:
                        skipped_records.append({
                            'model': model_key,
                            'record': record,
                            'reason': f'Missing desktop identifier field: {desktop_id_field}'
                        })
                        continue

                    desktop_id_val = str(desktop_id_val)

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

                    # Remove the desktop ID field from defaults (it's used for matching)
                    upsert_data.pop(desktop_id_field, None)

                    # For STUDENT: extract auth fields before DB upsert
                    student_username = None
                    student_password = None
                    if model_key == 'STUDENT':
                        student_username = upsert_data.pop('username', desktop_id_val)
                        student_password = upsert_data.pop('password', desktop_id_val)
                        upsert_data.pop('user', None)

                    # Resolve FK fields (scoped to teacher)
                    fk_resolved = True
                    for fk_payload_field, (orm_field, fk_model, fk_lookup) in FK_FIELD_MAP.items():
                        if fk_payload_field in upsert_data:
                            fk_val = str(upsert_data.pop(fk_payload_field))
                            cache = fk_caches.get(fk_payload_field, {})
                            fk_obj = cache.get(fk_val)
                            if fk_obj is None:
                                skipped_records.append({
                                    'model': model_key,
                                    'record': record,
                                    'reason': f'Referenced {orm_field} with desktop_id={fk_val} does not exist for this teacher'
                                })
                                fk_resolved = False
                                break
                            upsert_data[orm_field] = fk_obj

                    if not fk_resolved:
                        continue

                    # Resolve student FK (for non-Student models)
                    if 'student_id' in upsert_data and model_key != 'STUDENT':
                        student_val = str(upsert_data.pop('student_id'))
                        student_cache = fk_caches.get('student_id', {})
                        student_obj = student_cache.get(student_val)
                        if student_obj is None:
                            skipped_records.append({
                                'model': model_key,
                                'record': record,
                                'reason': f'Referenced student with student_id={student_val} does not exist for this teacher'
                            })
                            continue
                        upsert_data['student'] = student_obj

                    # Remove any teacher_id from data (teacher is set from payload)
                    upsert_data.pop('teacher_id', None)

                    # Set teacher on the record
                    upsert_data['teacher'] = teacher

                    # Build the lookup kwargs for update_or_create
                    if model_key == 'STUDENT':
                        lookup_kwargs = {'teacher': teacher, 'student_id': desktop_id_val}
                    else:
                        lookup_kwargs = {'teacher': teacher, 'desktop_id': desktop_id_val}
                        # Also store the desktop_id in defaults if not in lookup
                        # (desktop_id is in lookup, not defaults)

                    obj, created = model_class.objects.update_or_create(
                        **lookup_kwargs,
                        defaults=upsert_data
                    )
                    upserted_counts[model_key] += 1

                    if model_key == 'STUDENT' and student_username is not None:
                        _handle_student_user(obj, teacher, student_username, student_password)

        return True, upserted_counts, skipped_records, None

    except Exception as e:
        logger.exception("Sync upsert failed: %s", str(e))
        return False, {}, [], str(e)
