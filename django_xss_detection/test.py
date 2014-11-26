#!/usr/bin/python
import os
import unittest

import lxml.html
from django.template import loader

from . import util
from . import parse_template


def _get_test_template_dir():
    """ returns the test template directory. """
    return os.path.join(os.path.dirname(
        os.path.abspath(__file__)), 'test_templates/')


def _get_expecting_vuln(doc, xpath=None):
    ret = []
    if xpath is None:
        xpath = ".//div[@type='vuln']"
    for elem in doc.findall(xpath):
        ret.append({
            'name': elem.attrib['name'],
            'line_number': elem.sourceline})
    return ret


class TestXSSDetection(unittest.TestCase):
    """ test xss detection in templates. """

    @classmethod
    def setUpClass(cls):
        util.configure_django([_get_test_template_dir()])

    def setUp(self):
        self.template_dir = _get_test_template_dir()
        self.csw = parse_template.CompileStringWrapper()
        util.patch(self.csw)

    def _test_template_tag(self, tag_file):
        """ test a template tag """
        return self._test_template(os.path.join("tags", tag_file))

    def test_autoescape_tag(self):
        return self._test_template_tag("autoescape.html")

    def test_extends_tag(self):
        extends_dir = 'extends'
        for _file in os.listdir(os.path.join(
                self.template_dir,
                'tags', extends_dir)):
            self.setUp()
            template_name = os.path.join(extends_dir, _file)
            self._test_template_tag(template_name)

    @unittest.skip("firstof tag detection has not yet been implemented")
    def test_firstof_tag(self):
        return self._test_template_tag("firstof.html")

    def test_for_tag(self):
        return self._test_template_tag("for.html")

    def test_ifchanged_tag(self):
        return self._test_template_tag("ifchanged.html")

    def test_ifequal_tag(self):
        return self._test_template_tag("ifequal.html")

    def test_if_tag(self):
        return self._test_template_tag("if.html")

    def test_include_tag(self):
        return self._test_template_tag("include/includer.1.html")

    def test_include_tag_with_context(self):
        """ where an include node includes a template with a 'context'
            parameter name a TypeError is raised.
        """
        with self.assertRaises(TypeError):
            self._test_template_tag("include/includer.1.with_context.html")

    def test_include_missing_include(self):
        return self._test_template_tag("include/missing.html")

    def test_with_tag(self):
        return self._test_template_tag("with.html")

    def test_custom_waffle_tag(self):
        return self._test_template_tag("custom/waffle.html")

    @unittest.expectedFailure
    def test_include_in_for_tag_tag(self):
        """ include tag in for loop is not handled correctly """
        return self._test_template_tag("include/includer.2.html")

    def test_attr_injection_variable_detection(self):
        return self._test_template("attribute/injection.html")

    def test_javascript_variable_detection(self):
        """ tests detection for variables in between <script> tags
            that do not have the 'escapejs' filter
        """
        return self._test_template("javascript/javascript.html")

    @unittest.expectedFailure
    def test_javascript_variable_detection_inside_verbatim_block(self):
        """ detection of variables in between script tags - where a
            verbatim block is opened before the script tag is not handled
            correctly.
        """
        return self._test_template("javascript/verbatim.html")

    def test_walk_templates(self):
        """ test walk_templates """
        results = util.walk_templates([self.template_dir])
        self.assertTrue(results)

    def test_uniquify_results(self):
        """ test uniquify_results """
        results = util.walk_templates([self.template_dir])
        fname_and_counts = [
            ('uniquify_results/lower.html', 2),
            ('uniquify_results/top.html', 1),
            ('uniquify_results/include.html', 1),
        ]
        for fname, count in fname_and_counts:
            self.assertEqual(len(results[fname]), count)

    def _test_template(self, template_path):
        """ test that the detector finds the problems
            in a given template file.
        """
        full_path = os.path.join(self.template_dir, template_path)
        doc = lxml.html.parse(full_path)
        expecting_vuln = _get_expecting_vuln(doc)
        templ = loader.get_template(template_path)
        context = parse_template.get_default_context()
        templ.render(context)
        methods = [
            parse_template.get_non_js_escaped_results_for_template,
            parse_template.get_non_quoted_attr_vars_for_template
        ]
        for method in methods:
            for result in method(templ):
                self.csw.handle_callback(result)
        self.assertEqual(len(self.csw.results), len(expecting_vuln))
        for result, expected in zip(self.csw.results, expecting_vuln):
            line_no = result.get_line_number()
            part = result.get_vulnerability_text()
            filename = result.get_filename()
            var = str(result._var_node.filter_expression.var)
            self.assertEqual(line_no, expected['line_number'])
            self.assertEqual(var, expected['name'])
            self.assertEqual(filename, full_path)
            self.assertTrue(var in part)


class TestUtil(unittest.TestCase):
    """ test util methods. """

    def test_get_non_quoted_content(self):
        method = util.get_non_quoted_content
        for content in ["a'b'cdc", 'a"b"cdc', """a'b'" "cdc"""]:
            self.assertEqual(method(content), "acdc")


if __name__ == "__main__":
    unittest.main()
