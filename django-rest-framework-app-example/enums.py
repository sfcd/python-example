class ClosingReason:
    NO_PAYOUT_ACCOUNT = 'no_payout_account'
    MANUALLY = 'manually'
    EXPIRED = 'expired'
    UNPAID = 'unpaid'

    choices = [
        (MANUALLY, 'Manually'),
        (NO_PAYOUT_ACCOUNT, 'No payout account'),
        (EXPIRED, 'Expired'),
        (UNPAID, 'Unpaid'),
    ]

    messages = {
        NO_PAYOUT_ACCOUNT: "Closed automatically due one of the sides does not have an account for payouts.",
        UNPAID: "Closed automatically client has troubles with payment.",
        EXPIRED: "Closed automatically due expiration.",
        MANUALLY: "Closed manually by {email}.",
    }
