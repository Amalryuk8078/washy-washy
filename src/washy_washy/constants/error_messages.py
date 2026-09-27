"""Default human-readable messages paired with error_codes.py."""

VALIDATION_ERROR = "The request could not be validated."
UNAUTHORIZED = "Authentication is required to access this resource."
FORBIDDEN = "You do not have permission to perform this action."
NOT_FOUND = "The requested resource could not be found."
CONFLICT = "The request conflicts with the current state of the resource."
BUSINESS_RULE_ERROR = "The request violates a business rule."
INTERNAL_SERVER_ERROR = "An unexpected error occurred."

# Authentication (Phase 2)
# AUTH_INVALID_CREDENTIALS is deliberately generic: it must never reveal
# whether the email or the password was the incorrect one.
AUTH_INVALID_CREDENTIALS = "Incorrect email or password."
AUTH_TOKEN_INVALID = "The provided token is invalid."
AUTH_TOKEN_EXPIRED = "The provided token has expired."
AUTH_REFRESH_TOKEN_REQUIRED = "A refresh token is required for this operation."
AUTH_USER_INACTIVE = "This account is inactive."
AUTH_EMAIL_ALREADY_EXISTS = "An account with this email already exists."
AUTH_PHONE_ALREADY_EXISTS = "An account with this phone number already exists."

# Users / profiles / addresses / service areas (Phase 4)
CUSTOMER_PROFILE_ALREADY_EXISTS = "A customer profile already exists for this account."
PARTNER_PROFILE_ALREADY_EXISTS = "A partner profile already exists for this account."
SERVICE_AREA_NAME_ALREADY_EXISTS = "A service area with this name already exists."

# Role management
ROLE_ALREADY_ASSIGNED = "The user already has this role."
ROLE_NOT_ASSIGNED = "The user does not have this role."
CANNOT_REMOVE_OWN_ADMIN_ROLE = "You cannot remove your own ADMIN role."

# Catalog (Phase 5)
SERVICE_NAME_ALREADY_EXISTS = "A service with this name already exists."
MATERIAL_NAME_ALREADY_EXISTS = "A material with this name already exists."
SERVICE_MATERIAL_ALREADY_EXISTS = "This service/material compatibility already exists."
PARTNER_CAPABILITY_ALREADY_EXISTS = "This partner already has this capability."

# Pricing (Phase 6)
NO_ACTIVE_PRICING_RULE = "This service has no active pricing rule."
QUANTITY_REQUIRED = "A quantity is required for this service's pricing model."
WEIGHT_REQUIRED = "A weight (kg) is required for this service's pricing model."
UNKNOWN_PRICING_MODEL = "This service's pricing model is not recognized."
