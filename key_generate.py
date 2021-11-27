from random import choice

alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def key_generate():
    key = ""
    for _ in range(6):
        key += choice(alpha)

    return key
