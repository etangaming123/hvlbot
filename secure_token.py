"""
Portable bot-token encryption helper. Drop this file into the root of any
Discord bot with a plaintext JSON config file (config.json, env.json, etc.)
holding the bot token under a string field.

Usage:
    import secure_token
    bot.run(secure_token.secure_token())                              # config.json, field "token"
    bot.run(secure_token.secure_token(config_path="env.json"))        # different config filename
    bot.run(secure_token.secure_token(token_field="bottoken"))        # different field name

First call encrypts the plaintext token in place (migrating the config file)
and generates a key file (default: bot_token.key) alongside it - gitignore
*.key so the key never gets committed. Every call after that just decrypts.
Requires the `cryptography` package.
"""

import os
import json
from cryptography.fernet import Fernet

DEFAULT_KEY_FILE = "bot_token.key"

def _load_or_create_key(key_file: str) -> bytes:
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            return f.read().strip()
    key = Fernet.generate_key()
    with open(key_file, "wb") as f:
        f.write(key)
    try:
        os.chmod(key_file, 0o600)
    except Exception:
        pass
    print(f"Generated new encryption key at [{key_file}]. Back this file up - if lost, you'll need to re-enter your bot token.")
    return key

def _get_fernet(key_file: str) -> Fernet:
    return Fernet(_load_or_create_key(key_file))

def secure_token(config_path: str = "config.json", token_field: str = "token", key_file: str = DEFAULT_KEY_FILE) -> str:
    with open(config_path, "r") as f:
        data = json.load(f)

    stored = data[token_field]
    fernet = _get_fernet(key_file)

    try:
        return fernet.decrypt(stored.encode("utf-8")).decode("utf-8")
    except Exception:
        pass # not valid ciphertext yet, treat as plaintext and migrate below

    plaintext = stored
    data[token_field] = fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    with open(config_path, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Encrypted {token_field!r} in {config_path} at rest.")
    return plaintext
