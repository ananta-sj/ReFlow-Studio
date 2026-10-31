"""API credential storage via the OS-native credential store.

Uses the `keyring` package (Windows Credential Manager / macOS Keychain /
Linux Secret Service). API keys are never written to settings.json or
models.json in plaintext - only a reference name is persisted there, and
that reference is looked up here to get the actual secret at call time.

If no OS keyring backend is available, this refuses to store the
credential rather than silently falling back to a plaintext file - a
missing backend is surfaced as a real error, not downgraded security.
"""

import keyring
import keyring.errors

SERVICE_NAME = "ReflowStudio"


class CredentialError(Exception):
    pass


def set_credential(ref: str, value: str) -> None:
    try:
        keyring.set_password(SERVICE_NAME, ref, value)
    except keyring.errors.NoKeyringError as e:
        raise CredentialError(
            "No OS credential store is available on this system - "
            "refusing to store the API key in plaintext instead."
        ) from e
    except Exception as exc:
        # Native keychain backends also raise platform exceptions outside the
        # keyring error hierarchy. Do not expose backend messages or secrets.
        raise CredentialError("Could not save the API key in the OS credential store. Check your account's access.") from exc


def get_credential(ref: str) -> str | None:
    try:
        return keyring.get_password(SERVICE_NAME, ref)
    except keyring.errors.NoKeyringError:
        return None
    except Exception as exc:
        raise CredentialError("Could not read the OS credential store. Check your account's access.") from exc


def delete_credential(ref: str, strict: bool = False) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, ref)
    except keyring.errors.PasswordDeleteError as exc:
        if get_credential(ref) is not None:
            raise CredentialError("Credential could not be removed from the OS store.") from exc
        # An absent credential is an idempotent success.
    except keyring.errors.NoKeyringError as exc:
        if strict:
            raise CredentialError("OS credential store unavailable; credential removal is unconfirmed.") from exc
    except Exception as exc:
        raise CredentialError("Could not remove the API key from the OS credential store. Check your account's access.") from exc
