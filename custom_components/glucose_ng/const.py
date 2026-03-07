
DOMAIN = "glucose_ng"

CONF_SHARED_SECRET = "shared_secret"
CONF_NAME = "name"
CONF_LOW = "threshold_low"
CONF_HIGH = "threshold_high"
CONF_RATE_DROP = "rate_drop"

DEFAULT_NAME = "Glucosa"
DEFAULT_LOW = 70.0
DEFAULT_HIGH = 180.0
DEFAULT_RATE_DROP = 3.0  # mg/dL/min

SIGNAL_NEW_READING = "glucose_ng_new_reading"
SIGNAL_NEW_TREATMENT = "glucose_ng_new_treatment"
SIGNAL_NEW_DEVICESTATUS = "glucose_ng_new_devicestatus"
