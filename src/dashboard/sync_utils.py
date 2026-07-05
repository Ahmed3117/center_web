import logging
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
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


def _batch_handle_student_users(student_user_tasks, teacher):
    """
    Batch create/update Django auth Users for students.
    Pre-hashes all passwords BEFORE touching the DB to minimize transaction time.
    Uses change-detection signature to avoid hashing/DB writes for unmodified passwords.

    student_user_tasks: list of (student_obj, username, password)
    """
    import hashlib
    from django.conf import settings

    if not student_user_tasks:
        return

    # Phase 1: Filter tasks needing updates and pre-hash only when changed
    hashed_tasks = []

    for student_obj, username, password in student_user_tasks:
        namespaced_username = f"{teacher.slug}_{username}"
        # Generate a fast signature of the raw password to detect changes
        sig = hashlib.sha256((password + settings.SECRET_KEY).encode('utf-8')).hexdigest()

        # If password hash matches, the namespaced username is correct, and user is linked, skip hashing
        if student_obj.password_hash == sig and student_obj.user_id:
            if student_obj.user and student_obj.user.username == namespaced_username:
                continue

        hashed_pw = make_password(password)
        hashed_tasks.append((student_obj, namespaced_username, hashed_pw, sig))

    if not hashed_tasks:
        return

    # Phase 2: Batch DB operations
    all_usernames = {t[1] for t in hashed_tasks}
    existing_users_map = {
        u.username: u
        for u in User.objects.filter(username__in=all_usernames)
    }

    users_to_create = []
    users_to_update = []
    students_to_link = []  # (student_obj, user_obj) pairs to update student.user FK
    students_to_update_hash_fields = []

    for student_obj, namespaced_username, hashed_pw, sig in hashed_tasks:
        student_obj.password_hash = sig
        students_to_update_hash_fields.append(student_obj)

        if student_obj.user:
            user = student_obj.user
            user.username = namespaced_username
            user.password = hashed_pw
            users_to_update.append(user)
        elif namespaced_username in existing_users_map:
            existing_user = existing_users_map[namespaced_username]
            if hasattr(existing_user, 'student_profile') and existing_user.student_profile is not None:
                if existing_user.student_profile.pk != student_obj.pk:
                    logger.warning(
                        "Username '%s' already belongs to another student '%s', cannot assign to '%s'.",
                        namespaced_username, existing_user.student_profile.student_id, student_obj.student_id
                    )
                    continue
            existing_user.password = hashed_pw
            users_to_update.append(existing_user)
            students_to_link.append((student_obj, existing_user))
        else:
            new_user = User(username=namespaced_username, password=hashed_pw)
            users_to_create.append((student_obj, new_user))

    # Bulk update existing users
    if users_to_update:
        User.objects.bulk_update(users_to_update, ['username', 'password'], batch_size=100)

    # Bulk create new users
    if users_to_create:
        new_user_objects = [u for _, u in users_to_create]
        User.objects.bulk_create(new_user_objects, batch_size=100)
        # Link newly created users to students
        for student_obj, new_user in users_to_create:
            students_to_link.append((student_obj, new_user))

    # Bulk update student fields (user FK + password_hash)
    if students_to_link:
        for student_obj, user_obj in students_to_link:
            student_obj.user = user_obj

    # Save both user and password_hash in a single bulk_update call
    if students_to_update_hash_fields:
        Student.objects.bulk_update(
            students_to_update_hash_fields,
            ['user', 'password_hash'],
            batch_size=100
        )


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

    # Collect student user tasks to batch-process after the main upsert loop
    student_user_tasks = []  # list of (student_obj, username, password)

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

                objs_to_upsert = []
                student_creds_map = {}
                model_field_names = {f.name for f in model_class._meta.fields}

                # Pre-fetch existing model instances to preserve primary keys (id) and relations
                existing_instances = {
                    str(getattr(obj, 'student_id' if model_key == 'STUDENT' else 'desktop_id')): obj
                    for obj in model_class.objects.filter(teacher=teacher)
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

                    # Build the constructor/lookup kwargs
                    if model_key == 'STUDENT':
                        lookup_kwargs = {'teacher': teacher, 'student_id': desktop_id_val}
                    else:
                        lookup_kwargs = {'teacher': teacher, 'desktop_id': desktop_id_val}

                    # Filter clean fields only
                    constructor_kwargs = {**lookup_kwargs, **upsert_data}

                    # Reuse existing PK and relations if updating to prevent duplicate insert/returning mismatch
                    existing_obj = existing_instances.get(desktop_id_val)
                    if existing_obj:
                        constructor_kwargs['id'] = existing_obj.id
                        if model_key == 'STUDENT':
                            if existing_obj.user_id:
                                constructor_kwargs['user'] = existing_obj.user
                            if existing_obj.password_hash:
                                constructor_kwargs['password_hash'] = existing_obj.password_hash

                    clean_constructor_kwargs = {k: v for k, v in constructor_kwargs.items() if k in model_field_names}

                    # Instantiate object (autogenerating UUID primary key if needed)
                    obj = model_class(**clean_constructor_kwargs)
                    objs_to_upsert.append(obj)

                    if model_key == 'STUDENT':
                        student_creds_map[desktop_id_val] = (student_username, student_password)

                if objs_to_upsert:
                    # Determine update fields and unique fields for bulk_create
                    update_fields = [
                        f.name for f in model_class._meta.fields
                        if not f.primary_key and f.name not in ['teacher', 'desktop_id', 'student_id', 'user', 'password_hash']
                    ]
                    if model_key == 'STUDENT':
                        unique_fields = ['teacher_id', 'student_id']
                    else:
                        unique_fields = ['teacher_id', 'desktop_id']

                    upserted_objs = model_class.objects.bulk_create(
                        objs_to_upsert,
                        update_conflicts=True,
                        unique_fields=unique_fields,
                        update_fields=update_fields
                    )

                    upserted_counts[model_key] += len(upserted_objs)

                    if model_key == 'STUDENT':
                        for obj in upserted_objs:
                            creds = student_creds_map.get(obj.student_id)
                            if creds:
                                student_user_tasks.append((obj, creds[0], creds[1]))

            # Batch process all student user accounts at end of transaction
            _batch_handle_student_users(student_user_tasks, teacher)

        return True, upserted_counts, skipped_records, None

    except Exception as e:
        logger.exception("Sync upsert failed: %s", str(e))
        return False, {}, [], str(e)
