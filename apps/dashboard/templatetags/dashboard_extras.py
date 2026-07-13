from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Django templates can't do `dict.dynamic_key` — the segment after a
    dot is always a literal string, never a resolved variable. Used by
    the reports preview table, where column names come from a loop."""
    if dictionary is None:
        return ''
    return dictionary.get(key, '')
