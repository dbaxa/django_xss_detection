import django
import os
import warnings

from django.conf import settings
from django.template import loader
from django.utils.encoding import smart_text

from . import parse_template


def configure_django(template_dirs):
    """ this configures django by calling settings.configure.
        note: settings.configure can only be called once!
    """
    TEMPLATE_LOADERS = (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
        'django_xss_detection.loaders.nop.Loader',
    )
    settings.configure(DEBUG=False, TEMPLATE_DEBUG=True,
                       TEMPLATE_DIRS=template_dirs,
                       TEMPLATE_LOADERS=TEMPLATE_LOADERS)
    if hasattr(django, 'setup'):
        django.setup()


def patch(csw):
    django.template.base.compile_string = csw.compile_string
    django.template.defaulttags.IfChangedNode = parse_template.\
        IfChangedNodeOverload
    django.template.defaulttags.IfNode = parse_template.IfNodeOverload
    django.template.defaulttags.IfEqualNode = parse_template.\
        IfEqualNodeOverload
    django.template.base.add_to_builtins(
        'django_xss_detection.templatetags.waffle')


def get_template_wrapped(template_name):
    """ returns the result of calling loader.get_template(template_name)
        if the template can be loaded.
        otherwise returns None.
    """
    try:
        return loader.get_template(template_name)
    except (django.template.base.TemplateSyntaxError, UnicodeDecodeError) as e:
        msg = "skipping %s %s" % (template_name, repr(e))
        warnings.warn(msg)
    return None


def is_vuln_in_parent(result, template_name):
    """ returns True if the vulnerability is found within the parent of
        the given UnEscapedVariableFinding.
    """
    f_name = result.get_filename()
    if f_name and not f_name.endswith(template_name):
        """ ^ found in parent. """
        return True
    return False


def is_vuln_already_in_include(result, input_results):
    """ returns true if the given result is already present in the
        'included' file.
    """
    if not hasattr(result, 'source_node'):
        return False
    if not (result.source_node and result._var_node.source):
        return False
    lookup_name = result._var_node.source[0].loadname
    if lookup_name not in input_results:
        return False
    result_v_info = parse_template._get_var_node_source_info(result._var_node)
    for _res in input_results[lookup_name]:
        _rv_info = parse_template._get_var_node_source_info(
            _res._var_node)
        if _rv_info == result_v_info:
            return True
    return False


def uniquify_results(input_results):
    """ transforms a set of results per a file into a set of
        unique results - holding for different files.

        This includes:
        removing results that are found in the parent
        of a given template,

        removing results that are found in a template
        through being included but already exist in the
        included template.
    """
    ret = {}
    for template_name, results in input_results.items():
        new_results = []
        for result in results:
            skip = False
            if is_vuln_in_parent(result, template_name):
                skip = True
            elif is_vuln_already_in_include(result, input_results):
                skip = True
            if not skip:
                new_results.append(result)
        if new_results:
            ret[template_name] = new_results
    return ret


def walk_templates(template_dirs):
    templates = (os.path.relpath(os.path.join(root, _file), template_dir)
                 for template_dir in template_dirs
                 for root, dirs, files in os.walk(smart_text(template_dir))
                 for _file in files)
    results = {}
    for templ in templates:
        csw = parse_template.CompileStringWrapper()
        patch(csw)
        template = get_template_wrapped(templ)
        context = parse_template.get_default_context()
        if template is None:
            continue
        _source, _origin_fname = parse_template.get_template_source(templ)
        for method in [parse_template.get_non_js_escaped_results_for_template,
                       parse_template.get_non_quoted_attr_vars_for_template]:
            try:
                for result in method(template, source=_source,
                                     origin_fname=_origin_fname):
                    csw.handle_callback(result)
            except ValueError as e:
                warnings.warn("could not call %s, %s" % (
                    method.__name__, e))
        try:
            template.render(context)
        except (django.template.base.TemplateSyntaxError,
                django.template.base.TemplateDoesNotExist,
                TypeError) as e:
            msg = "skipping %s %s" % (templ, repr(e))
            warnings.warn(msg)
        if csw.results:
            results[templ] = csw.results
    return uniquify_results(results)


def get_non_quoted_content(content):
    ret = []
    quote_chrs = {"'", '"'}
    if not quote_chrs.intersection(set(content)):
        return content
    inside_quote = None
    for ch in content:
        if ch in quote_chrs:
            if inside_quote is None:
                inside_quote = ch
            elif ch == inside_quote:
                inside_quote = None
        else:
            if inside_quote is None:
                ret.append(ch)
    return ''.join(ret)
