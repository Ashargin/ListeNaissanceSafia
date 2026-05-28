"""French UI and email copy (app is French-only)."""

from __future__ import annotations

from safia.models import format_eur


def progress_label(*, contributed: int, price: int, remaining: int) -> str:
    return (
        f"{format_eur(contributed)} sur {format_eur(price)} "
        f"— il reste {format_eur(remaining)}"
    )


# Contribution panel
FULLY_FUNDED = "Entièrement financé — merci !"
BTN_CLOSE = "Fermer"
BTN_CONTRIBUTE = "Contribuer"
LABEL_NAME = "Nom"
LABEL_EMAIL = "E-mail"
LABEL_MESSAGE = "Message"
LABEL_AMOUNT = "Montant (€)"
AMOUNT_PLACEHOLDER = ""
BTN_PAY = "Confirmer"
BTN_PENDING = "En attente…"
BTN_BACK_WISHLIST = "Retour à la liste"

THANK_YOU_BODY = (
    "Merci beaucoup, {donor_name} ! "
    "Votre générosité nous touche énormément 🥰\n\n"
    "Vous devriez bientôt recevoir un e-mail de confirmation.\n\n"
    "Pour finaliser votre contribution de {amount} pour « {item_name} », retrouvez ci-dessous les informations de paiement.\n"
    "N'oubliez pas d'indiquer votre nom dans le libellé du paiement pour qu'on puisse vous dire merci 😘"
)

PAYMENT_METHOD_PICK_LABEL = "Choisissez un moyen de paiement"
PAYMENT_METHOD_LYDIA = "Lydia"
PAYMENT_METHOD_WERO_PHONE = "Wero"
PAYMENT_METHOD_WERO_QR = "Wero (QR code)"
PAYMENT_METHOD_PAYPAL = "PayPal"
PAYMENT_METHOD_IBAN = "Virement bancaire"
PAYMENT_DETAIL_LYDIA_PHONE = "Numéro Lydia"
PAYMENT_DETAIL_WERO_PHONE = "Numéro Wero"
PAYMENT_DETAIL_WERO_QR = "QR code Wero"
PAYMENT_DETAIL_PAYPAL_URL = "Lien PayPal"
PAYMENT_DETAIL_IBAN = "IBAN"
PAYMENT_DETAIL_BIC = "BIC (optionnel)"
PAYMENT_PAYPAL_OPEN = "Lien PayPal"
WARN_PAYMENT_METHODS_NOT_CONFIGURED = (
    "Aucun moyen de paiement n'est configuré. Renseignez la section [payment] "
    "dans .streamlit/secrets.toml (voir secrets.toml.example)."
)

# Validation
ERR_AMOUNT_MIN = "Indiquez un montant entier d'au moins 1 €."
ERR_AMOUNT_RANGE = "Indiquez un montant entier entre 1 € et le solde restant."
ERR_AMOUNT_INVALID = "Indiquez un montant entier en euros."
ERR_NAME_REQUIRED = "Veuillez indiquer votre nom."
ERR_EMAIL_INVALID = "Veuillez indiquer une adresse e-mail valide."

# App chrome
DEBUG_MODE = "Mode débogage (`SAFIA_DEBUG`)"

# Dev helpers
DEV_SIMULATE_SUCCESS = "Simuler succès"
DEV_SIMULATE_FAILURE = "Simuler échec"

# Email — donor
EMAIL_THANK_YOU_SUBJECT = "Merci pour votre cadeau 🎁"
EMAIL_PAYMENT_INSTRUCTIONS_INTRO = (
    "Si vous n'avez pas encore finalisé le paiement, vous pouvez le faire via :"
)
EMAIL_PAYMENT_NAME_REMINDER = (
    "N'oubliez pas d'indiquer votre nom dans le libellé du paiement "
    "pour qu'on puisse vous dire merci 😘"
)
EMAIL_THANK_YOU_BODY = (
    "Bonjour {donor_name},\n\n"
    "Merci infiniment pour votre contribution de {amount} pour « {item_name} » 🥰\n"
    "Votre générosité compte énormément pour nous.\n\n"
    "{payment_instructions}\n\n"
    "Avec toute notre affection,\n"
    "Loïc et Meriem\n"
)
EMAIL_THANK_YOU_BODY_HTML = (
    "<p>Bonjour {donor_name},</p>"
    "<p>Merci infiniment pour votre contribution de {amount} pour "
    "«&nbsp;{item_name}&nbsp;» 🥰<br>"
    "Votre générosité compte énormément pour nous.</p>"
    "{payment_instructions}"
    "<p>Avec toute notre affection,<br>Loïc et Meriem</p>"
)

# Email — owner
EMAIL_OWNER_SUBJECT = "Nouveau cadeau : {item_name} ({amount})"
EMAIL_OWNER_BODY = (
    "Une nouvelle contribution a été reçue sur la liste de naissance.\n\n"
    "Donateur·rice : {donor_name}\n"
    "E-mail : {donor_email}\n"
    "Article : {item_name}\n"
    "Montant : {amount}\n\n"
    "Message du ou de la donateur·rice :\n"
    "{message}\n"
)
EMAIL_NO_MESSAGE = "(aucun message)"

# Payment service (debug / warnings)
WARN_THANK_YOU_EMAIL_FAILED = (
    "Paiement enregistré, mais l'e-mail de remerciement n'a pas pu être envoyé : {exc}"
)
WARN_OWNER_EMAIL_FAILED = (
    "Paiement enregistré, mais l'e-mail de notification n'a pas pu être envoyé : {exc}"
)
CAPTION_NOTIFY_EMAIL = (
    "Définissez SAFIA_NOTIFY_EMAIL (ou smtp.notify_email dans les secrets) "
    "pour recevoir les alertes."
)
