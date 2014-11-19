import copy

import django
import lxml.etree
import lxml.html
from django.template.base import Context
from django.template import debug
from django.utils import six


def node_has_a_filter(node, filter_func_name):
    """ returns True if the node has the given filter_func_name
        , e.g. 'safe',  otherwise returns False.
    """
    if not hasattr(node, 'filter_expression'):
        return False

    for _filter in node.filter_expression.filters:
        if _filter and _filter[0].__name__ == filter_func_name:
            return True
    return False


class InceptionDictionary(dict):
    """ subclass dict to return a dictionary that always
        has the key requested. The purpose of this is to ensure that
        django template variable and their attribute look ups always
        can always be 'resolved'.
    """

    def __str__(self):
        if '__self__' in self:
            return self['__self__']
        return super(InceptionDictionary, self).__str__()

    def __missing__(self, key):
        """ if the key cannot be found then return a new instance
            of this class.
        """
        return self.__class__()

    def __iter__(self):
        return six.moves.zip(self.items())

    def __reversed__(self):
        return self.__iter__()


def _get_var_node_source_info(var_node):
    """ returns the line number, part and filename
        for a given variable node.
    """
    source = var_node.source[0]
    string_range = var_node.source[1]
    filename = getattr(source, 'name', None)
    line_no = None
    part = None
    if hasattr(source, 'loader'):
        origin = source.loader(source.loadname)[0]
        line_no = 1 + origin[: string_range[0]].count("\n")
        part = origin[string_range[0]: string_range[1]]
    return line_no, part, filename


class IfChangedNodeOverload(django.template.defaulttags.IfChangedNode):
    """ this is used to replace the default
        IfChangedNode class - to render all condition nodelists.
    """

    def render(self, context):
        return (self.nodelist_true.render(context) + '\n' +
                self.nodelist_false.render(context))


class IfNodeOverload(django.template.defaulttags.IfNode):
    """ this is used to replace the default
        IfNode class - to render all condition nodelists
    """

    def render(self, context):
        ret = []
        for condition, nodelist in self.conditions_nodelists:
            ret.append(nodelist.render(context))
        return '\n'.join(ret)


class IfEqualNodeOverload(django.template.defaulttags.IfEqualNode):
    """ this is used to replace the default
        IfEqualNode class - to render all condition nodelists
    """

    def render(self, context):
        return (self.nodelist_true.render(context) + '\n' +
                self.nodelist_false.render(context))


class VariableNodeAlertingOnUnescapeUse(debug.DebugVariableNode):
    def __init__(self, filter_expression, callback_func=None):
        super(VariableNodeAlertingOnUnescapeUse, self).__init__(
            filter_expression)
        self.__callback_func = callback_func

    def render(self, context):
        msg = None
        escaped = False
        if node_has_a_filter(self, 'force_escape'):
            escaped = True
        if not context.autoescape:
            if node_has_a_filter(self, 'escape_filter') and (
                    not node_has_a_filter(self, 'safe')):
                escaped = True
            msg = "In a context where autoescaping has been disabled."
        elif node_has_a_filter(self, 'safe'):
            msg = "Has the 'safe' template filter and will not be escaped."
        if not escaped and msg and self.__callback_func:
            source_node = getattr(context, 'source_node', None)
            result = UnEscapedVariableFinding(
                self, msg=msg, source_node=source_node)
            self.__callback_func(result)
        try:
            return super(VariableNodeAlertingOnUnescapeUse, self).render(
                context)
        except TypeError:
            return 'An error occured in rendering : %s %s' % (
                repr(self),
                'due to the workarounds for custom template filters')


class DebugNodeListOverLoad(debug.DebugNodeList):
    """ this is used to overload the DebugNodeList class so that
        extra context information can be provided to find the 'source node'
        of an un-escaped variable.
        e.g. the context of 'BaseIncludeNode' instances have a
        'source_node' attribute
    """

    def render_node(self, node, context):
        source_node_name = 'source_node'
        _include_node_name = 'IncludeNode'
        _prev_include_node_name = 'BaseIncludeNode'
        if hasattr(django.template.loader_tags,
                   _prev_include_node_name):
            _include_node_name = _prev_include_node_name
        if isinstance(node, getattr(django.template.loader_tags,
                                    _include_node_name)):
            new_context = copy.copy(context)
            if not hasattr(new_context, source_node_name):
                setattr(new_context, source_node_name, node)
            context = new_context
        return super(DebugNodeListOverLoad, self).render_node(
            node, context)


class ParserThatIdentifiesUnescapedVariable(debug.DebugParser):
    def _set_var_callback_func(self, var_callback_func):
        self.var_callback_func = var_callback_func

    def create_nodelist(self):
        return DebugNodeListOverLoad()

    def create_variable_node(self, filter_expression):
        var_callback_func = getattr(self, 'var_callback_func', None)
        return VariableNodeAlertingOnUnescapeUse(
            filter_expression, var_callback_func)

    def find_filter(self, filter_name):
        if filter_name not in self.filters:
            return lambda s, *args: filter_name
        return super(ParserThatIdentifiesUnescapedVariable, self).find_filter(
            filter_name)

    def compile_filter(self, token):
        try:
            return FilterExpressionExtraVarResolution(token, self)
        except django.template.base.TemplateSyntaxError:
            return FilterExpressionIgnoresArgCheck(token, self)


