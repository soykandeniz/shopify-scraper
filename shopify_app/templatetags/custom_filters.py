from django import template

register = template.Library()


@register.filter(name="dict_key")
def dict_key(d, key):
    """Returns the given key from a dictionary."""
    return d.get(key, "")


@register.filter(name="split")
def split(value, delimiter="\n"):
    """Split the value by delimiter."""
    if value:
        return value.split(delimiter)
    return []
