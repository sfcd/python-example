from utils.filters import NestableFilterSetMixin, NestedFilter
from django_filters import rest_framework as drf_filters
from employees.filters import EmployeeFilter

from .models import Contract


class ContractFilter(NestableFilterSetMixin, drf_filters.FilterSet):
    nested_filters = [
        NestedFilter(EmployeeFilter, name='employee', prefix='employee__'),
    ]

    class Meta:
        model = Contract

        fields = {
            'is_active': ['exact'],
            'employee': ['exact'],
            'employee__company': ['exact'],
            'job_request': ['exact'],
            'job_request__company': ['exact'],
            'date_started': ['exact', 'lt', 'lte', 'gt', 'gte'],
            'date_finished': ['exact', 'lt', 'lte', 'gt', 'gte'],
        }
