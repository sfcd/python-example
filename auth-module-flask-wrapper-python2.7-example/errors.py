# coding: utf-8

from ..errors import SFKitError


class AuthError(SFKitError):
    namespace = 'auth.error'


class FacebookError(AuthError):
    namespace = 'facebook'


class StrategyNotDefined(AuthError):
    namespace = 'wrongMethod'
    description = 'This method is not implemented yet'


class EmailAlreadyExists(AuthError):
    namespace = 'emailAlreadyExists'


class FacebookAlreadyExists(FacebookError):
    namespace = 'alreadyExists'


class NoFacebookToken(FacebookError):
    namespace = 'noToken'


class IncorrectFacebookToken(FacebookError):
    namespace = 'invalidToken'


class AccountNotFound(AuthError):
    namespace = 'accountNotFound'


class FacebookNotFound(FacebookError):
    namespace = 'accountNotFound'


class NoCredentialDataProvided(AuthError):
    namespace = 'noCredentialProvided'
    description = 'No login or/and password'


class WrongAuthorizationData(AuthError):
    namespace = "wrongAuthData"
    description = 'Wrong authorization data'


class UserIsNotActive(AuthError):
    namespace = 'noActiveAccount'
    description = 'The user not active'
