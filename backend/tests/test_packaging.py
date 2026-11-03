"""The release allowlist must reject accidental data inside source folders."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('package_source', Path(__file__).resolve().parents[2] / 'scripts' / 'package_source.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackagingTests(unittest.TestCase):
    def test_obvious_embedded_credentials_block_release(self):
        with tempfile.TemporaryDirectory(prefix='package-secret-') as directory:
            candidate = Path(directory) / 'example.js'
            candidate.write_text('const key = ' + repr('sk-' + 'syntheticcredential' * 2), encoding='utf-8')
            with self.assertRaises(ValueError): package.validate_source_content(candidate)
            candidate.write_text('const key = process.env.OPENAI_API_KEY', encoding='utf-8')
            package.validate_source_content(candidate)

    def test_nested_local_data_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='package-deny-') as directory:
            root = Path(directory)
            for name in ['src/leak.db', 'public/.env', 'src/credentials/token.js', 'tests/session.enc',
                         'src/accounts.key', 'tests/backup.sqlite3', 'src/recoveredData.js', 'public/runtime.env',
                         'src/local.env', 'tests/private.json', 'test_playwright.py',
                         'src/components/HelloWorld.vue', 'src/assets/hero.png', 'src/assets/vite.svg', 'src/assets/vue.svg']:
                candidate = root / name
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_text('synthetic private fixture', encoding='utf-8')
                with self.subTest(name=name), self.assertRaises(ValueError): package.validate_source(candidate, root)

    def test_source_and_configuration_examples_remain_packaged(self):
        with tempfile.TemporaryDirectory(prefix='package-allow-') as directory:
            root = Path(directory)
            for name in ['src/Example.vue', 'src/helper.js', 'backend/main.py', 'backend/.env.example',
                         'backend/runtime.env.example', 'tests/example.test.mjs', 'third-party/provider-LICENSE.txt',
                         'docs/development.md', '.github/workflow-templates/ci.yml']:
                candidate = root / name
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_text('synthetic public fixture', encoding='utf-8')
                package.validate_source(candidate, root)
