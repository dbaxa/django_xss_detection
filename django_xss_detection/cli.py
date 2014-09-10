from __future__ import print_function
import argparse
import collections
import json
import logging

from . import util


def setup_option():
    opt = argparse.ArgumentParser(
        description="Find potential xss bugs in a django app!")
    opt.add_argument(
        "-d", "--template-directory", dest="template_dirs",
        action="append", help="Specify a template directory. "
        "This argument can be specified multiple times.", required=True)
    opt.add_argument(
        "-j", "--json", dest="json_output",
        action="store_true", help="Print results out as JSON.")
    return opt


def main(template_dirs, json_output=False, **kwargs):
    util.configure_django(template_dirs)
    if 'logging_capture_warnings' in kwargs:
        logging.captureWarnings(kwargs.get('logging_capture_warnings'))
    f_results = util.walk_templates(template_dirs)
    if json_output:
        _output_results_in_json(f_results)
    else:
        for template_name, results in f_results.items():
            print(template_name)
            for result in results:
                print('    ', result)


def _output_results_in_json(f_results):
    """ Prints out results in JSON in the following format:
        {'filename' : [{'result ...}, 'filename_two' : [...] }
    """
    out = collections.defaultdict(list)
    for filename, results in f_results.items():
        for result in results:
            result_dict = {
                'line_number': result.get_line_number(),
                'finding_reason': result._get_reason(),
                'vulnerability_text': result.get_vulnerability_text(),
            }
            out[result.get_filename()].append(result_dict)
    print(json.dumps(out))


def from_cli():
    opt = setup_option()
    args = opt.parse_args()
    main(args.template_dirs, args.json_output, logging_capture_warnings=False)


if __name__ == "__main__":
    from_cli()
