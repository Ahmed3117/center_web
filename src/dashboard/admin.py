from django.contrib import admin
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

# ----------------- INLINES -----------------

class GroupScheduleInline(admin.TabularInline):
    model = GroupSchedule
    extra = 1
    verbose_name = "موعد الحصة"
    verbose_name_plural = "مواعيد الحصص الأسبوعية"


class GroupSubscriptionInline(admin.TabularInline):
    model = GroupSubscription
    extra = 1
    verbose_name = "اشتراك مجموعة"
    verbose_name_plural = "اشتراكات الطالب في المجموعات"


class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    verbose_name = "تسجيل حضور"
    verbose_name_plural = "سجل حضور الحصة"
    raw_id_fields = ('student',)


class ExamResultInline(admin.TabularInline):
    model = ExamResult
    extra = 0
    verbose_name = "درجة الطالب"
    verbose_name_plural = "درجات الطلاب في الامتحان"
    raw_id_fields = ('student',)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 1
    verbose_name = "سجل مدفوعات"
    verbose_name_plural = "المدفوعات والاشتراكات المالية"

# ----------------- ADMIN MODELS -----------------

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'level')
    search_fields = ('name',)
    ordering = ('level',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'academic_year')
    list_filter = ('academic_year',)
    search_fields = ('name',)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(AcademicCenter)
class AcademicCenterAdmin(admin.ModelAdmin):
    list_display = ('name', 'location')
    search_fields = ('name', 'location')


@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'academic_year', 'center', 'teacher', 'get_student_count', 'created_at')
    list_filter = ('academic_year', 'subject', 'center', 'teacher')
    search_fields = ('name', 'subject__name', 'center__name')
    inlines = [GroupScheduleInline]
    readonly_fields = ('created_at',)

    def get_student_count(self, obj):
        return obj.subscriptions.count()
    get_student_count.short_description = "عدد الطلاب المشتركين"


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'full_name', 'phone_number', 'parent_phone_number', 'academic_year', 'section', 'created_at')
    list_filter = ('academic_year', 'section')
    search_fields = ('student_id', 'full_name', 'phone_number', 'parent_phone_number')
    inlines = [GroupSubscriptionInline, PaymentInline]
    readonly_fields = ('created_at',)


@admin.register(GroupSubscription)
class GroupSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('student', 'group', 'subscription_type', 'price', 'created_at')
    list_filter = ('subscription_type', 'group__center', 'group')
    search_fields = ('student__full_name', 'student__student_id', 'group__name')
    raw_id_fields = ('student', 'group')


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('group', 'session_date', 'status', 'get_present_count', 'get_absent_count')
    list_filter = ('group__center', 'group', 'session_date', 'status')
    search_fields = ('group__name', 'group__subject__name')
    inlines = [AttendanceInline]

    def get_present_count(self, obj):
        return obj.attendance_records.filter(is_present=True).count()
    get_present_count.short_description = "عدد الحضور"

    def get_absent_count(self, obj):
        return obj.attendance_records.filter(is_present=False).count()
    get_absent_count.short_description = "عدد الغياب"


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'get_group_name', 'session', 'is_present', 'notes')
    list_filter = ('is_present', 'session__group__center', 'session__group')
    search_fields = ('student__full_name', 'student__student_id', 'session__group__name')
    raw_id_fields = ('student', 'session')

    def get_group_name(self, obj):
        return obj.session.group.name
    get_group_name.short_description = "المجموعة"


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'max_score', 'exam_date')
    list_filter = ('group__center', 'group', 'exam_date')
    search_fields = ('name', 'group__name')
    inlines = [ExamResultInline]


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'student_score', 'get_max_score')
    list_filter = ('exam__group__center', 'exam')
    search_fields = ('student__full_name', 'student__student_id', 'exam__name')
    raw_id_fields = ('student', 'exam')

    def get_max_score(self, obj):
        return obj.exam.max_score
    get_max_score.short_description = "الدرجة النهائية"


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('student', 'amount', 'payment_date', 'description')
    list_filter = ('payment_date',)
    search_fields = ('student__full_name', 'student__student_id', 'description')
    raw_id_fields = ('student',)
