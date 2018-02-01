# coding: utf-8

from .interfaces import IAuthorizationStrategy
from ..errors import (
    AccountNotFound,
    FacebookNotFound,
    IncorrectFacebookToken,
    NoCredentialDataProvided,
    NoFacebookToken,
    WrongAuthorizationData,
)
from ..facebook_loader import FacebookSDKLoader
from ...models import passwords


class FacebookStrategy(IAuthorizationStrategy):
    name = 'facebook'
    facebook_loader = FacebookSDKLoader

    def authorize(self, error_callback=None):
        data = self.data_source.get_authorization_data()

        facebook_token = data.get('facebook_token')

        if facebook_token is None:
            error_callback(NoFacebookToken())
            return

        faccount = self.get_facebook_account(facebook_token)

        if not faccount:
            error_callback(IncorrectFacebookToken())
            return

        facebook_id = faccount['id']
        user = self.user_loader.load(facebook_id=facebook_id)

        if not user:
            error_callback(FacebookNotFound())
            return

        return user

    def get_facebook_account(self, facebook_token):
        fb_loader = self.facebook_loader()
        return fb_loader.load(facebook_token)


class SimpleStrategy(IAuthorizationStrategy):
    name = 'simple'
    password_delegate = passwords.Pbkdf2Sha512PasswordDelegate

    def authorize(self, error_callback=None):
        data = self.data_source.get_authorization_data()
        login = data.get('login')
        password = data.get('password')

        if login is None or password is None:
            error_callback(NoCredentialDataProvided())
            return

        user = self.user_loader.load(email=login)

        if user is None:
            error_callback(AccountNotFound())
            return

        user.password_delegate = self.create_password_delegate()
        if not user.compare_passwords(password):
            error_callback(WrongAuthorizationData())
            return

        return user

    def create_password_delegate(self):
        return self.password_delegate()
