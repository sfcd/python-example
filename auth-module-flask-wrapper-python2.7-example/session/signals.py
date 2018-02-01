# coding: utf-8

from flask.signals import Namespace

_signals = Namespace()

on_get = _signals.signal('on-get')
on_after_create = _signals.signal('on-after-create')
on_after_update = _signals.signal('on-after-update')
on_before_save = _signals.signal('on-before-save')
on_after_save = _signals.signal('on-after-save')
