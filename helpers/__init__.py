def humanize(value):
    return "{:,}".format(round(value)).replace(",", ".")