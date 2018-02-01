from django.dispatch import Signal


contract_signed = Signal(providing_args=['contract'])
contract_closed = Signal(providing_args=['contract', 'user'])
