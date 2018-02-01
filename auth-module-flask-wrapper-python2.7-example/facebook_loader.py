# coding: utf-8

import facebook

from .interfaces import IFacebookLoader


class FacebookSDKLoader(IFacebookLoader):
    def load(self, facebook_token):
        faccount = None

        try:
            fconn = facebook.GraphAPI(facebook_token)
            faccount = fconn.get_object('me')
        except facebook.GraphAPIError:
            pass

        return faccount
