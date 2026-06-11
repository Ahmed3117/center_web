import uuid
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone


class AcademicYear(models.Model):
    """الصف الدراسي"""
    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="اسم الصف الدراسي")
    level = models.IntegerField(verbose_name="المستوى الدراسي")

    class Meta:
        verbose_name = "الصف الدراسي"
        verbose_name_plural = "الصفوف الدراسية"
        ordering = ['level']

    def __str__(self):
        return self.name


class Subject(models.Model):
    """المادة الدراسية"""
    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name="اسم المادة")
    academic_year = models.ForeignKey(
        AcademicYear, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='subjects', 
        verbose_name="الصف الدراسي"
    )

    class Meta:
        verbose_name = "المادة الدراسية"
        verbose_name_plural = "المواد الدراسية"
        ordering = ['name']

    def __str__(self):
        if self.academic_year:
            return f"{self.name} - {self.academic_year.name}"
        return self.name


class Teacher(models.Model):
    """المدرس"""
    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, verbose_name="اسم المدرس")

    class Meta:
        verbose_name = "المدرس"
        verbose_name_plural = "المدرسين"
        ordering = ['name']

    def __str__(self):
        return self.name


class AcademicCenter(models.Model):
    """السنتر / المركز التعليمي"""
    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, verbose_name="اسم السنتر")
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="موقع السنتر")

    class Meta:
        verbose_name = "السنتر"
        verbose_name_plural = "السناتر / المراكز"
        ordering = ['name']

    def __str__(self):
        return self.name


class ClassGroup(models.Model):
    """المجموعة"""
    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, verbose_name="اسم المجموعة")
    academic_year = models.ForeignKey(
        AcademicYear, 
        on_delete=models.CASCADE, 
        related_name='groups', 
        verbose_name="الصف الدراسي"
    )
    subject = models.ForeignKey(
        Subject, 
        on_delete=models.CASCADE, 
        related_name='groups', 
        verbose_name="المادة"
    )
    center = models.ForeignKey(
        AcademicCenter, 
        on_delete=models.CASCADE, 
        related_name='groups', 
        verbose_name="السنتر"
    )
    teacher = models.ForeignKey(
        Teacher, 
        on_delete=models.CASCADE, 
        related_name='groups', 
        verbose_name="المدرس"
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="تاريخ الإنشاء")

    class Meta:
        verbose_name = "المجموعة"
        verbose_name_plural = "المجموعات"

    def __str__(self):
        return f"{self.name} ({self.subject.name} - {self.center.name})"


class Student(models.Model):
    """الطالب"""
    # Using CharField as PK to handle custom scanner or typed student codes (كود الطالب)
    student_id = models.CharField(primary_key=True, max_length=100, verbose_name="كود الطالب")
    full_name = models.CharField(max_length=255, verbose_name="اسم الطالب")
    phone_number = models.CharField(max_length=50, blank=True, default='', verbose_name="رقم تليفون الطالب")
    parent_phone_number = models.CharField(max_length=50, blank=True, default='', verbose_name="رقم تليفون ولي الأمر")
    academic_year = models.ForeignKey(
        AcademicYear, 
        on_delete=models.CASCADE, 
        related_name='students', 
        verbose_name="الصف الدراسي"
    )
    section = models.CharField(max_length=100, blank=True, null=True, verbose_name="الشعبة")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="تاريخ التسجيل")
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='student_profile',
        verbose_name="حساب المستخدم"
    )

    class Meta:
        verbose_name = "الطالب"
        verbose_name_plural = "الطلاب"

    def __str__(self):
        return f"{self.full_name} ({self.student_id})"


@receiver(post_delete, sender=Student)
def delete_student_user_account(sender, instance, **kwargs):
    """When a Student is deleted, also delete their linked auth User account."""
    if instance.user_id:
        User.objects.filter(pk=instance.user_id).delete()


