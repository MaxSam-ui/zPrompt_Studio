"""Fast-forward update for Git clones; never reset local files."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True, stderr=subprocess.STDOUT).strip()

def main():
    if not (ROOT / '.git').exists():
        print('This copy came from a ZIP. Download the new ZIP into a separate folder,')
        print('or use git clone for automatic updates. No files were changed.')
        return 1
    if not shutil.which('git'):
        print('Install Git for Windows to update the source files.')
        return 1
    try:
        if Path(git('rev-parse', '--show-toplevel')).resolve() != ROOT:
            raise ValueError('This folder is not the repository root.')
        if git('status', '--porcelain'):
            raise ValueError('Local changes or untracked files exist. Save them before updating; no automatic reset will be performed.')
        branch = git('symbolic-ref', '--quiet', '--short', 'HEAD')
        remote = git('config', '--get', f'branch.{branch}.remote')
        ref = git('config', '--get', f'branch.{branch}.merge')
        if not remote or remote == '.' or not ref.startswith('refs/heads/'):
            raise ValueError('No remote tracking branch is configured. Use a clone of the GitHub repository.')
        print('Fetching updates... ', flush=True)
        git('fetch', remote)
        upstream = git('rev-parse', '--abbrev-ref', '@{upstream}')
        if int(git('rev-list', '--count', f'{upstream}..HEAD')):
            raise ValueError('Local commits are not present on the remote. Update stopped.')
        print(git('merge', '--ff-only', upstream), flush=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(ROOT/'requirements.txt')], cwd=ROOT, check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'check'], cwd=ROOT, check=True)
        print('Update completed. You can restart zPrompt Studio.')
        return 0
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(getattr(exc, 'output', None) or str(exc))
        print('Update did not complete. If source files were already updated, retry after resolving the error.')
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
