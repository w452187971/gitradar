import datetime as dt
import unittest
from unittest.mock import patch

import collect


TODAY = dt.date(2026, 10, 20)


def repository(description='', topics=None, name='sample/tool'):
    return {'full_name': name, 'html_url': 'https://github.com/' + name,
            'description': description, 'topics': topics or [], 'stargazers_count': 100,
            'created_at': '2025-01-01T00:00:00Z', 'pushed_at': '2026-10-20T00:00:00Z',
            'language': None, 'fork': False, 'archived': False}


def platforms(description='', topics=None, name='sample/tool'):
    return collect.buildProject(repository(description, topics, name), {}, TODAY).get('platforms_zh')


class PlatformTests(unittest.TestCase):
    def testExactTopicsHaveStableOrderAndNoDuplicates(self):
        topics = ['ios', 'osx', 'windows', 'linux', 'macos', 'windows',
                  'android', 'android-tv', 'browser-extension', 'web-app']
        self.assertEqual(['Windows', 'macOS', 'Linux', 'Android TV', 'Android', 'iOS',
                          '网页', '浏览器扩展'], platforms(topics=topics))

    def testTopicSubstringsAndRepositoryNamesAreNotEvidence(self):
        topics = ['windows-api', 'ios-widget', 'android-tv-launcher', 'webkit', 'awesome-linux']
        self.assertEqual([], platforms(topics=topics, name='windows/ios-linux-tools'))

    def testDescriptionCanExplicitlyTargetSeveralPlatforms(self):
        self.assertEqual(['Windows', 'macOS', 'Linux'],
                         platforms('A desktop app for Windows, macOS and Linux.'))

    def testExplicitRuntimeAndSupportPhrasesAreRecognized(self):
        fixtures = [('Runs on Linux.', ['Linux']),
                    ('Supports Android and iOS.', ['Android', 'iOS']),
                    ('Available for Windows and macOS.', ['Windows', 'macOS']),
                    ('A launcher for Android TV.', ['Android TV']),
                    ('A web app.', ['网页']),
                    ('A browser extension.', ['浏览器扩展'])]
        for description, expected in fixtures:
            with self.subTest(description=description):
                self.assertEqual(expected, platforms(description))

    def testGenericCrossPlatformAndUnneededMacAreNotSupportEvidence(self):
        for description in ['A cross-platform tool.', 'No Mac required.', 'No need for Windows.']:
            with self.subTest(description=description):
                self.assertEqual([], platforms(description))

    def testBuildAndExampleInstructionsAreNotRuntimePlatformClaims(self):
        for description in ['Build from source on Windows.', 'An example for Linux.',
                            'Builds for Windows.', 'Compile the project for macOS.',
                            'A sample browser extension.']:
            with self.subTest(description=description):
                self.assertEqual([], platforms(description))

    def testBuildInstructionsDoNotHideIndependentPositiveEvidence(self):
        self.assertEqual(['Windows'],
                         platforms('A desktop app for Windows; compile from source on macOS.'))

    def testExplicitUnsupportedPlatformsAreRemovedEvenFromTopics(self):
        descriptions = ['macOS is not supported.', 'No support for macOS.',
                        'No macOS support.', 'Does not support macOS.',
                        'Not available for macOS.', 'Not for macOS.',
                        '暂不支持macOS。', 'macOS暂不支持。']
        for description in descriptions:
            with self.subTest(description=description):
                self.assertEqual(['Windows'], platforms(description, ['windows', 'macos']))

    def testNotRequiringAMacDoesNotCancelIndependentMacTopicEvidence(self):
        self.assertEqual(['macOS'], platforms('No Mac required.', ['macos']))

    def testCommonNegatedSupportAndRuntimePhrasesExcludePlatforms(self):
        fixtures = [("We don't support Windows.", []),
                    ('We do not support Windows.', ['windows']),
                    ("It doesn't support Windows.", ['windows']),
                    ('It does not run on Linux.', ['linux']),
                    ("It doesn't run on Linux.", ['linux'])]
        for description, topics in fixtures:
            with self.subTest(description=description):
                self.assertEqual([], platforms(description, topics))

    def testNotImmediatelyBeforeAPlatformListExcludesOnlyThosePlatforms(self):
        self.assertEqual(['Windows'], platforms('An app for Windows, not macOS.', ['windows', 'macos']))
        self.assertEqual(['Windows'], platforms('An app for Windows, not macOS or Linux.',
                                               ['windows', 'macos', 'linux']))
        self.assertEqual(['Windows'], platforms('Not only Windows.', ['windows']))

    def testWebExamplesSourcesAndDeploymentTargetsAreNotTheProjectsPlatform(self):
        descriptions = ['A web app example for learning.', 'A web app source code example.',
                        'A CLI that deploys web apps.', 'A CLI that deploys a web app.',
                        'A CLI for web apps.', 'A browser extension example.']
        for description in descriptions:
            with self.subTest(description=description):
                self.assertEqual([], platforms(description))

    def testFileeUsesItsExplicitPlatformTopicsWithoutInferringFromOfficeFormats(self):
        description = ('Free, open-source file converter. Convert 244+ formats offline by drag & drop — '
                       'images, PDF, Word, Excel, PowerPoint, HWP/HWPX, video, audio, e-books and archives. '
                       'No upload, no Office needed.')
        self.assertEqual(['Windows', 'macOS', 'Linux'],
                         platforms(description, ['file-converter', 'linux', 'macos', 'windows'],
                                   'KnifeLemon/Filee'))
        self.assertEqual([], platforms(description))

    def testCleanYourTvDoesNotImplyPhoneOrApplePlatformSupport(self):
        description = 'Debloat any Android or Google TV over Wi-Fi and get an Apple TV-style home.'
        self.assertEqual(['Android TV'],
                         platforms(description, ['android-tv', 'apple-tv'], 'Gathin23/cleanyourtv'))

    def testGitAiAndCraftLauncherRemainUnknownWithoutPlatformEvidence(self):
        self.assertEqual([], platforms('Git designed for AI agents.', ['ai-agents', 'git'], 'feder-cr/git-ai'))
        self.assertEqual([], platforms('The Craft App Launcher', [], 'storytold/craft-launcher'))

    def testRealDesktopSyncDescriptionSuppliesWindowsWithoutTopics(self):
        description = ('Unlimited Google Photos auto-sync on Windows with Pixel original quality '
                       'spoofing — native, portable, and zero-quota.')
        self.assertEqual(['Windows'], platforms(description, ['google-photos', 'unlimited-storage'],
                                                 'shishir0x/GoogleUnlimited'))

    def testFailedRefreshAlsoDerivesHintsFromRetainedDescriptionAndTopics(self):
        previous = repository('A desktop app for Windows.', ['macos'])
        previous.update(delta_1d=10, delta_7d=40, discovery_score=100)
        with patch.object(collect, 'api', side_effect=TimeoutError('temporary failure')), patch('time.sleep'):
            retained = collect.refreshTracked([previous], {}, None, [])
        self.assertEqual(['Windows', 'macOS'], retained[0].get('platforms_zh'))
        self.assertIsNone(retained[0]['delta_1d'])

    def testPlatformDerivationMakesNoNetworkRequests(self):
        with patch.object(collect, 'api', side_effect=AssertionError('unexpected network request')):
            self.assertEqual(['Windows'], platforms('A desktop app for Windows.'))


if __name__ == '__main__':
    unittest.main()
