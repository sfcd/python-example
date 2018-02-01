# coding: utf-8

from .interfaces import IRegistrationStrategy
from ..errors import (
    EmailAlreadyExists,
    FacebookAlreadyExists,
    IncorrectFacebookToken,
    NoFacebookToken,
    NoCredentialDataProvided,
)
from ..facebook_loader import FacebookSDKLoader
from ...models import passwords


class SimpleStrategy(IRegistrationStrategy):
    name = 'simple'
    password_delegate = passwords.Pbkdf2Sha512PasswordDelegate

    def register(self, user, error_callback=None):
        data = self.data_source.get_registration_data()

        login = data.get('login')
        password = data.get('password')

        if login is None or password is None:
            error_callback(NoCredentialDataProvided())
            return

        if self.unique_check_delegate.check(email=login):
            error_callback(EmailAlreadyExists())
            return

        user.password_delegate = self.create_password_delegate()
        user.email = login
        user.password = password

    def create_password_delegate(self):
        return self.password_delegate()


class FacebookStrategy(SimpleStrategy):
    name = 'facebook'
    facebook_loader = FacebookSDKLoader

    def __init__(self, *args, **kwargs):
        self.user_simple_registration = kwargs.pop('use_simple', True)
        super(FacebookStrategy, self).__init__(*args, **kwargs)

    def register(self, user, error_callback=None):
        data = self.data_source.get_registration_data()

        facebook_token = data.get('facebook_token')

        if facebook_token is None:
            error_callback(NoFacebookToken())
            return

        faccount = self.get_facebook_account(facebook_token)
        if faccount is None:
            error_callback(IncorrectFacebookToken())
            return

        facebook_id = faccount['id']

        if self.unique_check_delegate.check(facebook_id=facebook_id):
            error_callback(FacebookAlreadyExists())
            return

        if self.user_simple_registration:
            super(FacebookStrategy, self).register(user, error_callback)
        else:
            if self.unique_check_delegate.check(email=data['email']):
                error_callback(EmailAlreadyExists())
                return

        user.facebook_id = facebook_id
        user.email = data['email']

        # user.status = UserAccountStatusEnum.ACTIVED
        # return self.save(new_user, faccount=faccount)

    def get_facebook_account(self, facebook_token):
        fb_loader = self.facebook_loader()
        return fb_loader.load(facebook_token)
