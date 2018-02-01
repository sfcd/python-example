# coding: utf-8

from .interfaces import IViewDbDelegate


class SAViewDbDelegate(IViewDbDelegate):
    db = None
    model = None

    def __init__(self, db, model):
        self.db = db
        self.model = model

    def find_by(self, **params):
        criteria = []

        for k, v in params.iteritems():
            field = getattr(self.model, k, None)
            if field is not None:
                criteria.append(field == v)

        if criteria:
            return self.db.session.query(self.model).filter(self.db.or_(*criteria)).first()

    def save(self, user):
        self.db.session.add(user)
        self.db.session.commit()

    def get_empty(self):
        return self.model()