class GroupSubscription(models.Model):
    """اشتراك الطالب في المجموعة"""
    SUBSCRIPTION_CHOICES = [
        ('شهري', 'شهري'),
        ('بالحصة', 'بالحصة'),
        ('إعفاء', 'إعفاء'),
    ]

    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE, 
        related_name='subscriptions', 
        verbose_name="الطالب"
    )
    group = models.ForeignKey(
        ClassGroup, 
        on_delete=models.CASCADE, 
        related_name='subscriptions', 
        verbose_name="المجموعة"
    )
    subscription_type = models.CharField(
        max_length=50, 
        choices=SUBSCRIPTION_CHOICES, 
        verbose_name="نوع الاشتراك"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="سعر الاشتراك")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="تاريخ الاشتراك")

    class Meta:
        verbose_name = "اشتراك الطالب"
        verbose_name_plural = "اشتراكات الطلاب"
        unique_together = ('student', 'group')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.full_name} in {self.group.name} ({self.subscription_type})"


class Session(models.Model):
    """الحصة الفعلية"""
    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        ClassGroup, 
        on_delete=models.CASCADE, 
        related_name='sessions', 
        verbose_name="المجموعة"
    )
    session_date = models.DateTimeField(verbose_name="تاريخ ووقت الحصة")
    status = models.CharField(max_length=50, default="نشطة", verbose_name="حالة الحصة")

    class Meta:
        verbose_name = "الحصة"
        verbose_name_plural = "سجل الحصص"
        ordering = ['-session_date']

    def __str__(self):
        return f"{self.group.name} - {self.session_date.strftime('%Y-%m-%d %H:%M')}"


class Attendance(models.Model):
    """حضور الطالب وغيابه في الحصة"""
    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        Session, 
        on_delete=models.CASCADE, 
        related_name='attendance_records', 
        verbose_name="الحصة"
    )
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE, 
        related_name='attendance_records', 
        verbose_name="الطالب"
    )
    is_present = models.BooleanField(verbose_name="حاضر")
    notes = models.TextField(blank=True, null=True, verbose_name="ملاحظات الحضور")

    class Meta:
        verbose_name = "تسجيل الحضور"
        verbose_name_plural = "حضور وغياب الطلاب"
        unique_together = ('session', 'student')

    def __str__(self):
        status = "حاضر" if self.is_present else "غائب"
        return f"{self.student.full_name} - {self.session.group.name} ({status})"


class Exam(models.Model):
    """الامتحان"""
    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        ClassGroup, 
        on_delete=models.CASCADE, 
        related_name='exams', 
        verbose_name="المجموعة"
    )
    name = models.CharField(max_length=150, verbose_name="اسم الامتحان")
    max_score = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="الدرجة النهائية")
    exam_date = models.DateField(verbose_name="تاريخ الامتحان")

    class Meta:
        verbose_name = "الامتحان"
        verbose_name_plural = "الامتحانات"
        ordering = ['-exam_date']

    def __str__(self):
        return f"{self.name} - {self.group.name}"


class ExamResult(models.Model):
    """نتيجة امتحان الطالب"""
    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(
        Exam, 
        on_delete=models.CASCADE, 
        related_name='results', 
        verbose_name="الامتحان"
    )
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE, 
        related_name='exam_results', 
        verbose_name="الطالب"
    )
    student_score = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="درجة الطالب")

    class Meta:
        verbose_name = "نتيجة الطالب"
        verbose_name_plural = "نتائج الامتحانات"
        unique_together = ('exam', 'student')

    def __str__(self):
        return f"{self.student.full_name} - {self.exam.name}: {self.student_score}/{self.exam.max_score}"


class Payment(models.Model):
    """المدفوعات"""
    id = models.CharField(primary_key=True, max_length=100, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE, 
        related_name='payments', 
        verbose_name="الطالب"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="المبلغ المدفوع")
    payment_date = models.DateField(verbose_name="تاريخ الدفع")
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name="تفاصيل الدفع")

    class Meta:
        verbose_name = "سجل دفع"
        verbose_name_plural = "المدفوعات المالية"
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.student.full_name} paid {self.amount} on {self.payment_date}"
