"""Interactive local login for the approved evaluation; never send tokens to chat."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ['HF_HOME'] = str(ROOT / 'models/indicf5/evaluation/auth')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'


if __name__ == '__main__':
    from getpass import getpass
    from huggingface_hub import login
    print('Enter your Hugging Face read token at the hidden local prompt.')
    print('This saves it only in the evaluation authentication directory; not in Git credentials.')
    token = getpass('Hugging Face read token (hidden): ')
    login(token=token.strip(), add_to_git_credential=False)
