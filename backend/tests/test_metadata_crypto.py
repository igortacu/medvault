import base64
import os
import unittest

from app.crypto import metadata


def _b64_key(byte: int) -> str:
    return base64.b64encode(bytes([byte]) * 32).decode()


class MetadataCryptoTests(unittest.TestCase):
    def setUp(self):
        self._saved = {
            k: os.environ.get(k)
            for k in ("METADATA_ENCRYPTION_KEYS", "METADATA_ENCRYPTION_KEY_VERSION")
        }
        os.environ["METADATA_ENCRYPTION_KEYS"] = (
            '{"1": "%s", "2": "%s"}' % (_b64_key(1), _b64_key(2))
        )
        os.environ["METADATA_ENCRYPTION_KEY_VERSION"] = "2"
        metadata.reset_cache()

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        metadata.reset_cache()

    def test_round_trip_uses_write_version(self):
        blob, version = metadata.encrypt("Essential hypertension")
        self.assertEqual(version, 2)
        self.assertEqual(metadata.current_key_version(), 2)
        self.assertEqual(metadata.decrypt(blob, version), "Essential hypertension")

    def test_ciphertext_is_not_plaintext_and_is_randomised(self):
        blob_a, _ = metadata.encrypt("secret note")
        blob_b, _ = metadata.encrypt("secret note")
        self.assertNotIn(b"secret note", blob_a)
        self.assertNotEqual(blob_a, blob_b)  # random nonce per call

    def test_decrypt_with_older_key_version(self):
        blob, _ = metadata.encrypt("old value", key_version=1)
        self.assertEqual(metadata.decrypt(blob, 1), "old value")

    def test_unicode_round_trip(self):
        text = "Rezultat: Timofei Moșneaga — 37°C"
        blob, version = metadata.encrypt(text)
        self.assertEqual(metadata.decrypt(blob, version), text)

    def test_tampered_ciphertext_is_rejected(self):
        blob, version = metadata.encrypt("value")
        tampered = bytearray(blob)
        tampered[-1] ^= 0x01
        with self.assertRaises(metadata.MetadataCryptoError):
            metadata.decrypt(bytes(tampered), version)

    def test_missing_keys_env_raises(self):
        os.environ.pop("METADATA_ENCRYPTION_KEYS", None)
        os.environ.pop("METADATA_ENCRYPTION_KEY_VERSION", None)
        metadata.reset_cache()
        with self.assertRaises(metadata.MetadataCryptoError):
            metadata.encrypt("value")


if __name__ == "__main__":
    unittest.main()
