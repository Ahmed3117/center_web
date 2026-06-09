from rest_framework import serializers
from dashboard.models import (
    Student,
    GroupSubscription,
    Attendance,
    ExamResult,
    Payment,
)
from dashboard.serializers import AcademicYearSerializer, GroupScheduleSerializer


class StudentSelfSubscriptionSerializer(serializers.ModelSerializer):
    """Subscription details for the student's own profile"""
    group_id = serializers.UUIDField(source='group.id')
    group_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='group.subject.name')
    center_name = serializers.CharField(source='group.center.name')
    schedules = GroupScheduleSerializer(source='group.schedules', many=True, read_only=True)

    class Meta:
        model = GroupSubscription
        fields = [
            'group_id',
            'group_name',
            'subject_name',
            'center_name',
            'subscription_type',
            'price',
            'schedules',
            'created_at'
        ]

    def get_group_name(self, obj):
        return f"{obj.group.name} ({obj.group.center.name})"


class StudentSelfAttendanceSerializer(serializers.ModelSerializer):
    """Attendance record for the student's own history"""
    session_id = serializers.UUIDField(source='session.id')
    session_date = serializers.DateTimeField(source='session.session_date')
    group_name = serializers.SerializerMethodField()
    status = serializers.CharField(source='session.status')

    class Meta:
        model = Attendance
        fields = [
            'session_id',
            'session_date',
            'group_name',
            'is_present',
            'notes',
            'status'
        ]

    def get_group_name(self, obj):
        return f"{obj.session.group.name} ({obj.session.group.center.name})"


class StudentSelfExamResultSerializer(serializers.ModelSerializer):
    """Exam result for the student's own history"""
    exam_id = serializers.UUIDField(source='exam.id')
    exam_name = serializers.CharField(source='exam.name')
    exam_date = serializers.DateField(source='exam.exam_date')
    max_score = serializers.DecimalField(source='exam.max_score', max_digits=6, decimal_places=2)
    group_name = serializers.SerializerMethodField()

    class Meta:
        model = ExamResult
        fields = [
            'exam_id',
            'exam_name',
            'exam_date',
            'student_score',
            'max_score',
            'group_name'
        ]

    def get_group_name(self, obj):
        return f"{obj.exam.group.name} ({obj.exam.group.center.name})"


class StudentSelfPaymentSerializer(serializers.ModelSerializer):
    """Payment record for the student's own history"""
    class Meta:
        model = Payment
        fields = ['id', 'amount', 'payment_date', 'description']


class StudentSelfProfileSerializer(serializers.ModelSerializer):
    """Full profile for a logged-in student — all their info in one response"""
    academic_year = AcademicYearSerializer(read_only=True)
    subscriptions = StudentSelfSubscriptionSerializer(many=True, read_only=True)
    attendance_history = StudentSelfAttendanceSerializer(
        source='attendance_records', many=True, read_only=True
    )
    exam_results = StudentSelfExamResultSerializer(many=True, read_only=True)
    payments = StudentSelfPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Student
        fields = [
            'student_id',
            'full_name',
            'phone_number',
            'parent_phone_number',
            'academic_year',
            'section',
            'subscriptions',
            'attendance_history',
            'exam_results',
            'payments'
        ]
