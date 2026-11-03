"""Create a source-only archive from an explicit allowlist; never package local data."""
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = [
    'package.json', 'package-lock.json', 'vite.config.js', 'index.html', '.gitignore', 'LICENSE',
    'README.md', 'SECURITY.md', 'CONTRIBUTING.md', 'CHANGELOG.md', 'start_project.bat',
]

FOLDER_TYPES = {
    'src': {'.vue', '.js', '.mjs', '.css', '.svg', '.png', '.jpg', '.jpeg', '.webp'},
    'public': {'.svg', '.png', '.jpg', '.jpeg', '.webp', '.ico', '.woff', '.woff2'},
    'tests': {'.mjs', '.js'}, 'scripts': {'.py'}, 'backend/tests': {'.py'},
    'docs': {'.md', '.svg', '.png', '.webp'},
    '.github/workflow-templates': {'.yml', '.yaml'}, 'third-party': {'.txt', '.md'},
}

TEXT_TYPES = {'.vue', '.js', '.mjs', '.css', '.svg', '.py', '.md', '.txt', '.json', '.yml', '.yaml', '.html', '.example'}
EXCLUDED_SOURCE_FILES = {'src/recoveredData.js', 'src/components/HelloWorld.vue',
                         'src/assets/hero.png', 'src/assets/vite.svg', 'src/assets/vue.svg'}
CREDENTIAL_PATTERN = re.compile(r'(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{35}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})')


def validate_source_content(file):
    if file.suffix.lower() in TEXT_TYPES or file.name == 'LICENSE':
        if CREDENTIAL_PATTERN.search(file.read_text(encoding='utf-8', errors='replace')):
            raise ValueError(f'Possible embedded credential; source archive was not created: {file.name}')


def validate_source(file, root=ROOT):
    relative = file.relative_to(root)
    if relative.as_posix() in EXCLUDED_SOURCE_FILES:
        raise ValueError(f'Not a publishable source input: {relative}')
    parts = {part.lower() for part in relative.parts}
    if not file.resolve().is_relative_to(root.resolve()) or not file.is_file() or file.is_symlink():
        raise ValueError(f'Invalid source input: {relative}')
    if parts & {'credentials', 'node_modules', '.venv', '.git', 'uploads', 'backups', 'logs', '__pycache__'}:
        raise ValueError(f'Private/runtime directory: {relative}')
    if file.suffix.lower() in {'.db', '.pyc', '.sqlite', '.sqlite3', '.enc', '.key', '.pem', '.crt'} or file.name in {'.env', 'runtime.env', 'recoveredData.js'}:
        raise ValueError(f'Local data must never be packaged: {relative}')
    if relative.as_posix() in ROOT_FILES or (relative.parent.as_posix() == 'backend' and file.name in BACKEND_FILES):
        return
    for folder, extensions in FOLDER_TYPES.items():
        if relative.is_relative_to(folder) and file.suffix.lower() in extensions:
            return
    raise ValueError(f'Not an approved source type: {relative}')
BACKEND_FILES = [
    'main.py', 'agents.py', 'database.py', 'models.py', 'retrieval.py',
    'settings.py', 'security.py', 'launch.py', 'requirements.txt', 'requirements.lock', 'work_validation.py',
    'account_store.py', 'chatgpt_oauth.py', 'muse_accounts.py', 'muse_worker.mjs', 'muse_usage.mjs',
    'account_routes.py', 'account_providers.py',
    '.env.example', 'runtime.env.example',
]


def main():
    files = [ROOT / name for name in ROOT_FILES]
    files += [ROOT / 'backend' / name for name in BACKEND_FILES]
    for folder in FOLDER_TYPES:
        files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.relative_to(ROOT).as_posix() not in EXCLUDED_SOURCE_FILES)
    files = sorted(set(files))
    for file in files:
        validate_source(file)
        validate_source_content(file)
    output = ROOT / 'release' / 'ai-creation-studio-source.zip'
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, file.relative_to(ROOT).as_posix())
    print(f'Source archive: {output} ({len(files)} files)')
    print('MIT LICENSE and third-party notices included. Local credentials, data and legacy scripts are excluded; source credential check passed.')


if __name__ == '__main__':
    main()
