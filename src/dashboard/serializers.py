from rest_framework import serializers
from django.db.models import Avg, Max, Min
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

# ----------------- BASIC HELPERS -----------------

class TeacherPublicSerializer(serializers.ModelSerializer):
    """Public teacher info — used on homepage for students to select a teacher"""
    class Meta:
        model = Teacher
        fields = [
            'id', 'name', 'slug', 'image', 'bio',
            'facebook_url', 'linkedin_url', 'instagram_url',
            'youtube_url', 'telegram_url', 'tweeter_url'
        ]


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ['id', 'name', 'level']


class AcademicCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicCenter
        fields = ['id', 'name', 'location']


class SubjectSerializer(serializers.ModelSerializer):
    academic_year = AcademicYearSerializer(read_only=True)

    class Meta:
        model = Subject
        fields = ['id', 'name', 'academic_year']


class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = [
            'id', 'name', 'slug', 'image', 'bio',
            'facebook_url', 'linkedin_url', 'instagram_url',
            'youtube_url', 'telegram_url', 'tweeter_url'
        ]


class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = [
            'id', 'name', 'slug', 'image', 'bio',
            'facebook_url', 'linkedin_url', 'instagram_url',
            'youtube_url', 'telegram_url', 'tweeter_url'
        ]
        read_only_fields = ['id', 'slug']





# ----------------- STUDENT SERIALIZERS -----------------

class StudentListSerializer(serializers.ModelSerializer):
    """Serializer for Student List View"""
    academic_year = AcademicYearSerializer(read_only=True)
    teacher = TeacherPublicSerializer(read_only=True)

    class Meta:
        model = Student
        fields = [
            'id',
            'student_id',
            'full_name',
            'phone_number',
            'parent_phone_number',
            'academic_year',
            'section',
            'created_at',
            'teacher'
        ]


class StudentSubscriptionSerializer(serializers.ModelSerializer):
    """Nested subscription detail inside Student Profile"""
    group_id = serializers.CharField(source='group.id')
    group_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='group.subject.name')

    class Meta:
        model = GroupSubscription
        fields = [
            'group_id',
            'group_name',
            'subject_name',
            'subscription_type',
            'price'
        ]

    def get_group_name(self, obj):
        """Return group name with center name, e.g. 'مجموعة 3 (ألفا شبرا)'"""
        return f"{obj.group.name} ({obj.group.center.name})"


class StudentAttendanceSerializer(serializers.ModelSerializer):
    """Nested attendance details inside Student Profile"""
    session_id = serializers.CharField(source='session.id')
    session_date = serializers.DateTimeField(source='session.session_date')
    group_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            'session_id',
            'session_date',
            'group_name',
            'is_present',
            'notes'
        ]

    def get_group_name(self, obj):
        """Return group name with center name, e.g. 'مجموعة 5 (مكة الهرم)'"""
        return f"{obj.session.group.name} ({obj.session.group.center.name})"


class StudentExamResultSerializer(serializers.ModelSerializer):
    """Nested exam results inside Student Profile"""
    exam_name = serializers.CharField(source='exam.name')
    exam_date = serializers.DateField(source='exam.exam_date')
    max_score = serializers.DecimalField(source='exam.max_score', max_digits=6, decimal_places=2)

    class Meta:
        model = ExamResult
        fields = [
            'exam_id',
            'exam_name',
            'exam_date',
            'student_score',
            'max_score'
        ]


class StudentPaymentSerializer(serializers.ModelSerializer):
    """Nested payments inside Student Profile"""
    class Meta:
        model = Payment
        fields = ['id', 'amount', 'payment_date', 'description']


class StudentDetailSerializer(serializers.ModelSerializer):
    """Serializer for Complete Student Profile Detail View"""
    academic_year = AcademicYearSerializer(read_only=True)
    teacher = TeacherPublicSerializer(read_only=True)
    subscriptions = StudentSubscriptionSerializer(many=True, read_only=True)
    attendance_history = StudentAttendanceSerializer(source='attendance_records', many=True, read_only=True)
    exam_results = StudentExamResultSerializer(many=True, read_only=True)
    payments = StudentPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Student
        fields = [
            'id',
            'student_id',
            'full_name',
            'phone_number',
            'parent_phone_number',
            'academic_year',
            'section',
            'teacher',
            'subscriptions',
            'attendance_history',
            'exam_results',
            'payments'
        ]

# ----------------- GROUP SERIALIZERS -----------------

