from datetime import date, timedelta

from decimal import Decimal
from django.core import mail
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from django.test import TestCase
from unittest import mock
from factory.django import mute_signals

from billing.models import PaymentStatus
from contracts.serializers import TimesheetSerializer
from utils.test import EndpointTestCase
from billing.factories import ContractDepositFactory, TimesheetPaymentFactory
from employers.factories import EmployerFactory
from employees.factories import EmployeeFactory
from job_requests.factories import JobRequestFactory
from offers.factories import OfferFactory

from .factories import ContractFactory, TimesheetFactory
from .signals import contract_signed

from .tasks import (
    close_expired_contracts,
    fill_empty_timesheets,
    close_unpaid_contracts,
    close_contracts_without_payout,
)

from .models import (
    Contract,
    Timesheet,
)


class ContractEmployeeListEndpointTest(EndpointTestCase):
    def setUp(self):
        self.url = '/contracts/'
        self.current_subset_url = '/contracts/current/'
        self.future_subset_url = '/contracts/future/'
        self.past_subset_url = '/contracts/past/'
        self.employer = EmployerFactory()
        self.employee = EmployeeFactory()
        self.job_request = JobRequestFactory(company=self.employer.company)

        self.current_date = timezone.now().date()
        self.future_date = timezone.now().date() + timedelta(weeks=4)
        self.past_date = timezone.now().date() - timedelta(weeks=4)

        self.offer = OfferFactory(
            created_by=self.employee, contractor=self.employee, job_request=self.job_request,
            customer_accepted=True, supplier_accepted=True, contractor_accepted=True,
            date_started=timezone.now().date())

        self.client.force_authenticate(self.employee)

    def test_list_all(self):
        ContractFactory(employee=self.employee, job_request=self.job_request)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(self.job_request.company.name, response.data[0]['job_request']['company']['name'])
        self.assertSwaggerSchema(response, response.wsgi_request)

    def test_list_current(self):
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=timezone.now())
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=timezone.now())
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=self.past_date)
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=self.future_date)

        response = self.client.get(self.current_subset_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_past(self):
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=self.past_date)
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=self.past_date)
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=timezone.now())
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=self.future_date)

        response = self.client.get(self.past_subset_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_list_future(self):
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=self.future_date)
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=self.future_date)
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=self.past_date)
        ContractFactory(employee=self.employee, job_request=self.job_request, date_started=timezone.now())

        response = self.client.get(self.future_subset_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)


