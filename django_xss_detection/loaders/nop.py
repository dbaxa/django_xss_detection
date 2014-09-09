from django.template.loader import BaseLoader, get_template_from_string


class Loader(BaseLoader):
    """ This loader will always return an 'empty' template and *therefore*
        *should* be the last loader in settings.TEMPLATE_LOADERS.
    """
    is_usable = True

    def load_template(self, template_name, template_dirs=None):
        template = get_template_from_string('', None, template_name)
        return template, None

    def load_template_source(self, template_name, template_dirs=None):
        return '', None
