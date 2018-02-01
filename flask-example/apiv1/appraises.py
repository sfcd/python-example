# coding: utf-8

from flask import (
    abort,
    Blueprint,
    current_app as c_app,
)

from sfkit import current_user as c_user
from sfkit.auth.login import login_required
from sfkit.reqparser import RequestParser
from sfkit.errors import SFKitException
from sfkit.views import View

from ..errors import IncorrectData
from ..serializers import AppraiseSerializer
from ..services import exceptions as excs

bp = Blueprint('appraises', __name__, url_prefix='/appraises')


class ListAppraiseView(View):
    decorators = (login_required, )

    def get(self):
        """
        ===============
        GET /appraises/
        ===============
        Get a list of all appraises for the current user.

        Statuses
        ********
        200
            Returns a list of :ref:`Appraise`
        """
        appraise_service = c_app.service_locator.get_by_name(u"appraises")
        appraise_list = appraise_service.get_list(
            c_user._get_current_object(),
        )

        paginator = c_app.extensions['sfkit:paginator'].paginate(appraise_list)
        return self.build_response(paginator.items).paginate_with(
            paginator).serialize_with(AppraiseSerializer(many=True))

    def post(self):
        """
        ================
        POST /appraises/
        ================
        Create a new appraise

        .. note:: Authorization required.

        Parameters
        **********
        **name** : string
            Appraisal name. Ex.:: ``Mordor ring``.

        **data** : dict
            A json with appraise metadata.

        **images** : array
            An array of images IDs.

        *comment* : string
            A comment to the appraise. Ex.:: ``My favourite gold ring``.

        Statuses
        ********
        200
            Returns a new :ref:`Appraise`

        400
            Invalid data. Additional statuses:
                * traxnyc.errors.incorrectData - sent file not found or doesn't not belong to the current user
        """
        appraise_service = c_app.service_locator.get_by_name(u"appraises")

        try:
            new_appraise = appraise_service.create(
                c_user._get_current_object(),
                self.get_post_data,
            )
        except excs.IncorrectDataError:
            raise SFKitException(IncorrectData())

        mailer_ext = c_app.extensions[u'mailer']
        notify_service = c_app.service_locator.get_by_name(u'notifications')

        mailer_ext.send_appraise_submitted(new_appraise)
        notify_service.send_push(new_appraise, c_app.config['PUSH_SUBMITTED'])

        return self.build_response(new_appraise) \
            .serialize_with(AppraiseSerializer())

    def delete(self):
        """
        ==================
        DELETE /appraises/
        ==================
        Delete all user's appraisals

        .. note:: Authorization required.

        Statuses
        ********
        200
            Success
        """
        appraisal_service = c_app.service_locator.get_by_name(u"appraises")
        appraisal_service.remove_collection(c_user._get_current_object())
        return self.build_response(None)


    @staticmethod
    def get_post_data():
        req_parser = RequestParser()
        req_parser.add_argument(u'name')
        req_parser.add_argument(u'data', type=dict)
        req_parser.add_argument(u'images', type=list)
        req_parser.add_argument(u'comment')
        return req_parser.parse_args()


class SingleAppraiseView(View):
    decorators = (login_required, )

    def get(self, appraise_id):
        """
        ============================
        GET /appraises/:appraise_id/
        ============================
        Get a single appraise.

        Path parameters
        ***************
        **appraise_id** : int
            An appraise ID. Ex.:: ``1``.

        Statuses
        ********
        200
            Returns the :ref:`Appraise`

        404
            Appraise not found.
        """
        appraise_service = c_app.service_locator.get_by_name(u"appraises")

        try:
            appraise = appraise_service.get(c_user._get_current_object(), appraise_id)
        except excs.AccessDeniedError:
            abort(403)
        except excs.NotFoundError:
            abort(404)

        return self \
            .build_response(appraise) \
            .serialize_with(AppraiseSerializer())

    def put(self, appraise_id):
        """
        ============================
        PUT /appraises/:appraise:id/
        ============================
        Update a certain appraise.

        .. note:: Authorization required.

        Path parameters
        ***************
        **appraise_id** : int
            An appraise ID. Ex.:: ``1``.

        Parameters
        **********
        **name** : string
            Appraisal name. Ex.:: ``Mordor ring``.

        **data** : dict
            A json with appraise metadata.

        **images** : array
            An array of images IDs.

        *comment* : string
            A comment to the appraise. Ex.:: ``My favourite gold ring``.

        Statuses
        ********
        200
            Returns the updated :ref:`Appraise`

        400
            Invalid data. Additional statuses:
                * traxnyc.errors.incorrectData - sent file not found or doesn't not belong to the current user

        404
            Appraise not found.
        """
        appraise_service = c_app.service_locator.get_by_name(u"appraises")

        try:
            edited_appraise = appraise_service.edit(c_user._get_current_object(), appraise_id, self.get_put_data)
        except excs.IncorrectDataError:
            raise SFKitException(IncorrectData())
        except excs.AccessDeniedError:
            abort(400)
        except excs.NotFoundError:
            abort(404)

        return self \
            .build_response(edited_appraise) \
            .serialize_with(AppraiseSerializer())

    @staticmethod
    def get_put_data():
        req_parser = RequestParser()
        req_parser.add_argument(u'name')
        req_parser.add_argument(u'data', type=dict)
        req_parser.add_argument(u'images', type=list)
        req_parser.add_argument(u'comment')
        return req_parser.parse_args()


ListAppraiseView.register(bp, endpoint='appraises:create')
SingleAppraiseView.register(bp, endpoint='appraises:single', url='/<int:appraise_id>/')
