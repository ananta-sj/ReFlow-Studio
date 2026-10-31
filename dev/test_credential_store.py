"""Native credential failures are explicit and never become plaintext storage."""
import unittest
from unittest.mock import patch
import keyring.errors
from core import credential_store as store


class CredentialFailureTests(unittest.TestCase):
    def test_native_failures_are_wrapped_without_backend_details(self):
        for operation, method, args in (
            (store.set_credential, 'set_password', ('fixture', 'secret-value')),
            (store.get_credential, 'get_password', ('fixture',)),
            (store.delete_credential, 'delete_password', ('fixture',)),
        ):
            with self.subTest(method=method), patch.object(store.keyring, method, side_effect=Exception('secret-value')):
                with self.assertRaises(store.CredentialError) as error:
                    operation(*args)
                self.assertNotIn('secret-value', str(error.exception))

    def test_failed_deletion_cannot_succeed_while_credential_remains(self):
        with patch.object(store.keyring, 'delete_password', side_effect=keyring.errors.PasswordDeleteError()), \
                patch.object(store.keyring, 'get_password', return_value='still present'):
            for strict in (True, False):
                with self.subTest(strict=strict), self.assertRaises(store.CredentialError):
                    store.delete_credential('fixture', strict=strict)

    def test_denied_read_cannot_confirm_a_failed_deletion(self):
        with patch.object(store.keyring, 'delete_password', side_effect=keyring.errors.PasswordDeleteError()), \
                patch.object(store.keyring, 'get_password', side_effect=PermissionError('denied')):
            with self.assertRaises(store.CredentialError):
                store.delete_credential('fixture', strict=True)

    def test_missing_credential_deletion_is_idempotent(self):
        with patch.object(store.keyring, 'delete_password', side_effect=keyring.errors.PasswordDeleteError()), \
                patch.object(store.keyring, 'get_password', return_value=None):
            store.delete_credential('fixture', strict=True)
