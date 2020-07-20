# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Chong peng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the CmdOptions module which parses the users'
 input and provides hint for users.

"""

from __future__ import absolute_import

import argparse

from blade import console
from blade.blade_platform import BuildArchitecture
from blade.blade_platform import BuildPlatform

# The 'version.py' is generated by the dist script, then it only exists in blade.zip
try:
    from blade.version import VERSION
except ImportError:
    VERSION = '(developing, unversioned)'


class ParsedCommandLine(object):
    """Parsed Command Line

    Parses user's input and provides hint.
    blade {command} [options] targets

    """

    def __init__(self, argv):
        """Init the class. """
        self.options, others = self._cmd_parse(argv)

        # If '--' in arguments, use all other arguments after it as run
        # arguments
        if '--' in others:
            pos = others.index('--')
            self.targets = others[:pos]
            self.options.args = others[pos + 1:]
        else:
            self.targets = others
            self.options.args = []

        for t in self.targets:
            if t.startswith('-'):
                console.error_exit('Unrecognized option %s, use blade [action] '
                                   '--help to get all the options' % t)

        command = self.options.command

        # Check the options with different sub command
        actions = {
            'build': self._check_build_command,
            'clean': self._check_clean_command,
            'dump': self._check_dump_command,
            'query': self._check_query_command,
            'run': self._check_run_command,
            'test': self._check_test_command,
        }
        actions[command]()

    def _check_run_targets(self):
        """check that run command should have only one target. """
        if not self.targets or ':' not in self.targets[0]:
            console.error_exit('Please specify a single target to run: '
                               'blade run //target_path:target_name (or '
                               'a_path:target_name)')
        if len(self.targets) > 1:
            console.warning('Run command will only take one target to build and run')

    def _check_test_options(self):
        """check that test command options."""

    def _check_plat_and_profile_options(self):
        """check platform and profile options. """
        compiler_arch = self._compiler_target_arch()
        arch = BuildArchitecture.get_canonical_architecture(compiler_arch)
        if arch is None:
            console.error_exit('Unknown architecture: %s' % compiler_arch)

        m = self.options.m
        if not m:
            self.options.arch = arch
            self.options.bits = BuildArchitecture.get_architecture_bits(arch)
            assert self.options.bits
        else:
            self.options.bits = m
            self.options.arch = BuildArchitecture.get_model_architecture(arch, m)
            if self.options.arch is None:
                console.error_exit('"-m%s" is not supported by the architecture %s'
                                   % (m, compiler_arch))

    def _check_clean_options(self):
        """check the clean options. """
        self._check_plat_and_profile_options()

    def _check_query_options(self):
        """check query action options. """
        if not self.options.deps and not self.options.dependents:
            console.error_exit('Please specify --deps, --dependents or both to '
                               'query target')

    def _check_build_options(self):
        """check the building options. """
        self._check_plat_and_profile_options()

    def _check_build_command(self):
        """check build options. """
        self._check_build_options()

    def _check_dump_command(self):
        """check build options. """
        self._check_build_options()

    def _check_run_command(self):
        """check run options and the run targets. """
        self._check_build_options()
        self._check_run_targets()

    def _check_test_command(self):
        """check test optios. """
        self._check_build_options()
        self._check_test_options()

    def _check_clean_command(self):
        """check clean options. """
        self._check_clean_options()

    def _check_query_command(self):
        """check query options. """
        self._check_plat_and_profile_options()
        self._check_query_options()

    def __add_plat_profile_arguments(self, parser):
        """Add plat and profile arguments. """
        parser.add_argument('-m',
                            dest='m',
                            choices=['32', '64'],
                            default='',
                            help=('Generate code for a 32-bit(-m32) or '
                                  '64-bit(-m64) environment, '
                                  'default is autodetect'))

        parser.add_argument('-p',
                            '--profile',
                            dest='profile',
                            choices=['debug', 'release'],
                            default='release',
                            help=('Build profile, default is release'))

        parser.add_argument('--debug-info-level',
                            dest='debug_info_level',
                            choices=['no', 'low', 'mid', 'high'],
                            help='Produces how much debug information')

        # DEPRECATED, see above
        parser.add_argument('--no-debug-info',
                            dest='debug_info_level',
                            action='store_const',
                            const='no',
                            help=argparse.SUPPRESS)

    def __add_generate_arguments(self, parser):
        """Add generate related arguments. """
        parser.add_argument(
            '--generate-dynamic', dest='generate_dynamic',
            action='store_true', default=False,
            help='Generate dynamic libraries')

        parser.add_argument(
            '--generate-package', dest='generate_package',
            action='store_true', default=False,
            help='Generate packages for package target')

        parser.add_argument(
            '--generate-java', dest='generate_java',
            action='store_true', default=False,
            help='Generate java files for proto_library, thrift_library and '
                 'swig_library')

        parser.add_argument(
            '--generate-php', dest='generate_php',
            action='store_true', default=False,
            help='Generate php files for proto_library and swig_library')

        parser.add_argument(
            '--generate-python', dest='generate_python',
            action='store_true', default=False,
            help='Generate python files for proto_library and thrift_library')

        parser.add_argument(
            '--generate-go', dest='generate_go',
            action='store_true', default=False,
            help='Generate go files for proto_library')

    def __add_build_actions_arguments(self, parser):
        """Add build related action arguments. """
        parser.add_argument(
            '--backend-builder', dest='backend_builder', choices=['ninja'],
            help='Specify the underlying backend builder (currently only support ninja)')

        # Add extra backend builder options arguments.
        parser.add_argument(
            '--backend-builder-options', dest='backend_builder_options', metavar='OPTIONS',
            help='Specifies extra backend builder options, for debug purpose')

        parser.add_argument(
            '-j', '--jobs', dest='build_jobs', type=int,
            help=('Specifies the number of build jobs (commands) to run simultaneously'))

        parser.add_argument(
            '-k', '--keep-going', dest='keep_going',
            action='store_true', default=False,
            help='Continue as much as possible after an error')

        parser.add_argument(
            '--no-test', dest='no_test', action='store_true',
            default=False, help='Do not build the test targets')

        parser.add_argument(
            '-n', '--dry-run', dest='dry_run', action='store_true', default=False,
            help='Dry run (don\'t run commands but act like they succeeded)')

        parser.add_argument(
            '--show-builds-slower-than', dest='show_builds_slower_than', metavar='SECONDS', type=float,
            help='Show build commands which are slower than specified seconds')

    def __add_coverage_arguments(self, parser):
        """Add coverage arguments. """
        parser.add_argument(
            '--gprof', dest='gprof',
            action='store_true', default=False,
            help='Add build options to support GNU gprof')

        parser.add_argument(
            '--coverage', dest='coverage',
            action='store_true', default=False,
            help='Add build options to support coverage test')

        # DEPRECATED, please use --coverage
        parser.add_argument(
            '--gcov', dest='coverage',
            action='store_true', default=False,
            help=argparse.SUPPRESS)

    def _add_query_arguments(self, parser):
        """Add query arguments for parser. """
        self.__add_plat_profile_arguments(parser)
        parser.add_argument(
            '--deps', dest='deps',
            action='store_true', default=False,
            help='Show all targets that depended by the target being queried')
        parser.add_argument(
            '--dependents', dest='dependents',
            action='store_true', default=False,
            help='Show all targets that depends on the target being queried')
        parser.add_argument(
            '--output-file', dest='output_file', type=str,
            help='The name of file to output query results, default to stdout')
        parser.add_argument(
            '--output-format', dest='output_format', type=str,
            choices=('plain', 'tree', 'dot'), default='plain',
            help='Specify the format of query results')
        parser.add_argument(
            '--depended', dest='dependents', action='store_true',
            help='DEPRECATED, please use --dependents')

    def _add_clean_arguments(self, parser):
        """Add clean arguments for parser. """
        self.__add_plat_profile_arguments(parser)
        self.__add_build_actions_arguments(parser)
        self.__add_generate_arguments(parser)

    def _add_test_arguments(self, parser):
        """Add test command arguments. """
        parser.add_argument(
            '--full-test', action='store_true',
            dest='full_test', default=False,
            help='Enable full test, default is incremental test')

        parser.add_argument(
            '-t', '--test-jobs', dest='test_jobs', type=int,
            help=('Specifies the number of tests to run simultaneously'))

        parser.add_argument(
            '--show-details', action='store_true',
            dest='show_details', default=False,
            help='Shows the test result in detail and provides a file')

        parser.add_argument(
            '--show-tests-slower-than', type=float, metavar='SECONDS',
            dest='show_tests_slower_than',
            help='Show tests which are slower than specified seconds')

        parser.add_argument(
            '--no-build', action='store_true',
            dest='no_build', default=False,
            help='Run tests directly without build')

        parser.add_argument(
            '--exclude-tests', dest='exclude_tests', default='', metavar='TARGET_LIST',
            help='Exclude tests which matches this comma seperated target pattern list')

        parser.add_argument(
            '--run-unrepaired-tests', dest='run_unrepaired_tests', action='store_true',
            help='Whether run unrepaired(no changw after previous failure) tests during incremental test')

    def _add_run_arguments(self, parser):
        """Add run command arguments. """

    def _add_build_arguments(self, *parsers):
        """Add building arguments for parsers. """
        for parser in parsers:
            self.__add_plat_profile_arguments(parser)
            self.__add_build_actions_arguments(parser)
            self.__add_generate_arguments(parser)
            self.__add_coverage_arguments(parser)

    def _add_common_arguments(self, *parsers):
        for parser in parsers:
            parser.add_argument(
                '--profiling', dest='profiling', action='store_true',
                help='Blade performance profiling, for blade developing')
            parser.add_argument(
                '--stop-after', dest='stop_after', type=str,
                choices=['load', 'analyze', 'generate', 'build', 'all'], default='all',
                help='Stop after specified phase')
            parser.add_argument(
                '--color', dest='color', choices=['yes', 'no', 'auto'], default='auto',
                help='Output color mode selection')
            parser.add_argument(
                '--load-local-config', dest='load_local_config',
                default=True, action='store_true',
                help='Load BLADE_ROOT.local')
            parser.add_argument(
                '--no-load-local-config', dest='load_local_config',
                action='store_false',
                help='Do not load BLADE_ROOT.local')
            parser.add_argument(
                '--verbose', dest='verbosity', action='store_const', const='verbose',
                default='normal', help='Show all details')
            parser.add_argument(
                '--quiet', dest='verbosity', action='store_const', const='quiet',
                help='Only show warnings and errors')

    def _add_dump_arguments(self, parser):
        """Add query arguments for parser. """
        parser.add_argument(
            '--to-file', dest='dump_to_file', action='store', metavar='FILEPATH',
            default='/dev/stdout',
            help='Specifies the path of file to write the dump result')
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--compdb', dest='dump_compdb', default=False, action='store_true',
            help='Dump compilation database')
        group.add_argument(
            '--config', dest='dump_config', default=False, action='store_true',
            help='Dump blade configuration')
        group.add_argument(
            '--targets', dest='dump_targets', default=False, action='store_true',
            help='Dump attributes of targets in json format')

    def _cmd_parse(self, argv):
        """Add command options, add options whthin this method."""
        blade_cmd_help = 'blade <subcommand> [options...] [targets...]'
        arg_parser = argparse.ArgumentParser(prog='blade', description=blade_cmd_help)
        arg_parser.add_argument('--version', action='version', version='%(prog)s ' + VERSION)
        sub_parser = arg_parser.add_subparsers(
            dest='command',
            help='Available subcommands')

        sub_parser.required = True

        build_parser = sub_parser.add_parser(
            'build',
            help='Build specified targets')

        run_parser = sub_parser.add_parser(
            'run',
            help='Build and runs a single target',
            epilog='Any arguments after the empty "--" will be passed to the program')

        test_parser = sub_parser.add_parser(
            'test',
            help='Build the specified targets and runs tests',
            epilog='Any arguments after the empty "--" will be passed to the program')

        clean_parser = sub_parser.add_parser(
            'clean',
            help='Remove all blade-created output')

        query_parser = sub_parser.add_parser(
            'query',
            help='Execute a dependency graph query')

        dump_parser = sub_parser.add_parser(
            'dump',
            help='Dump specified internal information')

        self._add_common_arguments(build_parser, run_parser, test_parser,
                                   clean_parser, query_parser, dump_parser)
        self._add_build_arguments(build_parser, run_parser, test_parser, dump_parser)
        self._add_run_arguments(run_parser)
        self._add_test_arguments(test_parser)
        self._add_clean_arguments(clean_parser)
        self._add_query_arguments(query_parser)
        self._add_dump_arguments(dump_parser)

        return arg_parser.parse_known_args(argv)

    def _compiler_target_arch(self):
        """Compiler(gcc) target architecture. """
        arch = BuildPlatform._get_cc_target_arch()
        pos = arch.find('-')
        if pos == -1:
            console.error_exit('Unknown target architecture %s from gcc.'
                               % arch)
        return arch[:pos]

    def get_command(self):
        """Return blade command. """
        return self.options.command

    def get_options(self):
        """Returns the command options, which should be used by blade manager."""
        return self.options

    def get_targets(self):
        """Returns the targets from command line."""
        return self.targets


def parse(argv):
    """Parse argv into command, options and targets"""
    cmdline = ParsedCommandLine(argv)
    return cmdline.get_command(), cmdline.get_options(), cmdline.get_targets()
