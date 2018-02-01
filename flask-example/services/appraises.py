# coding: utf-8

import six

from flask import current_app as c_app

from sfkit import validation as val

from . import (
    exceptions as excs,
    Service,
)
from ..ext import db
from ..models import Appraise


create_appraise_schema = val.Schema({
    u'name': six.text_type,
    u'data': dict,
    u'comment': val.All(val.none_if_empty(), val.Any(None, six.text_type)),
    u'images': list,
})

update_appraise_schema = val.Schema({
    u'name': val.Any(None, six.text_type),
    u'data': val.Any(None, dict),
    u'comment': val.All(val.none_if_empty(), val.Any(None, six.text_type)),
    u'images': val.Any(None, list),
})


class AppraiseService(Service):
    name = u'appraises'

    def __init__(self, perm_service, file_service):
        self.perm_service = perm_service
        self.file_service = file_service

    def create(self, user, data_source):
        data = create_appraise_schema(data_source())

        new_appraise = Appraise(data[u'name'], user)
        new_appraise.data = data[u'data']
        new_appraise.comment = data[u'comment']
        new_appraise.position = user.appraisals.count()
        self._attach_images(new_appraise, data[u'images'])

        if user.is_free_appraisal_available:
            new_appraise.is_free = True
            user.is_free_appraisal_available = False

        Appraise.update_status([new_appraise])

        db.session.add(new_appraise)
        db.session.commit()
        return new_appraise

    def get(self, user, appraisal_id):
        appraisal = self._get_by_id(appraisal_id)

        if appraisal is None:
            raise excs.NotFoundError(u'appraisal')

        if not self.perm_service.can_view_appraise(user, appraisal):
            raise excs.AccessDeniedError()

        return appraisal

    def get_list(self, user):
        return self._get_list(user)

    def edit(self, user, appraise_id, data_source):
        appraise = self._get_by_id(appraise_id)

        if appraise is None:
            raise excs.NotFoundError(u'appraise')

        if not self.perm_service.can_edit_appraise(user, appraise):
            raise excs.AccessDeniedError()

        data = update_appraise_schema(data_source())

        # TODO: There is no way to set one of these values back to NULL.
        for attr in (u'name', u'data', u'comment'):
            if getattr(appraise, attr) != data[attr] and data[attr] is not None:
                setattr(appraise, attr, data[attr])

        if data[u'images'] is not None:
            self._attach_images(appraise, data[u'images'])

        Appraise.update_status([appraise])

        db.session.commit()
        return appraise

    def remove_collection(self, user):
        user.appraisals.delete()
        db.session.commit()

    def _attach_images(self, appraise, images):
        attached_image = []

        for image_id in images:
            try:
                image_file = self.file_service.get_by_id(appraise.owner, image_id)
            except excs.NotFoundError:
                raise excs.IncorrectDataError()

            if image_file.owner is None:
                image_file.owner = appraise.owner

            attached_image.append(image_file)

        if attached_image:
            appraise.images = attached_image

    def _get_by_id(self, appraise_id):
        return Appraise.query.get(appraise_id)

    def _get_list(self, user):
        return Appraise.query.filter_by(owner=user).order_by(Appraise.date_updated.desc())
