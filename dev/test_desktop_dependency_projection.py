"""Offline checks for target wheel selection and metadata-only planning."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'dev')]
import inspect_desktop_dependency_projection as proposal


class DesktopDependencyProjectionTests(unittest.TestCase):
    def file(self, name, **changes):
        result = dict(filename=name, packagetype='bdist_wheel', yanked=False,
                      requires_python='>=3.10', url='https://files.pythonhosted.org/packages/' + name,
                      digests={'sha256': 'a' * 64}, size=100)
        result.update(changes)
        return result

    def test_target_selects_windows_313_over_linux_or_310(self):
        data = dict(urls=[self.file('helper-1.0-cp310-cp310-win_amd64.whl'),
                          self.file('helper-1.0-cp313-cp313-manylinux_2_17_x86_64.whl'),
                          self.file('helper-1.0-cp313-cp313-win_amd64.whl')])
        self.assertEqual(proposal.artifact(data)['filename'], 'helper-1.0-cp313-cp313-win_amd64.whl')

    def test_yanked_and_python_incompatible_artifacts_rejected(self):
        data = dict(urls=[self.file('helper-1.0-py3-none-any.whl', yanked=True),
                          self.file('helper-1.1-py3-none-any.whl', requires_python='<3.13')])
        self.assertIsNone(proposal.artifact(data))

    def test_source_artifact_requires_explicit_planning_exception(self):
        data = dict(urls=[self.file('helper-1.0.tar.gz', packagetype='sdist')])
        self.assertIsNone(proposal.artifact(data))
        self.assertEqual(proposal.artifact(data, allow_source=True)['packagetype'], 'sdist')

    def test_target_markers_and_extras_propagate_without_claiming_installable_lock(self):
        declarations = {'root': ['child[special]>=1', 'oldhelper; python_version < "3.12"'],
                        'child': ['leaf; extra == "special"'], 'leaf': []}

        def choose(name, constraints):
            self.assertIn(name, declarations)
            info = dict(name=name, version='1.0', requires_dist=declarations[name])
            return dict(info=info), self.file(name + '-1.0-py3-none-any.whl')

        with patch.object(proposal, 'ROOTS', {'root': '1.0'}), patch.object(proposal, 'choose', side_effect=choose):
            report = proposal.project()
        self.assertEqual({row['name'] for row in report['packages']}, {'root', 'child', 'leaf'})
        self.assertEqual(next(row for row in report['packages'] if row['name'] == 'child')['requested_extras'], ['special'])
        self.assertTrue(all(edge['satisfied'] for edge in report['edges']))
        self.assertFalse(report['installable_lock'])
        self.assertFalse(report['archives_downloaded'])

    def test_direct_dependency_urls_are_rejected(self):
        def choose(name, constraints):
            return dict(info=dict(version='1.0', requires_dist=['child @ https://example.com/child.whl'])), {}
        with patch.object(proposal, 'ROOTS', {'root': '1.0'}), patch.object(proposal, 'choose', side_effect=choose):
            with self.assertRaisesRegex(ValueError, 'direct dependency URL'):
                proposal.project()


if __name__ == '__main__':
    unittest.main()
