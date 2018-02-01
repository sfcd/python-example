from django.contrib import admin
from .models import Contract, Timesheet


class TimesheetInline(admin.TabularInline):
    model = Timesheet
    extra = 1


class ContractInline(admin.TabularInline):
    model = Contract
    extra = 0

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('job_request', 'employee', 'date_started', 'date_finished', 'capacity_rate', 'is_active')
    raw_id_fields = ('job_request', 'employee', 'payment_source')
    inlines = [TimesheetInline]


@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    pass
