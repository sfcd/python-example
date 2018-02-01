from datetime import timedelta
from django.db.models import F, Q
from django.utils import timezone

from capacity.celery import celery_app
from billing.models import PaymentStatus

from .models import Contract
from .signals import contract_closed
from .enums import ClosingReason


@celery_app.task
def fill_empty_timesheets():
    today = timezone.now().date()

    contracts = Contract.objects.active().exclude(
        job_request__company=F('employee__company'),
    )

    for contract in contracts:
        schedule = contract.get_schedule()

        past_empty_weeks = (
            w for w in schedule if w.date_finished < today and not contract.timesheet.filter(
                date_started=w.date_started, date_finished=w.date_finished).exists())

        for week in past_empty_weeks:
            contract.timesheet.create(
                date_started=week.date_started,
                date_finished=week.date_finished,
                hours_count=contract.hours_per_week,
            )


@celery_app.task
def close_expired_contracts():
    contracts = Contract.objects.active().filter(
        date_finished__lte=timezone.now().date(),
    )

    for contract in contracts:
        contract.mark_closed(reason=ClosingReason.EXPIRED)
        contract_closed.send(sender=close_expired_contracts, contract=contract)


@celery_app.task
def close_unpaid_contracts():
    today = timezone.now()
    week_ago = today - timedelta(weeks=1)

    unpaid_contracts = Contract.objects.active().filter(
        Q(deposit__status=PaymentStatus.FAILED, deposit__date_created__lte=week_ago) |
        Q(timesheet__payments__status=PaymentStatus.FAILED, timesheet__payments__date_created__lte=week_ago),
    ).distinct()

    for contract in unpaid_contracts:
        contract.mark_closed(reason=ClosingReason.UNPAID)
        contract_closed.send(sender=close_expired_contracts, contract=contract)


@celery_app.task
def close_contracts_without_payout():
    today = timezone.now()
    week_ago = today - timedelta(weeks=1)

    contracts = Contract.objects.active().filter(
        Q(employee__payout_account=None) | Q(employee__company__payout_account=None),
        date_created__lte=week_ago,
    )

    for contract in contracts:
        contract.mark_closed(reason=ClosingReason.NO_PAYOUT_ACCOUNT)
        contract_closed.send(sender=close_contracts_without_payout, contract=contract)
