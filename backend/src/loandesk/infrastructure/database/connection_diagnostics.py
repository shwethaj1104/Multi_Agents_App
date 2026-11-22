from pymongo.errors import ConfigurationError, InvalidURI, OperationFailure


# Translate driver failures into actionable startup guidance without exposing credentials or hosts.
def describe_mongodb_failure(error: Exception, phase: str) -> str:
    message = str(error).lower()
    prefix = f"MongoDB {phase} failed. "
    if isinstance(error, InvalidURI):
        return prefix + "Check MONGODB_URI syntax and percent-encode reserved password characters."
    if isinstance(error, OperationFailure):
        if error.code == 18:
            return prefix + "Authentication was rejected. Check the database user and password."
        if error.code == 13:
            return (
                prefix
                + "The database user needs read/write and index permissions on this database."
            )
        if error.code in (85, 86):
            return prefix + "An existing index conflicts with the required index definition."
    if "certificate_verify_failed" in message:
        return prefix + "Certificate verification failed. Check your trusted CA certificates."
    if "tlsv1_alert_internal_error" in message or "ssl handshake failed" in message:
        return (
            prefix + "The TLS handshake was rejected. In Atlas > Security > Network Access, "
            "add this machine's current public IP and wait until it is Active. "
            "If it is already Active, check VPN/firewall restrictions and cluster status. "
            "TLS verification remains enabled."
        )
    if isinstance(error, ConfigurationError):
        return prefix + "Check the URI, SRV/DNS resolution and cluster availability."
    return (
        prefix
        + "Check Atlas IP access, network connectivity, cluster status and database permissions."
    )
