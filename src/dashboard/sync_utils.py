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
    'TEACHER': Teacher,
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


def run_sync_upsert(payload_data, center_id=None):
    """
    Core sync transactional upsert logic.
    Returns (success: bool, upserted_counts: dict, skipped_records: list, error_message: str)
    """
    upserted_counts = {model_name: 0 for model_name in MODEL_REGISTRY.keys()}
    skipped_records = []

    sync_sequence = [
        'ACADEMIC_YEAR',
        'SUBJECT',
        'ACADEMIC_CENTER',
        'TEACHER',
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

        return True, upserted_counts, skipped_records, None

    except Exception as e:
        logger.exception("Sync upsert failed: %s", str(e))
        return False, {}, [], str(e)
