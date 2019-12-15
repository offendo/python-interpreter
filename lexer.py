import itertools as it
import functools as ft
import re
import sys


global linenumber
global charnumber
linenumber = 1
charnumber = 0

# Interface for eating tokens, Class Tokenizer
class Tokenizer:# {{{
    def __init__(self, string):
        self.string = string 
        self.token = None

    def try_lookahead(self, wanted):
        token, temp = consume_token(self.string)
        next_token, _ = consume_token(temp)
        return wanted == next_token

    def try_match(self, wanted):
        token, _ = consume_token(self.string)
        return wanted == token

    def must_match(self, wanted):
        global charnumber
        token, rest = consume_token(self.string, update_pos=True)
        if not self.try_match(wanted):
            charnumber -= (len(token) - 1)
            fail(f"Token '{wanted}' expected, but received '{token}'")
        self.string = rest
        return token, rest

    def try_match_regex(self, regex):
        token, rest = consume_token(self.string)
        match = re.match(regex, token)
        return bool(match)

    def must_match_regex(self, regex):
        global charnumber
        token, rest = consume_token(self.string, update_pos=True)
        match = re.match(regex, token)
        if match is None:
            charnumber -= (len(token) - 1)
            fail(f"Regex {regex} expected, but no match!")
        self.string = rest
        return token# }}}


# Following functions are for tokenizing text
def consume_identifier(string):# {{{
    identifier = '[a-zA-Z][a-zA-Z0-9._]*'
    match = re.match(identifier, string)
    if match:
        return match.group(0), string[match.end():]
    return None, string# }}}

def consume_number(string):# {{{
    num = re.compile('-?\d+')
    match = re.match(num, string)
    if match is None:
        return None, string
    return string[:match.end()], string[match.end():] # }}}

def consume_string(mstr, string):# {{{
    if string.startwith(mstr):
        return mstr, string[len(mstr):]
    return None, string# }}}

def strip_ws(string, update_pos=False):# {{{
    global linenumber, charnumber
    rest = string.lstrip()
    deleted = string[:len(string) - len(rest)]
    if update_pos:
        # adjust newline count and char count
        newlines = deleted.count('\n')
        last_newline = deleted[::-1].find('\n')
        # move the char marker up for each space 
        if newlines > 0:
            linenumber += newlines
            charnumber = last_newline
    return deleted, rest# }}}

def consume_string_literal(string):# {{{
    if string[0] == '"':
        close = string[1:].index('"')
        return string[:close+2], string[close+2:]
    return None, string# }}}

def consume_comment(string):# {{{
    if string[0] == '#':
        newline = string.find('\n')
        if newline == -1:
            return string, None
        return string[:newline], string[newline:]
    return None, string# }}}

def consume_char_tokens(string):# {{{
    char_tokens = [ '{', '}', '(', ')', '=', ',', ';']
    if string[0] in char_tokens:
        return string[0], string[1:]
    return None, string# }}}

# consume whatever the next token happens to be, fail otherwise
def consume_token(string, update_pos=False):# {{{
    global charnumber
    global linenumber
    ws, string = strip_ws(string, update_pos)
    if not string:
        return None, None
    # delete comment if it's there
    comment, string = consume_comment(string)
    while comment:
        ws, string = strip_ws(string, update_pos)
        comment, string = consume_comment(string)
    if string is None:
        return None, None

    # is the first character important???
    token, string = consume_char_tokens(string)
    if token:
        charnumber += len(token) * update_pos
        return token, string
    # is there a string literal "I am a string"???
    token, string = consume_string_literal(string)
    if token:
        charnumber += len(token) * update_pos
        return token, string
    # is there an identifier (alpha + alnum)???
    token, string = consume_identifier(string)
    if token:
        charnumber += len(token) * update_pos
        return token, string
    # is there a number???
    token, string = consume_number(string)
    if token:
        charnumber += len(token) * update_pos
        return token, string
    fail(f"Not sure what to make of this: not comment, string, identifier, or integer: {string[:50]}...")# }}}

# errors {{{
class UnexpectedTokenException(Exception):
    pass

class ParsingException(Exception):
    pass# }}}

# fail function{{{
def fail(message, linenum=None):
    global linenumber, charnumber
    sys.tracebacklimit = None
    if linenum is not None:
        header = f"\n\nError at line {linenum}:{charnumber}\n"
    else:
        header = f"\n\nError at line {linenumber}:{charnumber}\n"
    raise ParsingException(header + message)# }}}
