# hvlbot

Source code for the Discord bot made for Hurstville Lurkers! You can check out Hurstville Lurkers at [hvl.etangaming.xyz](https://hvl.etangaming.xyz).

You may also know this bot as "Rui Kamishiro" if you're in the server, or "CiRCLE Shama" if you were part of Hurstville Lurkers since the beginning.

> [!WARNING]
> This bot is poorly coded. Read its source code at your own risk.

> [!NOTE]
> This is a remade repository as the old repository had some information I should have kept in a .env file. Whoops!

## Features

You can find the bot's features at [hvl.etangaming.xyz/rui](https://hvl.etangaming.xyz/rui).

## Encryption keys

`token` and `openweatherapikey` in `env.json` are encrypted at rest (reversible, via [`secure_token.py`](secure_token.py)) rather than stored in plaintext.

Out of the box this needs zero setup: the first run auto-generates `bot_token.key` next to `env.json` and encrypts both fields under it. `bot_token.key` is gitignored — don't commit it, and don't lose it, or you'll need to re-enter both secrets.

If you'd rather not rely on a key file sitting next to the config, set the `BOT_TOKEN_ENCRYPTION_KEY` environment variable instead. Existing file-key-encrypted values are transparently upgraded to the env-var key the next time the bot starts — no manual migration step.

- **Windows:** double-click `setup_encryption_keys.bat`. It generates a key and persists it to your user environment via `setx`.
- **macOS/Linux:** run `python generate_env_keys.py` and paste the printed `export BOT_TOKEN_ENCRYPTION_KEY="..."` line into your shell profile (`~/.zshrc`, `~/.bashrc`, etc).

Either way, back up the printed key value — losing it means losing access to the stored bot token/API key and having to re-issue them.

## Contributing

*Why would you subject yourself to the living hell of this bot?*

Please do report bugs and other errors on the "issues" tab of this repository, clearly stating your issue and steps to reproduce if necessary.

> [!NOTE]
> We currently only read issues for usage of the bot on the Hurstville Lurkers server. No support will be given if you *somehow* run the bot yourself.

If you wish to make some changes, such as more optimised code (no way) or fixing an issue by yourself, you're more than welcome to submit a pull request, because why not.

Do note that this repository is only for reference, I will rarely accept pull requests. Issues will be read, however.