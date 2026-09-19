# Initial Deployment Requirements
## Prerequisites for using bulwark

An Authentik OAuth2 application for Bulwark to sign in through. Its client ID and secret go in the Komodo Secrets `MAIL_OIDC_CLIENT_ID` and `MAIL_OIDC_CLIENT_SECRET`, and a 96-character random `BULWARK_SESSION_SECRET_KEY` goes beside them.

# Create and Setup Required Folders
## Create needed folders for bulwark

Bulwark runs as the image's own UID 1001, so its directories belong to host UID `101001` rather than `101000`.
