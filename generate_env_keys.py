"""
Generates Fernet encryption keys for the env vars secure_token.py looks for,
so at-rest secrets can be upgraded off the on-disk key-file fallback.

Usage:
    python generate_env_keys.py                 # print export/setx lines for the default vars
    python generate_env_keys.py --apply          # Windows: persist via `setx`. Elsewhere: same as no-flag.
    python generate_env_keys.py MY_KEY_VAR ...    # generate for custom var names instead of the defaults
"""

import os
import sys
import subprocess
from cryptography.fernet import Fernet

DEFAULT_VARS = ["BOT_TOKEN_ENCRYPTION_KEY"]


def main():
    args = sys.argv[1:]
    apply = "--apply" in args
    var_names = [a for a in args if a != "--apply"] or DEFAULT_VARS

    keys = {name: Fernet.generate_key().decode("utf-8") for name in var_names}

    if apply and os.name == "nt":
        for name, value in keys.items():
            subprocess.run(["setx", name, value], check=True)
        print("Applied the following keys to your user environment via setx (back these up now, they won't be shown again):")
        for name, value in keys.items():
            print(f'{name}="{value}"')
        return

    if os.name == "nt":
        for name, value in keys.items():
            print(f'setx {name} "{value}"')
    else:
        for name, value in keys.items():
            print(f'export {name}="{value}"')


if __name__ == "__main__":
    main()