def _add_missing_to_context(var, context):
    """ adds the variable and its lookup part to the context.
        returns the altered context.
    """
    current = context
    if var.lookups is None:
        return context
    for bit in var.lookups:
        if bit in current and isinstance(current, InceptionDictionary):
            current = current[bit]
        else:
            value = "<var var='%s' hash='%s' findme: %s />" % (
                var, hash(var),
                "injectedattributevalue='%s'" % var)
            current[bit] = InceptionDictionary({'__self__': value})
            current = current[bit]
    return context


class FilterExpressionExtraVarResolution(
        django.template.base.FilterExpression):
    def resolve(self, context, ignore_failures=False):
        """ because django's FilterExpression swallows VariableDoesNotExist
            exceptions and we want to ensure that missing variables have some
            content.
        """
        if not isinstance(self.var, django.template.base.Variable):
            context = self._fill_in_missing_variable_filter_args(
                context)
            return super(FilterExpressionExtraVarResolution, self).resolve(
                context, ignore_failures)
        else:
            try:
                obj = self.var.resolve(context)
            except django.template.base.VariableDoesNotExist:
                pass
            """ fix up the context """
            _add_missing_to_context(self.var, context)
            context = self._fill_in_missing_variable_filter_args(context)
            return super(FilterExpressionExtraVarResolution, self).resolve(
                context, ignore_failures)

    def _fill_in_missing_variable_filter_args(self, context):
        """ returns context filled in with missing variable
            that were provided as an arg.
        """
        for func, args in self.filters:
            for lookup, arg in args:
                if lookup:
                    try:
                        arg.resolve(context)
                    except django.template.base.VariableDoesNotExist:
                        _add_missing_to_context(arg, context)
        return context


class FilterExpressionIgnoresArgCheck(FilterExpressionExtraVarResolution):
    def args_check(name, func, provided):
        """ always return true """
        return True

    args_check = staticmethod(args_check)


def compile_string(template_string, origin, callback=None):
    """ Compiles template_string into NodeList ready for rendering
        using the custom Parser.
    """
    lexer = debug.DebugLexer(template_string, origin)
    filtered_tokens = []
    default_tags = set(debug.DebugParser([]).tags.keys())
    to_add = set()
    for tag in default_tags:
        to_add.add('end' + tag)
    default_tags = default_tags.union(to_add)
    default_tags = default_tags.union({"else", "elif"})
    for token in lexer.tokenize():
        skip = False
        if token.token_type == 2:  # TOKEN_BLOCK
            splitted = token.contents.split()
            if splitted:
                command = splitted[0]
                if command in {"load", "url"}:
                    skip = True
                if command not in default_tags:
                    skip = True
        if not skip:
            filtered_tokens.append(token)

    parser = ParserThatIdentifiesUnescapedVariable(filtered_tokens)
    parser._set_var_callback_func(callback)
    return parser.parse()


class UnEscapedFinding(object):
    """ this is the base class for representing an un-escaped finding """

    def __init__(self, **kwargs):
        pass

    def get_line_number(self):
        raise NotImplementedError("not implemented!")

    def get_vulnerability_text(self):
        raise NotImplementedError("not implemented!")

    def get_filename(self):
        raise NotImplementedError("not implemented!")

    def __str__(self):
        return "%s %s %s" % (self.get_line_number(),
                             self.get_vulnerability_text(),
                             self.get_filename())

    def _get_reason(self):
        """ returns a reason behind the finding
            e.g. a variable has been marked safe.
        """
        raise NotImplementedError("not implemented!")

    def __unicode__(self):
        return six.text_type(self.__str__())


class UnEscapedVariableFinding(UnEscapedFinding):
    """ this class represents an un-escaped variable finding. """

    def __init__(self, var_node, **kwargs):
        super(UnEscapedVariableFinding, self).__init__(**kwargs)
        self._var_node = var_node
        self.source_node = kwargs.get('source_node', None)
        self.msg = kwargs.get('msg', '')

    def _get_var_node_source_info(self):
        part = self.get_vulnerability_text()
        var_node = self._var_node
        if self.source_node:
            var_node = self.source_node
        temp_v_info = _get_var_node_source_info(var_node)
        line_number = temp_v_info[0]
        filename = temp_v_info[2]
        return line_number, part, filename

    def get_line_number(self):
        return self._get_var_node_source_info()[0]

    def get_vulnerability_text(self):
        """ returns the vulnerability text for this finding. """
        return _get_var_node_source_info(self._var_node)[1]

    def get_filename(self):
        return self._get_var_node_source_info()[2]

    def _get_reason(self):
        return self.msg

    def __str__(self):
        super_str = super(UnEscapedVariableFinding, self).__str__()
        s_node_info = None
        if self.source_node:
            s_node_info = _get_var_node_source_info(self.source_node)[:-1]
        return "%s %s (source_node %s) \n\t\t%s" % (self._var_node,
                                                    self.msg, s_node_info,
                                                    super_str)


