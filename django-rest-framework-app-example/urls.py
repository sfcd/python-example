from django.conf.urls import url
from utils.views import dispatch_role

from .views import (
    ScheduleView,
    TimesheetCreateView,
    ContractCloseView,
    ContractEmployeeListView,
    ContractEmployerListCreateView,
    ContractEmployerListSubsetView,
)


urlpatterns = [
    url(r'^$', dispatch_role(
        employee=ContractEmployeeListView.as_view(),
        employer=ContractEmployerListCreateView.as_view(),
    )),

    url(r'^(?P<contract_id>\d+)/close/$', ContractCloseView.as_view()),
    url(r'^(?P<contract_id>\d+)/schedule/$', ScheduleView.as_view()),
    url(r'^(?P<contract_id>\d+)/timesheet/$', TimesheetCreateView.as_view()),

    # employer subsets
    # TODO: ask frontenders and remove
    url(r'^incoming/$', ContractEmployerListSubsetView.as_view(subset='incoming')),
    url(r'^outgoing/$', ContractEmployerListSubsetView.as_view(subset='outgoing')),

    # employee subsets
    # TODO: ask frontenders and remove
    url(r'^current/$', ContractEmployeeListView.as_view(subset='active')),
    url(r'^future/$', ContractEmployeeListView.as_view(subset='future')),
    url(r'^past/$', ContractEmployeeListView.as_view(subset='past')),
]
