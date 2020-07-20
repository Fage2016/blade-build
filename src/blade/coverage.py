# Copyright (c) 2020 Tencent Inc.
# All rights reserved.
#
# Author: chen3feng <chen3feng@gmail.com>
# Date:   Jane 03, 2020

"""
Code Test Coverage
"""

from __future__ import absolute_import
from __future__ import print_function

import collections
import os
import subprocess
import zipfile

from blade import config
from blade import console


class JacocoReporter(object):
    """
    Jacoco Coverage Report Generator
    """
    def __init__(self, build_dir, target_database, command_targets, test_jobs):
        self.__build_dir = build_dir
        self.__target_database = target_database
        self.__command_targets = command_targets
        self.__test_jobs = test_jobs
        # Collect coverage targets
        self.__coverage_targets = []
        for key in self.__command_targets:
            target = self.__target_database[key]
            if target.data.get('jacoco_coverage'):
                self.__coverage_targets.append(target)

    # Copied from BinaryRunner
    # TODO(chen3feng): DRY
    def _executable(self, target):
        """Returns the executable path. """
        return os.path.join(self.__build_dir, target.path, target.name)

    # Copied from BinaryRunner
    def _runfiles_dir(self, target):
        """Returns runfiles dir. """
        return '%s.runfiles' % self._executable(target)

    @staticmethod
    def _list_classes(path):
        """Return all *.class files in a dir"""
        result = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.class'):
                    result.append(os.path.join(root, file))
        return result

    @staticmethod
    def _list_jar_classes(jar):
        """Return all *.class files in a jar"""
        with zipfile.ZipFile(jar) as zip:
            return [f for f in zip.namelist() if f.endswith('.class')]

    @staticmethod
    def _classes_conflict(checked_classes, classes_path, classes):
        """Check whether classes in class_path already in checked_classes and then ignore this path..
        jacoco will raise exception if it meets different classes with same name when report.
        """
        for cls in classes:
            if cls in checked_classes:
                console.warning('Conflict: %s/%s already existed in %s' % (classes_path, cls, checked_classes[cls]))
                return True
            checked_classes[cls] = classes_path
        return False

    def _collect_execfiles(self):
        """Return all jacoco.exec files generated by jacoco agent after testing."""
        execfiles = []
        for key in self.__test_jobs:
            target = self.__target_database[key]

            execution_data = os.path.join(self._runfiles_dir(target), 'jacoco.exec')
            if not os.path.isfile(execution_data):
                continue
            execfiles.append(execution_data)
        return execfiles

    def _collect_classes(self):
        """Collect classes to be used as coverage base.
        Returns:
            class directory: class directory of target under test
        """
        checked_classes = {}  # dict[classfile, classes_dir]
        classes_dirs = set()
        for target in self.__coverage_targets:
            classes_dir = target._get_classes_dir()
            if not os.path.exists(classes_dir):
                classes_dir = target._get_target_file('jar')
                classes = self._list_jar_classes(classes_dir)
            else:
                classes = self._list_classes(classes_dir)
            if not self._classes_conflict(checked_classes, classes_dir, classes):
                classes_dirs.add(classes_dir)

        return classes_dirs

    def _collect_sources(self):
        """Collect sources to be used as coverage base.
        Returns:
            source directory: source directory of target under test
        """
        return [target._get_sources_dir() for target in self.__coverage_targets]

    @staticmethod
    def _cut_in_before_each(value, items):
        """Cut in `value` before each elements of items"""
        # See https://www.w3resource.com/python-exercises/list/python-data-type-list-exercise-47.php
        return [v for elt in items for v in (value, elt)]

    @staticmethod
    def _check_java_debug_options():
        from blade import java_targets  # pylint: disable=import-outside-toplevel
        options = java_targets.debug_info_options()
        for option in options:
            if 'line' in option:  # "-g:line" is required to generate line coverage
                return
        console.warning('"global_config.debug_info_level" is too low to generate java line coverage')

    @staticmethod
    def _common_dir(files):
        """Common dir of a group of files"""
        dirname = ''
        for file in files:
            d = os.path.dirname(file)
            if not dirname or len(d) < len(dirname):
                dirname = d
        return dirname

    def _package_source_mapping(self):
        # Merge all pacage sources mappings
        merged = collections.defaultdict(list)
        for target in self.__coverage_targets:
            mapping = target.get_java_package_source_mapping()
            for package, sources in mapping.items():
                merged[package] += sources
        return {package : self._common_dir(sources) for package, sources in merged.items()}

    def _postprocess_report(self, report_dir):
        """Do more works on generated report"""
        # Replace the package names to source file dirs in index.html for better blaming
        mapping = self._package_source_mapping()
        index_html = os.path.join(report_dir, 'index.html')
        with open(index_html) as f:
            content = f.read()
        for package, path in mapping.items():
            content = content.replace('>%s</a>' % package, '>%s</a>' % path)
        with open(index_html, 'w') as f:
            f.write(content)
        # Also generate a package_mapping file
        with open(report_dir + '.packages.csv', 'w') as f:
            f.write('package_name,source_path\r\n')
            for package, path in mapping.items():
                f.write('%s,%s\r\n' % (package, path))

    def generate(self):
        """Run jacococli to generate coverage report"""
        if not self.__coverage_targets:
            console.debug('No jacoco supported targets')
            return

        report_dir = os.path.join(self.__build_dir, 'jacoco_coverage_report')
        console.info('Generating java coverage report `%s`' % report_dir)

        execfiles = self._collect_execfiles()
        if not execfiles:
            console.warning('jacoco exec files not found')
            return

        jacoco_home = config.get_item('java_test_config', 'jacoco_home')
        if not jacoco_home:
            console.warning('Missing jacoco home in java_test configuration. '
                            'Abort java coverage report generation.')
            return

        self._check_java_debug_options()
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)

        java = 'java'
        java_home = config.get_item('java_config', 'java_home')
        if java_home:
            java = os.path.join(java_home, 'bin', 'java')
        jacococli = os.path.join(jacoco_home, 'lib', 'jacococli.jar')

        classes_dirs = self._collect_classes()
        source_dirs = self._collect_sources()

        # See https://www.jacoco.org/jacoco/trunk/doc/cli.html
        cmd = [java, '-jar', jacococli, 'report', '--quiet']
        cmd += execfiles
        cmd += self._cut_in_before_each('--classfiles', classes_dirs)
        cmd += self._cut_in_before_each('--sourcefiles', source_dirs)
        cmd += ['--html', report_dir]
        cmd += ['--csv', report_dir + '.csv']
        cmd += ['--xml', report_dir + '.xml']

        console.debug(' '.join(cmd))

        # NOTE: If call with(cmd:str, shell=True), may cause a 'command line too long' error
        # Pass cmd as a list and shell=False solves this problem
        if subprocess.call(cmd, shell=False) != 0:
            console.warning('Failed to generate java coverage report')
            return
        self._postprocess_report(report_dir)
