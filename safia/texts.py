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
GIFT_FULL_REMAINING = "Offrir le montant restant"
BTN_PAY = "Payer"
BTN_PENDING = "En attente…"
BTN_BACK_WISHLIST = "Retour à la liste"

# Payment return / outcomes
PAYMENT_NOT_CONFIRMED = "Ce paiement n'a pas pu être confirmé."
CONFIRMING_PAYMENT = "Confirmation du paiement en cours…"
BTN_REFRESH = "Actualiser"
INVALID_RETURN_LINK = "Ce lien de retour de paiement n'est pas valide."

THANK_YOU_BODY = (
    "Merci beaucoup, {donor_name} ! "
    "Votre contribution de {amount} pour « {item_name} » nous touche énormément.\n\n"
    "Vous devriez également recevoir un e-mail de confirmation dans votre boîte de réception."
)

PAYMENT_FAILED = (
    "Le paiement n'a pas abouti. Vous pouvez réessayer quand vous le souhaitez."
)

# Validation
ERR_AMOUNT_MIN = "Indiquez un montant entier d'au moins 1 €."
ERR_AMOUNT_RANGE = "Indiquez un montant entier entre 1 € et le solde restant."
ERR_AMOUNT_INVALID = "Indiquez un montant entier en euros (chiffres uniquement)."
ERR_NAME_REQUIRED = "Veuillez indiquer votre nom."
ERR_EMAIL_INVALID = "Veuillez indiquer une adresse e-mail valide."
ERR_STRIPE_NOT_CONFIGURED = (
    "Les paiements ne sont pas configurés. Définissez STRIPE_SECRET_KEY dans l'environnement "
    "ou [stripe] dans .streamlit/secrets.toml."
)
ERR_STRIPE_CHECKOUT = "Impossible d'ouvrir le paiement Stripe : {detail}"

# App chrome
DEBUG_MODE = "Mode débogage (`SAFIA_DEBUG`)"
WARN_STRIPE_NOT_CONFIGURED = (
    "Stripe n'est pas configuré — le bouton Payer ne fonctionnera pas tant que "
    "STRIPE_SECRET_KEY n'est pas définie."
)

# Pending payment fallback link
PENDING_LINK_PREFIX = "Si le lien ne s'ouvre pas, "
PENDING_LINK_TEXT = "cliquez ici"

# Dev helpers
DEV_SIMULATE_SUCCESS = "Simuler succès"
DEV_SIMULATE_FAILURE = "Simuler échec"

# Email — donor
EMAIL_THANK_YOU_SUBJECT = "Merci pour votre cadeau"
EMAIL_THANK_YOU_BODY = (
    "Bonjour {donor_name},\n\n"
    "Merci infiniment pour votre contribution de {amount} pour « {item_name} ».\n"
    "Votre générosité compte énormément pour nous.\n\n"
    "Avec toute notre affection,\n"
    "La famille de Safia\n"
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

# Stripe (shown to users via st.error)
STRIPE_AMOUNT_MIN = "Le montant minimum est de 1 €."
