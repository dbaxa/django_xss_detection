from django import template


class SimpleConditionNode(template.Node):
    child_nodelists = ('nodelist_true', 'nodelist_false')

    def __init__(self, nodelist_true, nodelist_false, name):
        self.nodelist_true = nodelist_true
        self.nodelist_false = nodelist_false
        self.name = name

    def repr(self):
        return "<SimpleConditionNode %s>" % self.name

    def render(self, context):
        return self.nodelist_true.render(context) + '\n' + \
            self.nodelist_false.render(context)

    @classmethod
    def handle_token(cls, parser, token, kind):
        nodelist_true = parser.parse(('else', 'end%s' % kind))
        token = parser.next_token()
        if token.contents == 'else':
            nodelist_false = parser.parse(('end%s' % kind, ))
            parser.delete_first_token()
        else:
            nodelist_false = template.NodeList()
        return cls(nodelist_true, nodelist_false, kind)