class ContractEmployerListEndpointTest(EndpointTestCase):
    def setUp(self):
        self.url = '/contracts/'
        self.incoming_url = '/contracts/incoming/'
        self.outgoing_url = '/contracts/outgoing/'

        self.employer = EmployerFactory()
        self.employee = EmployeeFactory()
        self.job_request = JobRequestFactory(company=self.employer.company)

        self.offer = OfferFactory(
            created_by=self.employee, contractor=self.employee, job_request=self.job_request,
            customer_accepted=True, supplier_accepted=True, contractor_accepted=True,
            date_started=timezone.now().date())

    @mock.patch('billing.tasks.pay_deposit')
    def test_create(self, pay_deposit):
        self.client.force_authenticate(self.employer)

        pay_deposit.side_effect = lambda contract_id: \
            ContractDepositFactory(contract=Contract.objects.get(id=contract_id))

        response = self.client.post(self.url, format='json', data={
            'payment_source': self.employer.company.payment_account.default_source.id,
            'offer': self.offer.id,
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=response.data)
        contract = Contract.objects.get(id=response.data['id'])

        self.offer.refresh_from_db()
        self.assertEqual(self.offer.is_active, False)
        self.assertEqual(contract.capacity_rate, self.offer.capacity_rate)
        self.assertSwaggerSchema(response, response.wsgi_request)

    @mock.patch('billing.tasks.pay_deposit')
    def test_create_with_individual_employee(self, pay_deposit):
        self.employee.company = None
        self.employee.save(update_fields=['company'])
        self.client.force_authenticate(self.employer)

        pay_deposit.side_effect = lambda contract_id: \
            ContractDepositFactory(contract=Contract.objects.get(id=contract_id))

        response = self.client.post(self.url, format='json', data={
            'payment_source': self.employer.company.payment_account.default_source.id,
            'offer': self.offer.id,
        })

        self.run_commit_hooks()
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=response.data)

    @mock.patch('billing.tasks.pay_deposit')
    def test_create_customer_unaccepted(self, pay_deposit):
        self.client.force_authenticate(self.employer)
        self.offer.customer_accepted = None
        self.offer.save()

        pay_deposit.side_effect = lambda contract_id: \
            ContractDepositFactory(contract=Contract.objects.get(id=contract_id))

        response = self.client.post(self.url, format='json', data={
            'payment_source': self.employer.company.payment_account.default_source.id,
            'offer': self.offer.id
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=response.data)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.customer_accepted, True)
        self.assertSwaggerSchema(response, response.wsgi_request)

    def test_create_offer_is_inactive(self):
        self.offer.mark_closed()
        self.client.force_authenticate(self.employer)

        response = self.client.post(self.url, format='json', data={
            'payment_source': self.employer.company.payment_account.default_source.id,
            'offer': self.offer.id,
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, msg=response.data)
        self.assertValidationError(response.data, field='offer', code='inactive')
        self.assertSwaggerSchema(response, response.wsgi_request)

    @mock.patch('billing.tasks.pay_deposit')
    def test_create_autoaccept_offer(self, pay_deposit):
        supplier_customer = EmployerFactory()
        contractor = EmployeeFactory(company=supplier_customer.company)
        self.client.force_authenticate(supplier_customer)

        offer = OfferFactory(contractor=contractor, created_by=contractor,
            job_request__company=supplier_customer.company, contractor_accepted=True)

        pay_deposit.side_effect = lambda contract_id: \
            ContractDepositFactory(contract=Contract.objects.get(id=contract_id))

        response = self.client.post(self.url, format='json', data={
            'payment_source': supplier_customer.company.payment_account.default_source.id,
            'offer': offer.id,
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=response.data)

        offer.refresh_from_db()
        self.assertTrue(offer.supplier_accepted)
        self.assertTrue(offer.contractor_accepted)

    def test_create_internal_without_payment_source(self):
        supplier_customer = EmployerFactory()
        contractor = EmployeeFactory(company=supplier_customer.company)
        self.client.force_authenticate(supplier_customer)

        offer = OfferFactory(contractor=contractor, created_by=contractor,
            job_request__company=supplier_customer.company, contractor_accepted=True)

        response = self.client.post(self.url, format='json', data={
            'offer': offer.id,
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=response.data)

    @mock.patch('billing.tasks.pay_deposit')
    def test_create_closing_overlapping_offers(self, pay_deposit):
        customer = EmployerFactory()
        contractor = EmployeeFactory()
        today = timezone.now().date()

        pay_deposit.side_effect = lambda contract_id: \
            ContractDepositFactory(contract=Contract.objects.get(id=contract_id))

        offer = OfferFactory(
            contractor=contractor,
            created_by=contractor,
            date_started=today,
            weeks=4, hours_per_week=20,
            job_request__company=customer.company,
        )
        offer.accept_contractor()
        offer.accept_customer()
        offer.accept_supplier()

        overlapping_offers = [
            OfferFactory(
                contractor=contractor,
                created_by=contractor,
                date_started=(today - timedelta(weeks=2)),
                weeks=4,
                hours_per_week=40,
                contractor_accepted=True,
            ),
            OfferFactory(
                contractor=contractor,
                created_by=contractor,
                date_started=(today + timedelta(weeks=2)),
                weeks=4,
                hours_per_week=40,
                contractor_accepted=True,
            ),
        ]

        not_overlapping_offers = [
            OfferFactory(
                contractor=contractor,
                created_by=contractor,
                date_started=(today - timedelta(weeks=2, days=1)),
                weeks=2,
                hours_per_week=40,
                contractor_accepted=True,
            ),
            OfferFactory(
                contractor=contractor,
                created_by=contractor,
                date_started=(today + timedelta(weeks=4)),
                weeks=4,
                hours_per_week=40,
                contractor_accepted=True,
            ),
            OfferFactory(
                contractor=contractor,
                created_by=contractor,
                date_started=(today - timedelta(weeks=2)),
                weeks=4,
                hours_per_week=20,
                contractor_accepted=True,
            ),
        ]

        self.client.force_authenticate(customer)

        response = self.client.post(self.url, format='json', data={
            'payment_source': customer.company.payment_account.default_source.id,
            'offer': offer.id,
        })

        self.assertEqual(
            response.status_code, status.HTTP_200_OK, msg=response.data)

        for offer in overlapping_offers:
            offer.refresh_from_db()
            self.assertFalse(offer.is_active)

        for offer in not_overlapping_offers:
            offer.refresh_from_db()
            self.assertTrue(offer.is_active)

        self.assertEqual(len(mail.outbox), 2)

    def test_list_incoming(self):
        ContractFactory(job_request=self.job_request)
        ContractFactory(job_request=self.job_request)

        employee = EmployeeFactory(company=self.employer.company)
        ContractFactory(employee=employee)

        self.client.force_authenticate(self.employer)
        response = self.client.get(self.incoming_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertSwaggerSchema(response, response.wsgi_request)

    def test_list_outgoing(self):
        ContractFactory(job_request=self.job_request)
        ContractFactory(job_request=self.job_request)

        employee = EmployeeFactory(company=self.employer.company)
        ContractFactory(employee=employee)

        self.client.force_authenticate(self.employer)
        response = self.client.get(self.outgoing_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertSwaggerSchema(response, response.wsgi_request)

    def test_list_filter_by_date(self):
        ContractFactory(job_request=self.job_request, date_started=date(2030, 1, 10))
        ContractFactory(job_request=self.job_request, date_started=date(2030, 1, 20))

        self.client.force_authenticate(self.employer)
        response = self.client.get(self.url, {'date_started__lte': '2030-01-15'})
        self.assertEqual(len(response.data), 1)

        self.client.force_authenticate(self.employer)
        response = self.client.get(self.url, {'date_started__lte': '2030-01-20'})
        self.assertEqual(len(response.data), 2)

        self.client.force_authenticate(self.employer)
        response = self.client.get(self.url, {'date_started__gte': '2030-01-15'})
        self.assertEqual(len(response.data), 1)


class ContractCloseEndpointTest(EndpointTestCase):
    def setUp(self):
        self.url = '/contracts/{contract_id}/close/'

        self.employer = EmployerFactory()
        self.employee = EmployeeFactory()
        job_request = JobRequestFactory(company=self.employer.company)

        self.contract = ContractFactory(
            job_request=job_request,
            employee=self.employee,
            date_started=timezone.now().date(),
            date_finished=timezone.now().date() + timedelta(weeks=4),
        )

        patcher = mock.patch('billing.tasks.refund_deposit')
        self.addCleanup(patcher.stop)

        self.refund_contract_deposit = patcher.start()

    def test_close_by_employer(self):
        self.client.force_authenticate(self.employer)

        response = self.client.post(self.url.format(contract_id=self.contract.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=response.data)

        self.contract.refresh_from_db()
        self.refund_contract_deposit.delay.assert_called()
        self.assertEqual(self.contract.is_active, False)
        self.assertSwaggerSchema(response, response.wsgi_request)

    def test_close_by_contractor(self):
        self.client.force_authenticate(self.employee)

        response = self.client.post(self.url.format(contract_id=self.contract.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=response.data)

        self.contract.refresh_from_db()
        self.assertEqual(self.contract.is_active, False)
        self.assertSwaggerSchema(response, response.wsgi_request)

    def test_deny_close(self):
        third_party_employer = EmployerFactory()
        self.client.force_authenticate(third_party_employer)
        response = self.client.post(self.url.format(contract_id=self.contract.id),
                                    format='json', data={})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, msg=response.data)
        self.assertSwaggerSchema(response, response.wsgi_request)

    def test_close_with_message(self):
        self.client.force_authenticate(self.employer)
        response = self.client.post(self.url.format(contract_id=self.contract.id),
                                    format='json', data={'message': '¯\_(ツ)_/¯'})

        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=response.data)

        self.contract.refresh_from_db()
        self.assertEqual(self.contract.is_active, False)
        self.assertEqual(self.contract.closing_message, '¯\_(ツ)_/¯')
        self.assertSwaggerSchema(response, response.wsgi_request)


class TimesheetEndpointTest(EndpointTestCase):
    def setUp(self):
        self.timesheet_url = '/contracts/{contract_id}/timesheet/'
        self.schedule_url = '/contracts/{contract_id}/schedule/'

        self.employer = EmployerFactory()
        self.employee = EmployeeFactory()
        self.job_request = JobRequestFactory(company=self.employer.company)

        self.offer = OfferFactory(created_by=self.employee,
            contractor=self.employee, job_request=self.job_request,
            customer_accepted=True, supplier_accepted=True, contractor_accepted=True,
            date_started=timezone.now().date())

        self.contract = ContractFactory(employee=self.employee,
            job_request=self.job_request, date_started=timezone.now().date())

        self.future_contract = ContractFactory(employee=self.employee,
            job_request=self.job_request, date_started=timezone.now().date() + timedelta(weeks=2),
            date_finished=timezone.now().date() + timedelta(weeks=4))

    def test_create(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(self.timesheet_url.format(contract_id=self.contract.id),
            format='json', data={'hours_count': 40})

        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=response.data)
        timesheet = Timesheet.objects.get(id=response.data['id'])

        self.contract.refresh_from_db()
        self.assertEqual(self.contract.timesheet.first(), timesheet)
        self.assertSwaggerSchema(response, response.wsgi_request)

    def test_create_internal_contract(self):
        employee = EmployeeFactory()

        contract = ContractFactory(
            employee=employee,
            job_request__company=employee.company,
        )

        self.client.force_authenticate(employee)
        url = self.timesheet_url.format(contract_id=contract.id)
        response = self.client.post(url, format='json', data={'hours_count': 40})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertValidationError(response.data, code='internal_contract')
        self.assertSwaggerSchema(response, response.wsgi_request)

    def test_week_out_of_range(self):
        self.client.force_authenticate(self.employee)
        response = self.client.post(self.timesheet_url.format(
            contract_id=self.future_contract.id),
            format='json', data={'hours_count': 40})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, msg=response.data)
        self.assertSwaggerSchema(response, response.wsgi_request)

    def test_schedule(self):
        self.client.force_authenticate(self.employee)
        response = self.client.get(self.schedule_url.format(contract_id=self.contract.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=response.data)
        days_count = (self.contract.date_finished - self.contract.date_started).days
        self.assertEqual(days_count, len(response.json()) * 7)

        self.assertSwaggerSchema(response, response.wsgi_request)


class ScheduleEndpointTest(EndpointTestCase):
    def setUp(self):
        self.url = '/contracts/{}/schedule/'

    def test(self):
        employee = EmployeeFactory()

        contract = ContractFactory(
            date_started=date(2030, 1, 1),
            date_finished=date(2030, 1, 14),
            employee=employee,
        )

        self.client.force_authenticate(employee)
        response = self.client.get(self.url.format(contract.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data, [
            {'date_started': '2030-01-01', 'date_finished': '2030-01-07'},
            {'date_started': '2030-01-08', 'date_finished': '2030-01-14'}
        ])


class TasksTest(TestCase):
    def test_close_expired_contract(self):
        today = timezone.now().date()

        contract_1 = ContractFactory(
            date_started=today - timedelta(weeks=2),
            date_finished=today,
        )
        contract_2 = ContractFactory(
            date_started=today - timedelta(weeks=2),
            date_finished=today - timedelta(days=1),
        )

        close_expired_contracts()
        contract_1.refresh_from_db()
        self.assertFalse(contract_1.is_active)
        contract_2.refresh_from_db()
        self.assertFalse(contract_2.is_active)

    def test_close_unpaid_contracts(self):
        today = timezone.now()

        failed_deposit = ContractDepositFactory(status=PaymentStatus.FAILED)
        failed_deposit.date_created = today - timedelta(weeks=2)
        failed_deposit.save()

        failed_payment = TimesheetPaymentFactory(status=PaymentStatus.FAILED)
        failed_payment.date_created = today - timedelta(weeks=1)
        failed_payment.save()

        failed_payment_but_has_a_chance = TimesheetPaymentFactory(status=PaymentStatus.FAILED)
        failed_payment_but_has_a_chance.date_created = today - timedelta(days=5)
        failed_payment_but_has_a_chance.save()

        close_unpaid_contracts()

        failed_deposit.contract.refresh_from_db()
        self.assertFalse(failed_deposit.contract.is_active)

        failed_payment.timesheet.contract.refresh_from_db()
        self.assertFalse(failed_payment.timesheet.contract.is_active)

        failed_payment_but_has_a_chance.timesheet.contract.refresh_from_db()
        self.assertTrue(failed_payment_but_has_a_chance.timesheet.contract.is_active)

    def test_close_contracts_without_payout(self):
        today = timezone.now()
        week_and_one_day_ago = today - timedelta(days=8)

        contract_without_employee_payout = ContractFactory(
            employee__payout_account=None,
            date_created=week_and_one_day_ago,
        )
        contract_without_company_payout = ContractFactory(
            employee__company__payout_account=None,
            date_created=week_and_one_day_ago,
        )
        normal_contract = ContractFactory(
            date_created=week_and_one_day_ago,
        )

        close_contracts_without_payout()

        contract_without_employee_payout.refresh_from_db()
        self.assertFalse(contract_without_employee_payout.is_active)
        contract_without_company_payout.refresh_from_db()
        self.assertFalse(contract_without_company_payout.is_active)
        normal_contract.refresh_from_db()
        self.assertTrue(normal_contract.is_active)

    def test_fill_empty_timesheets(self):
        today = timezone.now().date()

        contract = ContractFactory(
            date_started=today - timedelta(weeks=2),
            hours_per_week=30,
        )
        contract.timesheet.create(
            hours_count=20,
            date_started=contract.date_started,
            date_finished=contract.date_started + timedelta(days=6),
        )

        fill_empty_timesheets()
        timesheet = contract.timesheet.last()
        self.assertEqual(contract.timesheet.count(), 2)
        self.assertEqual(timesheet.hours_count, 30)
        self.assertEqual(timesheet.date_started, contract.date_started + timedelta(weeks=1))
        self.assertEqual(timesheet.date_finished, contract.date_started + timedelta(weeks=1, days=6))


class TimesheetSerializerTest(TestCase):
    def test_amounts(self):
        timesheet = TimesheetFactory(
            contract__capacity_rate=Decimal('10.00'),
            hours_count=10,
        )
        serializer = TimesheetSerializer(timesheet)
        self.assertDictEqual(serializer.data['amounts'], {
            'customer': Decimal('100.00'),
            'supplier': Decimal('70.00'),
            'contractor': Decimal('10.00'),
        })