class BaseVariableContextFinding(UnEscapedFinding):
    """ this class is an extension of UnEscapedFinding for context variable
        finding results.
    """

    def __init__(self, var_node, **kwargs):
        super(BaseVariableContextFinding, self).__init__(**kwargs)
        self._var_node = var_node
        self._line_number = kwargs.get('line_number')
        self._filename = six.text_type(kwargs.get('filename'))
        self._vulnerability_text = six.text_type(
            kwargs.get('vulnerability_text'))

    def get_line_number(self):
        return self._line_number

    def get_vulnerability_text(self):
        return self._vulnerability_text

    def get_filename(self):
        return self._filename

    def __str__(self):
        super_str = super(BaseVariableContextFinding, self).__str__()
        return "%s %s \n\t\t%s" % (self._var_node, self._get_reason(),
                                   super_str)


class UnEscapedVarJavascriptContextFinding(BaseVariableContextFinding):
    """ this class represents an un-escaped variable finding
        in a javascript context.
    """

    def _get_reason(self):
        return "In a javascript context without the escapejs filter."


class UnQuotedVarElementAttributeContext(BaseVariableContextFinding):
    """ this class represents a variable finding
        in a html element attribute context which is not quoted.
    """

    def _get_reason(self):
        return "In a html element attribute context without being quoted."


class CompileStringWrapper(object):
    """ a class that wraps calling compile_string so as to provide a
        'callback' func
    """

    def __init__(self, callback_func=None, store_results=True):
        self.store_results = store_results
        self.callback_func = callback_func
        self.results = []

    def compile_string(self, template_string, origin):
        return compile_string(template_string, origin, self.handle_callback)

    def handle_callback(self, result, **kwargs):
        if self.store_results:
            self.add_result(result)
        if self.callback_func is not None:
            self.callback_func(result, **kwargs)

    def add_result(self, result):
        self.results.append(result)


def get_default_context():
    return Context({'csrf_token': 'csrf_token'})


def get_template_source(template_name):
    """ returns the source and 'origin' for a template name. """
    for loader in django.template.loader.template_source_loaders:
        try:
            source, origin = loader.load_template_source(
                template_name)
            if source:
                return source, origin
        except django.template.base.TemplateDoesNotExist:
            pass
    return None, None


def __get_template_source_info_from_kwargs(template, **kwargs):
    source = kwargs.get('source', None)
    origin_fname = kwargs.get('origin_fname', None)
    if source is None or origin_fname is None:
        source, origin_fname = get_template_source(template.name)
    return source, origin_fname


def get_non_js_escaped_results_for_template(template, **kwargs):
    """ returns a generator of UnEscapedJavascriptContextFinding results for
        a given template
    """
    source, origin_fname = __get_template_source_info_from_kwargs(
        template, **kwargs)
    if not source or source is None:
        raise ValueError("source is empty")
    try:
        doc = lxml.html.fromstring(source)
    except lxml.etree.ParserError:
        raise ValueError("could not parse source")
    for block in doc.xpath(".//script"):
        text = block.text_content()
        origin = django.template.base.StringOrigin(text)
        for node in compile_string(text, origin).get_nodes_by_type(
                debug.DebugVariableNode):
            if node_has_a_filter(node, 'escapejs_filter'):
                continue
            string_range = node.source[1]
            line_no = (block.sourceline +
                       text[: string_range[0]].count("\n"))
            part = text[string_range[0]: string_range[1]]
            result = UnEscapedVarJavascriptContextFinding(
                var_node=node, line_number=line_no,
                filename=origin_fname, vulnerability_text=part)
            yield result


def get_non_quoted_attr_vars_for_template(template, **kwargs):
    """ returns a generator of UnQuotedVarElementAttributeContext results
        for a given template.
    """
    from . import util

    source, origin_fname = __get_template_source_info_from_kwargs(
        template, **kwargs)
    if not source or source is None:
        raise ValueError("source is empty")
    orig = source
    for line_no, content in enumerate(orig.split("\n"), 1):
        while True:
            _end = -1
            _start = content.find("<")
            if _start != -1:
                _end = content.find(">")
            if _start == -1 or _end == -1:
                break
            if content[_end] != ">":
                raise ValueError("Invalid end tag index %s %s" % (
                    content[_end], _end))
            current = content[_start: _end]
            content = content[_end + 1:]
            non_q_text = util.get_non_quoted_content(current)
            origin = django.template.base.StringOrigin(non_q_text)
            if django.template.base.VARIABLE_TAG_START not in non_q_text:
                continue
            try:
                nodelist = compile_string(non_q_text, origin)
            except django.template.base.TemplateSyntaxError:
                nodelist = None
            if not nodelist:
                continue
            for node in nodelist.get_nodes_by_type(
                    debug.DebugVariableNode):
                part = non_q_text[node.source[1][0]:node.source[1][1]]
                res = UnQuotedVarElementAttributeContext(
                    var_node=node, line_number=line_no,
                    filename=origin_fname,
                    vulnerability_text=part)
                yield res
