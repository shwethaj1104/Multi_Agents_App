from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

from loandesk.infrastructure.database.connection_diagnostics import describe_mongodb_failure


# Identify the Atlas/network check without repeating potentially private driver details.
def test_tls_failure_guidance_hides_driver_details():
    secret = "mongodb+srv://user:private-password@private-host/"
    result = describe_mongodb_failure(
        ServerSelectionTimeoutError(f"SSL handshake failed TLSV1_ALERT_INTERNAL_ERROR {secret}"),
        "connection",
    )
    assert "current public IP" in result
    assert "private-password" not in result
    assert "private-host" not in result
    assert "TLS verification remains enabled" in result


# Authentication and authorization failures need different fixes than a TLS/IP restriction.
def test_database_permission_guidance():
    assert "Authentication" in describe_mongodb_failure(
        OperationFailure("private", code=18), "connection"
    )
    assert "permissions" in describe_mongodb_failure(
        OperationFailure("private", code=13), "storage"
    )
    assert "DNS" in describe_mongodb_failure(ConfigurationError("private"), "connection")
