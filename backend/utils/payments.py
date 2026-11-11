# backend/utils/payments.py
# Created by Anthony Jackson - Iteration 4 (11/11/26)
#
# THE PAYMENT DECISION FOR PIRATE COVE (so the code, README and specs all say the same thing):
#
#   1. Pirate Cove is an IN-PERSON EXCHANGE marketplace. Checkout records the order and the
#      on-campus meeting spot; the buyer pays the seller in person at the meetup.
#      This is the default and needs no keys at all.
#
#   2. Stripe is OPTIONAL and TEST MODE ONLY. If STRIPE_SECRET_KEY is set to a Stripe *test*
#      key (sk_test_... or rk_test_...), the Stripe card checkout can be shown for the demo.
#      No real money moves. Test card: 4242 4242 4242 4242, any future date, any CVC.
#
#   3. LIVE KEYS ARE REFUSED. If someone puts a live key (sk_live_ / rk_live_) in .env,
#      Stripe is switched off and a warning is printed. This keeps a class project from ever
#      charging a real card.
#
# Any code that talks to Stripe should call stripe_api_key() first and fall back to the
# in-person flow when it returns None.

import os

IN_PERSON = "IN_PERSON"
STRIPE_TEST = "STRIPE_TEST"

_TEST_PREFIXES = ("sk_test_", "rk_test_")
_LIVE_PREFIXES = ("sk_live_", "rk_live_")


def _key():
    return (os.getenv("STRIPE_SECRET_KEY") or "").strip()


def stripe_mode():
    """'test' when a Stripe test key is set, 'live_refused' for a live key, otherwise 'off'."""
    key = _key()
    if not key:
        return "off"
    if key.startswith(_LIVE_PREFIXES):
        return "live_refused"
    if key.startswith(_TEST_PREFIXES):
        return "test"
    return "off"


def stripe_enabled():
    return stripe_mode() == "test"


def stripe_api_key():
    """The Stripe key to use, or None if Stripe should not be used."""
    mode = stripe_mode()
    if mode == "live_refused":
        print("[payments] WARNING: a LIVE Stripe key is set. Pirate Cove only allows test keys. "
              "Stripe is OFF; checkout uses in-person payment.")
        return None
    return _key() if mode == "test" else None


def default_payment_method():
    """What a new order is recorded as when the buyer doesn't pay by card."""
    return IN_PERSON


def payment_summary():
    """Short text the README / checkout page can show."""
    if stripe_enabled():
        return "Pay in person at the meetup, or use the Stripe TEST card checkout (no real money)."
    return "Pay the seller in person at the meetup. No card payment is taken online."
