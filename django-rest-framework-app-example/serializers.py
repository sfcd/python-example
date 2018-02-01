from decimal import Decimal
from django.conf import settings
from django.db.models import DateField, Sum
from django.db.models.expressions import RawSQL, F
from django.db.models.functions import Cast
from rest_framework import serializers

from billing.models import PaymentSource, TimesheetPayment, PaymentStatus
from contracts.enums import ClosingReason
from contracts.models import (
    Contract,
    Timesheet,
)
from billing.serializers import ContractDepositSerializer, TimesheetPaymentSerializer
from employees.serializers import EmployeeSerializer
from job_requests.serializers import JobRequestSerializer
from offers.models import Offer
from offers.notifiers import OfferDeclineEmailNotifier


class TimesheetSerializer(serializers.ModelSerializer):
    default_error_messages = {
        'out_of_dates': 'Week out of range.',
        'internal_contract': 'Timesheets is not available for internal contracts.',
        'already_submitted': 'Timesheet could be submitted once during the week.',
    }

    date_started = serializers.DateField(read_only=True)
    date_finished = serializers.DateField(read_only=True)
    payments = TimesheetPaymentSerializer(many=True, read_only=True)
    amounts = serializers.SerializerMethodField()

    class Meta:
        model = Timesheet
        fields = ('id', 'hours_count', 'date_started', 'date_finished', 'payments', 'amounts')

    def get_amounts(self, obj: Timesheet):
        SUPPLIER_PAYOUT_COEFFICIENT = settings.CAPACITY_SUPPLIER_PAYOUT_COEFFICIENT
        CONTRACTOR_PAYOUT_COEFFICIENT = settings.CAPACITY_CONTRACTOR_PAYOUT_COEFFICIENT

        return {
            'customer': obj.amount,
            'supplier': round(obj.amount * SUPPLIER_PAYOUT_COEFFICIENT, 2),
            'contractor': round(obj.amount * CONTRACTOR_PAYOUT_COEFFICIENT, 2),
        }

    def save(self, contract):
        if contract.is_internal:
            self.fail('internal_contract')

        try:
            week = contract.get_current_week()
        except ValueError:
            self.fail('out_of_dates')

        hours_count = self.validated_data['hours_count']

        found_timesheet = Timesheet.objects.filter(
            date_started=week.date_started,
            date_finished=week.date_finished,
            contract=contract,
        )

        if found_timesheet.exists():
            self.fail('already_submitted')

        return Timesheet.objects.create(
            hours_count=hours_count,
            date_started=week.date_started,
            date_finished=week.date_finished,
            contract=contract,
        )


class ContractCreateSerializer(serializers.Serializer):
    offer = serializers.PrimaryKeyRelatedField(queryset=Offer.objects.all())
    payment_source = serializers.PrimaryKeyRelatedField(
        queryset=PaymentSource.objects.all(), allow_null=True, default=None)

    default_error_messages = {
        'inactive': 'Offer is inactive.',
        'not_approved': 'Offer is not approved.',
        'job_request_internal': 'Job Request is internal.',
        'job_request_inactive': 'Job Request is inactive.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['payment_source'].queryset = PaymentSource.objects.filter(
            payment_account__company=self.request_user.company,
        )

    @property
    def request_user(self):
        return self.context['request'].user

    def validate_offer(self, value):
        if not value.is_active:
            self.fail('inactive')

        if not value.contractor_accepted:
            self.fail('not_approved')

        if not value.is_user_supplier(self.request_user) \
                and not value.supplier_accepted:
            self.fail('not_approved')

        if value.job_request.is_internal \
                and value.job_request.company != value.contractor.company:
            self.fail('job_request_internal')

        if not value.job_request.is_active:
            self.fail('job_request_inactive')

        return value

    def _validate_payment_source(self, data):
        offer = data['offer']
        if data['payment_source'] is None \
                and offer.contractor.company != offer.job_request.company:
            self.fields['payment_source'].fail('required')

    def validate(self, attrs):
        self._validate_payment_source(attrs)
        return attrs

    def _close_overlapping_offers(self, contract):
        date_finished_expr = RawSQL("offers_offer.date_started + (offers_offer.weeks || ' weeks')::interval", ())

        offers = contract.employee.offers.active().annotate(
            date_finished_annotation=Cast(date_finished_expr, DateField()),
            total_hours_annotation=(F('hours_per_week') + contract.job_request.hours))

        offers = offers.filter(
            date_started__lt=contract.date_finished,
            date_finished_annotation__gte=contract.date_started,
            total_hours_annotation__gt=settings.MAX_HOURS_PER_WEEK)

        for offer in offers:
            offer.mark_closed()
            OfferDeclineEmailNotifier(offer).notify()

    def create(self, validated_data):
        offer = validated_data['offer']

        if not offer.customer_accepted:
            if offer.is_user_supplier(self.request_user) and not offer.supplier_accepted:
                offer.accept_supplier()
            offer.accept_customer()

        offer_data = {
            'employee': offer.contractor,
            'job_request': offer.job_request,
            'capacity_rate': offer.capacity_rate,
            'date_started': offer.date_started,
            'date_finished': offer.date_finished,
            'hours_per_week': offer.hours_per_week,
        }

        contract = Contract.objects.create(
            payment_source=validated_data['payment_source'],
            **offer_data,
        )

        offer.mark_closed()
        self._close_overlapping_offers(contract)

        return contract


class ContractSerializer(serializers.ModelSerializer):
    employee = EmployeeSerializer()
    job_request = JobRequestSerializer()
    timesheet = TimesheetSerializer(many=True)
    weeks = serializers.IntegerField(read_only=True)
    deposit = ContractDepositSerializer(read_only=True)
    payments_amount = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = '__all__'

    def get_payments_amount(self, obj):
        field = serializers.DecimalField(max_digits=12, decimal_places=2)
        zero = Decimal('0.00')

        payments = TimesheetPayment.objects.filter(
            timesheet__contract=obj,
            status=PaymentStatus.SUCCEEDED,
        )

        amounts = payments.aggregate(
            customer_paid=Sum('amount'),
            supplier_received=Sum('supplier_amount'),
            contractor_received=Sum('contractor_amount'),
        )

        return {
            x: field.to_representation(y or zero)
            for x, y in amounts.items()
        }


class ContractCloseSerializer(serializers.Serializer):
    message = serializers.CharField(default='')

    def close(self, user):
        self.instance.mark_closed(
            reason=ClosingReason.MANUALLY,
            message=self.validated_data['message'],
            user=user
        )


class WeekSerializer(serializers.Serializer):
    date_started = serializers.DateField()
    date_finished = serializers.DateField()
