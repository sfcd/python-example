from datetime import date, timedelta
from collections import namedtuple

from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from billing.models import PaymentSource
from employees.models import Employee
from job_requests.models import JobRequest
from users.models import User
from .enums import ClosingReason

Week = namedtuple('Week', ('date_started', 'date_finished'))


class ContractManager(models.Manager):
    def active(self):
        return self.get_queryset().filter(is_active=True)


class Contract(models.Model):
    objects = ContractManager()
    employee = models.ForeignKey(Employee, related_name='contracts')
    job_request = models.ForeignKey(JobRequest, related_name='contracts')
    payment_source = models.ForeignKey(PaymentSource, blank=True, null=True,
                                       related_name='contracts', on_delete=models.PROTECT)
    date_started = models.DateField()
    date_finished = models.DateField()
    hours_per_week = models.PositiveSmallIntegerField()
    capacity_rate = models.DecimalField(max_digits=8, decimal_places=2,
                                        validators=[MinValueValidator(Decimal('0.01'))])

    closing_reason = models.CharField(max_length=100, choices=ClosingReason.choices, blank=True)
    closing_message = models.TextField(blank=True)
    closed_by = models.ForeignKey(User, null=True, blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('date_started',)

    def __str__(self):
        return 'Contract object: {}'.format(self.id)

    @property
    def weeks(self):
        """Contract duration in weeks."""
        delta = self.date_finished - self.date_started
        return int(delta.days / 7)

    @property
    def is_internal(self):
        return self.job_request.company == self.employee.company

    @property
    def participants(self):
        users = [self.employee]
        users += list(self.job_request.company.employers.all())

        if self.employee.company is not None:
            users += list(self.employee.company.employers.all())

        return users

    def clean(self):
        if self.payment_source.payment_account.company != self.job_request.company:
            raise ValidationError({'payment_source': 'Payment source do not belong to the company.'})

    def get_schedule(self):
        schedule = []
        date_started = self.date_started

        while True:
            date_finished = date_started + timedelta(days=6)  # type: date
            schedule.append(Week(date_started, date_finished))

            date_started = date_finished + timedelta(days=1)
            if date_started >= self.date_finished:
                break

        return schedule

    def get_current_week(self):
        today = timezone.now().date()
        for week in self.get_schedule():
            if week.date_started <= today <= week.date_finished:
                return week
        raise ValueError('week out of range')

    def mark_closed(self, reason, message='', user=None):
        if not self.is_active:
            return

        self.is_active = False
        self.closing_reason = reason
        self.closing_message = message
        self.closed_by = user

        self.save(update_fields=[
            'is_active',
            'closing_reason',
            'closing_message',
            'closed_by',
        ])

    def get_weekly_cost(self):
        return self.hours_per_week * self.capacity_rate


class Timesheet(models.Model):
    contract = models.ForeignKey(Contract, related_name='timesheet')
    hours_count = models.PositiveSmallIntegerField()
    date_created = models.DateTimeField(default=timezone.now)
    date_started = models.DateField()
    date_finished = models.DateField()

    class Meta:
        ordering = ('contract', 'date_started', 'hours_count')

    def __str__(self):
        return 'Timesheet object: {}'.format(self.id)

    @property
    def amount(self):
        return self.contract.capacity_rate * self.hours_count

    @property
    def is_latest(self):
        return self.contract.date_finished == self.date_finished
