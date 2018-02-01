import factory
from datetime import timedelta
from django.utils import timezone
from factory.django import DjangoModelFactory

from employees.factories import EmployeeFactory
from job_requests.factories import JobRequestFactory

from .models import Contract, Timesheet


class ContractFactory(DjangoModelFactory):
    employee = factory.SubFactory(EmployeeFactory)
    job_request = factory.SubFactory(JobRequestFactory)
    payment_source = factory.LazyAttribute(lambda self: self.job_request.company.payment_account.sources.first())
    capacity_rate = factory.LazyAttribute(lambda self: self.employee.capacity_rate)
    date_started = factory.LazyFunction(lambda: timezone.now().date() + timedelta(weeks=1))
    date_finished = factory.LazyAttribute(lambda self: self.date_started + timedelta(weeks=2))
    hours_per_week = 20

    class Meta:
        model = Contract


class TimesheetFactory(DjangoModelFactory):
    contract = factory.SubFactory(ContractFactory)

    @factory.lazy_attribute
    def hours_count(self):
        return self.contract.hours_per_week

    @factory.lazy_attribute
    def date_started(self):
        return self.contract.date_started

    @factory.lazy_attribute
    def date_finished(self):
        return self.contract.date_started + timedelta(weeks=6)

    class Meta:
        model = Timesheet
