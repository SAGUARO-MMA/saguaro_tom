ALERT_EMAIL_FROM = ''   # email address from which the alerts are sent
ALERT_SMS_FROM = ''     # phone number from which the text message alerts are sent
ALERT_SMS_TO = {}       # dictionary of user name: phone numbers to which text message alerts are sent
ALLOWED_HOST = ''       # hostname or IP address of the web server (leave blank for development)
ATLAS_API_KEY = ''      # API key for the ATLAS forced photometry server
CONTACT_EMAIL = ''      # contact email for MMT observation request notes
DEBUG = False           # set to True to display error tracebacks in browser, leave False in production
FORCE_SCRIPT_NAME = ''  # the subdomain where you will host the site (leave blank for development)
GCN_CLIENT_ID = ''      # client ID for GCN Classic over Kafka
GCN_CLIENT_SECRET = ''  # secret key for GCN Classic over Kafka
GEM_N_API_KEY = ''      # API key for Gemini Observatory North
GEM_S_API_KEY = ''      # API key for Gemini Observatory South
HOPSKOTCH_GROUP_ID = '' # make up a unique ID for your Hopskotch alert consumer
LCO_API_KEY = ''        # API key for Las Cumbres Observatory
MMT_PROGRAMS = []       # list of (API key, human-readable name) for MMT Observatory
POSTGRES_DB = ''        # name of the Postgres database
POSTGRES_HOST = ''      # hostname or IP address of the Postgres database server
POSTGRES_PASSWORD = ''  # password for the Postgres database
POSTGRES_PORT = 5432    # port number for the Postgres database
POSTGRES_USER = ''      # username for the Postgres database
SAVE_TEST_ALERTS = False # save test gravitational-wave alerts
SCIMMA_AUTH_USERNAME = '' # username for SCIMMA authentication
SCIMMA_AUTH_PASSWORD = '' # password for SCIMMA authentication
SECRET_KEY = ''         # see https://docs.djangoproject.com/en/4.1/ref/settings/#secret-key
SLACK_URLS = []         # Slack URLs for incoming webhooks
TNS_API_KEY = ''        # API key for the Transient Name Server
TWILIO_ACCOUNT_SID = '' # account ID for Twilio text message alerts
TWILIO_AUTH_TOKEN = ''  # authorization token for Twilio text message alerts
