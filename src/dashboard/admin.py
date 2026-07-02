from django.contrib import admin
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


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'user', 'id')
    search_fields = ('name', 'slug', 'user__username')
    readonly_fields = ('id', 'slug')
    raw_id_fields = ('user',)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'teacher', 'desktop_id')
    list_filter = ('teacher',)
    search_fields = ('name',)
    readonly_fields = ('id', 'desktop_id')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'academic_year', 'teacher', 'desktop_id')
    list_filter = ('teacher', 'academic_year')
    search_fields = ('name',)
    readonly_fields = ('id', 'desktop_id')


@admin.register(AcademicCenter)
class AcademicCenterAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'teacher', 'desktop_id')
    list_filter = ('teacher',)
    search_fields = ('name', 'location')
    readonly_fields = ('id', 'desktop_id')


class GroupSubscriptionInline(admin.TabularInline):
    model = GroupSubscription
    extra = 0
    fields = ('student', 'subscription_type', 'price', 'created_at', 'desktop_id')
    readonly_fields = ('desktop_id',)


class SessionInline(admin.TabularInline):
    model = Session
    extra = 0
    fields = ('session_date', 'status', 'desktop_id')
    readonly_fields = ('desktop_id',)


class ExamInline(admin.TabularInline):
    model = Exam
    extra = 0
    fields = ('name', 'max_score', 'exam_date', 'desktop_id')
    readonly_fields = ('desktop_id',)


@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'center', 'teacher', 'created_at', 'desktop_id')
    list_filter = ('teacher', 'center', 'academic_year')
    search_fields = ('name', 'subject__name', 'center__name')
    readonly_fields = ('id', 'desktop_id')
    inlines = [GroupSubscriptionInline, SessionInline, ExamInline]


class StudentSubscriptionInline(admin.TabularInline):
    model = GroupSubscription
    extra = 0
    fields = ('group', 'subscription_type', 'price', 'created_at', 'desktop_id')
    readonly_fields = ('desktop_id',)


class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    fields = ('session', 'is_present', 'notes', 'desktop_id')
    readonly_fields = ('desktop_id',)


class ExamResultInline(admin.TabularInline):
    model = ExamResult
    extra = 0
    fields = ('exam', 'student_score', 'desktop_id')
    readonly_fields = ('desktop_id',)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ('amount', 'payment_date', 'description', 'desktop_id')
    readonly_fields = ('desktop_id',)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'full_name', 'phone_number', 'academic_year', 'teacher', 'created_at')
    list_filter = ('teacher', 'academic_year')
    search_fields = ('student_id', 'full_name', 'phone_number', 'parent_phone_number')
    readonly_fields = ('id',)
    inlines = [StudentSubscriptionInline, AttendanceInline, ExamResultInline, PaymentInline]


@admin.register(GroupSubscription)
class GroupSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('student', 'group', 'subscription_type', 'price', 'teacher', 'desktop_id')
    list_filter = ('teacher', 'subscription_type')
    search_fields = ('student__full_name', 'group__name')
    readonly_fields = ('id', 'desktop_id')


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('group', 'session_date', 'status', 'teacher', 'desktop_id')
    list_filter = ('teacher', 'status')
    search_fields = ('group__name',)
    readonly_fields = ('id', 'desktop_id')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'is_present', 'teacher', 'desktop_id')
    list_filter = ('teacher', 'is_present')
    search_fields = ('student__full_name',)
    readonly_fields = ('id', 'desktop_id')


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'max_score', 'exam_date', 'teacher', 'desktop_id')
    list_filter = ('teacher',)
    search_fields = ('name', 'group__name')
    readonly_fields = ('id', 'desktop_id')


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'student_score', 'teacher', 'desktop_id')
    list_filter = ('teacher',)
    search_fields = ('student__full_name', 'exam__name')
    readonly_fields = ('id', 'desktop_id')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('student', 'amount', 'payment_date', 'teacher', 'desktop_id')
    list_filter = ('teacher',)
    search_fields = ('student__full_name', 'description')
    readonly_fields = ('id', 'desktop_id')
