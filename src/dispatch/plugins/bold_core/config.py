from dispatch.config import config, Secret

# Google

GOOGLE_DEVELOPER_KEY = config("GOOGLE_DEVELOPER_KEY", cast=Secret)
GOOGLE_SERVICE_ACCOUNT_CLIENT_EMAIL = config("GOOGLE_SERVICE_ACCOUNT_CLIENT_EMAIL")
GOOGLE_SERVICE_ACCOUNT_CLIENT_ID = config("GOOGLE_SERVICE_ACCOUNT_CLIENT_ID")
GOOGLE_SERVICE_ACCOUNT_DELEGATED_ACCOUNT = config("GOOGLE_SERVICE_ACCOUNT_DELEGATED_ACCOUNT")
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY = config("GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY", cast=Secret)
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY_ID = config("GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY_ID")
GOOGLE_SERVICE_ACCOUNT_PROJECT_ID = config("GOOGLE_SERVICE_ACCOUNT_PROJECT_ID")

GOOGLE_DOMAIN = config("GOOGLE_DOMAIN")

GOOGLE_USER_OVERRIDE = config("GOOGLE_USER_OVERRIDE", default=None)

# Coda
CODA_API_KEY = config("CODA_API_KEY", cast=Secret)
CODA_TEMPLATE_ID = config("CODA_TEMPLATE_ID")
CODA_FOLDER_ID = config("CODA_FOLDER_ID")
