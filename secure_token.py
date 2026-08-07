"""
Portable secret-encryption helper. Drop into the root of any Discord bot
with a plaintext JSON config file (config.json, env.json, etc.) holding a
sensitive field (bot token, API key, ...).

Key resolution, checked on every call:
1. Env var (key_env_var) if set.
2. Else a dedicated on-disk key file (key_file), auto-generated on first use.

Auto-upgrade: if the stored value doesn't decrypt under the active key, and
the active key came from the env var and a leftover key_file exists on disk,
try that as a legacy key. If it decrypts, re-encrypt under the active key and
persist. Otherwise treat the stored value as raw plaintext, encrypt it under
the active key, and persist.

Usage:
    import secure_token
    bot.run(secure_token.secure_token("env.json", "token"))
    weatherkey = secure_token.secure_token("env.json", "openweatherapikey")

Requires the `cryptography` package.
"""

import os
import json
import binascii
from cryptography.fernet import Fernet, InvalidToken

DEFAULT_KEY_FILE = "bot_token.key"
DEFAULT_KEY_ENV_VAR = "HVL_BOT_TOKEN_ENCRYPTION_KEY"

DECRYPT_ERRORS = (InvalidToken, ValueError, TypeError, binascii.Error)


def _create_key_file(key_file: str) -> bytes:
    key = Fernet.generate_key()
    with open(key_file, "wb") as f:
        f.write(key)
    try:
        os.chmod(key_file, 0o600)
    except Exception:
        pass
    print(f"Generated new encryption key at [{key_file}]. Back this file up - if lost, you'll need to re-enter this secret.")
    return key


def _resolve_active_key(key_file: str, key_env_var: str):
    env_value = os.environ.get(key_env_var)
    if env_value:
        return env_value.encode("utf-8"), "env"
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            return f.read().strip(), "file"
    return _create_key_file(key_file), "file"


def secure_token(config_path: str = "config.json", token_field: str = "token",
                  key_env_var: str = DEFAULT_KEY_ENV_VAR, key_file: str = DEFAULT_KEY_FILE) -> str:
    with open(config_path, "r") as f:
        data = json.load(f)

    stored = data[token_field]
    active_key, source = _resolve_active_key(key_file, key_env_var)
    active_fernet = Fernet(active_key)

    try:
        return active_fernet.decrypt(stored.encode("utf-8")).decode("utf-8")
    except DECRYPT_ERRORS:
        pass

    if source == "env" and os.path.exists(key_file):
        try:
            with open(key_file, "rb") as f:
                legacy_key = f.read().strip()
            plaintext = Fernet(legacy_key).decrypt(stored.encode("utf-8")).decode("utf-8")
            data[token_field] = active_fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
            with open(config_path, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Upgraded {token_field!r} in {config_path} from legacy key file to {key_env_var}.")
            return plaintext
        except DECRYPT_ERRORS:
            pass

    plaintext = stored
    data[token_field] = active_fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    with open(config_path, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Encrypted {token_field!r} in {config_path} at rest.")
    return plaintext
