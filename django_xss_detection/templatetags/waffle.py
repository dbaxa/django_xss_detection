from django import template
from . import SimpleConditionNode
register = template.Library()


@register.tag('flag')
def flag(parser, token):
    return SimpleConditionNode.handle_token(parser, token, 'flag')


@register.tag('switch')
def switch(parser, token):
    return SimpleConditionNode.handle_token(parser, token, 'switch')


@register.tag('sample')
def sample(parser, token):
    return SimpleConditionNode.handle_token(parser, token, 'sample')
