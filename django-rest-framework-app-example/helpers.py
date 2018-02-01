def is_user_customer(user, contract):
    return user.id in contract.job_request.company.employers.values_list('id', flat=True)


def is_user_supplier(user, contract):
    return user.id in contract.employee.company.employers.values_list('id', flat=True)