class ClassGroupListSerializer(serializers.ModelSerializer):
    """Serializer for Group Directory List View"""
    academic_year = serializers.CharField(source='academic_year.name')
    subject = serializers.CharField(source='subject.name')
    center = AcademicCenterSerializer(read_only=True)
    teacher = TeacherPublicSerializer(read_only=True)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = ClassGroup
        fields = [
            'id',
            'name',
            'academic_year',
            'subject',
            'center',
            'teacher',
            'student_count'
        ]

    def get_student_count(self, obj):
        return obj.subscriptions.count()


class GroupEnrolledStudentSerializer(serializers.ModelSerializer):
    """Nested student enrolment details inside Group Profile"""
    student_id = serializers.CharField(source='student.student_id')
    full_name = serializers.CharField(source='student.full_name')

    class Meta:
        model = GroupSubscription
        fields = [
            'student_id',
            'full_name',
            'subscription_type',
            'price'
        ]


class GroupSessionSerializer(serializers.ModelSerializer):
    """Nested past sessions lists inside Group Profile"""
    session_id = serializers.CharField(source='id', read_only=True)
    attendance_summary = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = [
            'session_id',
            'session_date',
            'status',
            'attendance_summary'
        ]

    def get_attendance_summary(self, obj):
        return {
            "present_count": obj.attendance_records.filter(is_present=True).count(),
            "absent_count": obj.attendance_records.filter(is_present=False).count()
        }


class ClassGroupDetailSerializer(serializers.ModelSerializer):
    """Serializer for Detailed Group view"""
    center_name = serializers.CharField(source='center.name')
    subject_name = serializers.CharField(source='subject.name')
    teacher = TeacherPublicSerializer(read_only=True)
    enrolled_students = GroupEnrolledStudentSerializer(source='subscriptions', many=True, read_only=True)
    sessions = GroupSessionSerializer(many=True, read_only=True)

    class Meta:
        model = ClassGroup
        fields = [
            'id',
            'name',
            'center_name',
            'subject_name',
            'teacher',
            'enrolled_students',
            'sessions'
        ]

# ----------------- SESSION ATTENDANCE SERIALIZERS -----------------

class SessionAttendanceRecordSerializer(serializers.ModelSerializer):
    """Single attendance record item in a Session"""
    student_id = serializers.CharField(source='student.student_id')
    student_name = serializers.CharField(source='student.full_name')

    class Meta:
        model = Attendance
        fields = [
            'student_id',
            'student_name',
            'is_present',
            'notes'
        ]


class SessionAttendanceSerializer(serializers.ModelSerializer):
    """Serializer for Session Attendance view"""
    session_id = serializers.CharField(source='id', read_only=True)
    group_name = serializers.CharField(source='group.name')
    attendance_list = SessionAttendanceRecordSerializer(source='attendance_records', many=True, read_only=True)

    class Meta:
        model = Session
        fields = [
            'session_id',
            'session_date',
            'group_name',
            'attendance_list'
        ]

# ----------------- EXAMS SERIALIZERS -----------------

class ExamListSerializer(serializers.ModelSerializer):
    """Serializer for Exam List View"""
    group_name = serializers.SerializerMethodField()
    statistics = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            'id',
            'name',
            'group_name',
            'max_score',
            'exam_date',
            'statistics'
        ]

    def get_group_name(self, obj):
        """Return group name with center name, e.g. 'مجموعة 3 (ألفا شبرا)'"""
        if obj.group:
            return f"{obj.group.name} ({obj.group.center.name})"
        return "N/A"

    def get_statistics(self, obj):
        stats = obj.results.aggregate(
            highest=Max('student_score'),
            lowest=Min('student_score'),
            average=Avg('student_score')
        )
        return {
            "highest_score": stats['highest'] or 0.00,
            "lowest_score": stats['lowest'] or 0.00,
            "average_score": round(stats['average'] or 0.00, 2)
        }


class ExamResultDetailSerializer(serializers.ModelSerializer):
    """Nested student score inside Exam Result Detailed View"""
    student_id = serializers.CharField(source='student.student_id')
    student_name = serializers.CharField(source='student.full_name')

    class Meta:
        model = ExamResult
        fields = [
            'student_id',
            'student_name',
            'student_score'
        ]


class ExamDetailSerializer(serializers.ModelSerializer):
    """Serializer for Exam Results Detailed View"""
    exam_id = serializers.CharField(source='id', read_only=True)
    exam_name = serializers.CharField(source='name')
    results = ExamResultDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Exam
        fields = [
            'exam_id',
            'exam_name',
            'max_score',
            'results'
        ]
