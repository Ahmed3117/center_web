from rest_framework import serializers
from dashboard.models import (
    Student,
    GroupSubscription,
    Attendance,
    ExamResult,
    Payment,
    Teacher,
)


class StudentTeacherSerializer(serializers.ModelSerializer):
    """Teacher info included in student responses"""
    class Meta:
        model = Teacher
        fields = ['name', 'slug']


class StudentSelfProfileSerializer(serializers.ModelSerializer):
    """Full Student Self-Profile — all related data in one call"""
    academic_year = serializers.CharField(source='academic_year.name')
    teacher = StudentTeacherSerializer(read_only=True)
    subscriptions = serializers.SerializerMethodField()
    attendance_history = serializers.SerializerMethodField()
    exam_results = serializers.SerializerMethodField()
    payments = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
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

    def get_subscriptions(self, obj):
        return StudentSelfSubscriptionSerializer(
            obj.subscriptions.select_related('group__subject', 'group__center'),
            many=True
        ).data

    def get_attendance_history(self, obj):
        return StudentSelfAttendanceSerializer(
            obj.attendance_records.select_related('session__group__center').order_by('-session__session_date'),
            many=True
        ).data

    def get_exam_results(self, obj):
        return StudentSelfExamResultSerializer(
            obj.exam_results.select_related('exam__group').order_by('-exam__exam_date'),
            many=True
        ).data

    def get_payments(self, obj):
        return StudentSelfPaymentSerializer(
            obj.payments.order_by('-payment_date'),
            many=True
        ).data


class StudentSelfSubscriptionSerializer(serializers.ModelSerializer):
    """Single subscription item for a student"""
    group_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source='group.subject.name')
    center_name = serializers.CharField(source='group.center.name')

    class Meta:
        model = GroupSubscription
        fields = [
            'group_name',
            'subject_name',
            'center_name',
            'subscription_type',
            'price'
        ]

    def get_group_name(self, obj):
        return obj.group.name


class StudentSelfAttendanceSerializer(serializers.ModelSerializer):
    """Single attendance record for a student"""
    session_date = serializers.DateTimeField(source='session.session_date')
    group_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            'session_date',
            'group_name',
            'is_present',
            'notes'
        ]

    def get_group_name(self, obj):
        return f"{obj.session.group.name} ({obj.session.group.center.name})"


class StudentSelfExamResultSerializer(serializers.ModelSerializer):
    """Single exam result for a student"""
    exam_name = serializers.CharField(source='exam.name')
    exam_date = serializers.DateField(source='exam.exam_date')
    max_score = serializers.DecimalField(source='exam.max_score', max_digits=6, decimal_places=2)

    class Meta:
        model = ExamResult
        fields = [
            'exam_name',
            'exam_date',
            'student_score',
            'max_score'
        ]


class StudentSelfPaymentSerializer(serializers.ModelSerializer):
    """Single payment record for a student"""
    class Meta:
        model = Payment
        fields = [
            'amount',
            'payment_date',
            'description'
        ]
