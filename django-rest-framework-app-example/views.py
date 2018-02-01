from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from billing import tasks as billing_tasks
from utils.permissions import AnyOfPermission
from utils.pg_lock import atomic_with_xact_lock

from rest_framework.response import Response
from rest_framework import (
    views,
    filters,
    generics,
)

from employees.views import EmployeeListView
from employers.permissions import AllowEmployer
from employees.permissions import AllowEmployee
from utils.pagination import PageNumberHeaderPagination

from .models import Contract
from .filters import ContractFilter

from .signals import (
    contract_signed,
    contract_closed,
)

from .serializers import (
    ContractSerializer,
    ContractCreateSerializer,
    ContractCloseSerializer,
    TimesheetSerializer,
    WeekSerializer,
)

__all__ = [
    'ContractBaseListView',
    'ContractEmployeeListView',
    'ContractEmployerListCreateView',
    'ContractEmployerListSubsetView',
]


class ContractCreateMixin:
    def post(self, request):
        return self.create(request)

    def create(self, request):
        serializer = ContractCreateSerializer(
            data=request.data, context={'request': request})

        with atomic_with_xact_lock('create_contract', request.user):
            serializer.is_valid(raise_exception=True)
            offer = serializer.validated_data['offer']

            if not offer.is_user_customer(request.user):
                self.permission_denied(request)

            contract = serializer.save()
            transaction.on_commit(lambda: self.after_save(contract))

        return Response(ContractSerializer(contract, context={'request': request}).data)

    def after_save(self, contract):
        contract_signed.send(sender=self.__class__, contract=contract)

        if not contract.is_internal:
            billing_tasks.pay_deposit.delay(contract.id)


class ContractBaseListView(generics.ListAPIView):
    permission_classes = (AllowEmployer,)
    pagination_class = PageNumberHeaderPagination
    serializer_class = ContractSerializer
    filter_backends = (filters.DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter)
    search_fields = tuple('employee__' + f for f in EmployeeListView.search_fields)

    filter_class = ContractFilter
    ordering_fields = '__all__'

    def get_queryset(self):
        return Contract.objects.all()


class ContractEmployeeListView(ContractBaseListView):
    permission_classes = (AllowEmployee,)
    pagination_class = PageNumberHeaderPagination
    serializer_class = ContractSerializer
    subset = None

    def get_queryset(self):
        queryset = super().get_queryset().filter(employee=self.request.user)

        if self.subset:
            subset_method_name = 'get_{}_subset'.format(self.subset)
            queryset = getattr(self, subset_method_name)(queryset)

        return queryset

    def get_active_subset(self, queryset):
        today = timezone.now().date()
        return queryset.filter(date_started__lte=today, date_finished__gt=today)

    def get_past_subset(self, queryset):
        today = timezone.now().date()
        return queryset.filter(date_finished__lt=today)

    def get_future_subset(self, queryset):
        today = timezone.now().date()
        return queryset.filter(date_started__gt=today)


class ContractEmployerListCreateView(ContractCreateMixin, ContractBaseListView):
    permission_classes = (AllowEmployer,)
    pagination_class = PageNumberHeaderPagination
    serializer_class = ContractSerializer

    def get_queryset(self):
        return super().get_queryset().filter(
            Q(employee__company=self.request.user.company) |
            Q(job_request__company=self.request.user.company))


class ContractEmployerListSubsetView(ContractBaseListView):
    """
    Client firiendly shortcust for getting incoming and outgoing contracts.
    In normal way it may received with ``?job_request__company={id}``
    for incoming and ``?employee__company={id}`` for outgoing.
    """

    permission_classes = (AllowEmployer,)
    pagination_class = PageNumberHeaderPagination
    serializer_class = ContractSerializer
    subset = None

    def get_queryset(self):
        queryset = super().get_queryset()
        subset_method_name = 'get_{}_subset'.format(self.subset)
        queryset = getattr(self, subset_method_name)(queryset)
        return queryset

    def get_incoming_subset(self, queryset):
        return queryset.filter(job_request__company=self.request.user.company)

    def get_outgoing_subset(self, queryset):
        return queryset.filter(employee__company=self.request.user.company)


class ContractCloseView(views.APIView):
    permission_classes = (AnyOfPermission(AllowEmployer, AllowEmployee),)

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract, id=contract_id)

        if request.user not in contract.participants:
            self.permission_denied(request)

        serializer = ContractCloseSerializer(contract, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.close(user=request.user)

        billing_tasks.refund_deposit.delay(contract.id)
        contract_closed.send(sender=self.__class__, contract=contract, user=request.user)

        serializer = ContractSerializer(contract, context={'request': request})
        return Response(serializer.data)


class ScheduleView(views.APIView):
    permission_classes = (AnyOfPermission(AllowEmployer, AllowEmployee),)

    def get(self, request, contract_id):
        contract = get_object_or_404(Contract.objects.active(), id=contract_id)

        if request.user not in contract.participants:
            self.permission_denied(request)

        serializer = WeekSerializer(contract.get_schedule(), many=True)
        return Response(serializer.data)


class TimesheetCreateView(views.APIView):
    permission_classes = (AllowEmployee,)

    def post(self, request, contract_id):
        contract = get_object_or_404(Contract.objects.active(), id=contract_id)

        if contract.employee != request.user:
            self.permission_denied(request)

        serializer = TimesheetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        timesheet = serializer.save(contract=contract)
        return Response(TimesheetSerializer(timesheet).data)
