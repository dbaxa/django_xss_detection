# django xss detection
This package contains a django template parser that can be used to find templates
that contain variables that will not be escaped. This package currently has
no knowledge of custom filters, custom tags, and python code (e.g. uses of
mark safe). The code has only been tested against django versions >= 1.5 and <= 1.7(beta 1).

## Requirements
	* django >= 1.5
	* lxml
## Usage
This package can be used on the command line by running
> `python -m django_xss_detection.cli`

## How does it work?
The code works by monkey patching django template code and providing through 
a callback function to VariableNode that ends up referring to the
`CompileStringWrapper.handle_callback` method. The callback function is used
later when the code `renders` a given template and encounters a variable node
that will not be escaped. The implementation of detecting unquoted variable nodes 
in element attributes and variable nodes in a javascript context lacking 
javascript escaping are not implemented through callbacks, see
`get_non_quoted_attr_vars_for_template` and 
`get_non_js_escaped_results_for_template` in parse_template.py respectively.

Additionally, the code has modified versions of built in conditional tags,
such as `{% if %}` and `{% ifequal %}`, so as to `render` all possible template
code. If this package does not work on your custom template tags then
you can add support for them similar to how `waffle` template tags are
implemented (see `templatetags/waffle.py` and the `patch` method in `util.py`).
