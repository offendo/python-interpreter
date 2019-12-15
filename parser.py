#!/usr/bin/python3
from lexer import *
import lexer as lex
import sys
import os
sys.tracebacklimit = None

IDENTIFIER = '[a-zA-Z][a-zA-Z0-9_.]*'
NUMBER = '([0-9]+)|(-[0-9]+)'
STRING_LITERAL = '".*'

# global avl                  # nested dictionary of variables: {scope: {var: val, var2: val2}, ... }
global known_functions      # dictionary of Function objects 
global scope_num            # int which keeps track of scope
global current_module_name  # module name to prepend to functions
global statement_queue      # list of statements to execute, in order
global active_params
global function_depth
global scope
global tokenizer

function_depth = 0
known_functions = {}
scope_num = 0
current_module_name = 'main'
statement_queue = []
active_params = {function_depth: {}}
scope = {function_depth: {scope_num: {}}}


def parse(filename):# {{{
    global tokenizer
    text = open(filename, 'r').read()
    tokenizer = Tokenizer(text)
    initialize_known_functions()
    main_module_exports()
    for s in statement_queue:
        s.handle()# }}}

##### utilities #####
#===================#

def increase_scope():# {{{
    global scope 
    global scope_num
    global function_depth
    scope_num += 1
    scope[function_depth][scope_num] = {}
    # }}}

def decrease_scope():# {{{
    global scope 
    global scope_num
    global function_depth
    scope[function_depth].pop(scope_num)
    scope_num -= 1
    # }}}

def increase_depth():# {{{
    global function_depth
    global scope
    global scope_num
    function_depth += 1
    scope_num = 0
    scope[function_depth] = {scope_num: {}}
    active_params[function_depth] = {}
    # }}}

def decrease_depth():# {{{
    global function_depth
    global scope
    global scope_num
    scope.pop(function_depth)
    active_params.pop(function_depth)
    function_depth -= 1
    scope_num = max(scope[function_depth].keys())
    # }}}

def get_var(name):# {{{
    global active_params
    global scope
    global scope_num
    global function_depth
    if name in active_params[function_depth]:
        return active_params[function_depth][name]
    for num in range(scope_num, -1, -1):
        if name in scope[function_depth][num]:
            return scope[function_depth][num][name]
    fail(f'Variable {name} not found in active parameters or current scope')# }}}

def is_var_defined(name):# {{{
    global active_params
    global scope
    global scope_num
    global function_depth
    if name in active_params[function_depth]:
        return (function_depth, None)
    for num in range(scope_num, -1, -1):
        if name in scope[function_depth][num]:
            return (function_depth, num) 
    return None, None# }}}

def set_var(name, value, depth, num=None):# {{{
    # global function_depth
    global active_params
    global scope
    # global scope_num
    if num is None:
        active_params[depth][name] = value
    else:
        scope[depth][num][name] = value# }}}


##### interpreter #####
#=====================#

class Expression:# {{{
    def __init__(self, kind, value=None, name=None, args=None, linenum=None):
        self.kind = kind  # number, string, variable, function
        self.value = value # if number or string, the value of it; else, None
        self.name = name # if number or string, None; else, name associated with the variable or function
        self.args = args
        self.linenum = linenum

    def evaluate(self):
        global known_functions
        global scope_num
        global function_depth
        global scope

        if self.kind == 'value':
            return self.value
        elif self.kind == 'variable':
            var = get_var(self.name)
            return var.evaluate()
        elif self.kind == 'function':
            if self.name in known_functions:
                output = known_functions[self.name].call(self.args).evaluate() # args is a list of Expressions
                return output

            fail(f"Unknown function '{self.name}'", self.linenum)
# }}}

class Function:# {{{
    def __init__(self, name, inputs, outputs, statements):
        self.name = name
        self.outputs = outputs
        self.inputs = inputs
        self.statements = statements # list of statement objects, either assign, while etc.
        global known_functions

        if self.name in known_functions:
            if known_functions[self.name].is_defined(): # we already have a defined function
                fail(f"Function {self.name} has already been defined.") # redefinition of same function
            elif not self.is_defined(): # function isn't defined, so are we defining it now?
                fail(f"Function {self.name} has already been declared.") # no, so we're repeating a declaration
            else: # we are providing a definition
                known_functions[self.name] = self

    def set_statements(self, stmts):
        self.statements = stmts

    def is_defined(self):
        return self.statements is not None

    def call(self, arguments): # arguments is a list of expressions
        # print(f'calling {self.name} with {[a.value for a in arguments]}')
        if not self.is_defined():
            fail(f"Function '{self.name}' declared, but undefined")

        global scope
        global scope_num
        global function_depth

        if len(self.inputs) != len(arguments):
            fail(f"Error in call of function {self.name}: expected {len(self.inputs)} args, but got"
                    f" {len(arguments)}") # mismatched inputs

        values = [expr.evaluate() for expr in arguments] # evaluate the function arguments

        increase_depth() # increase depth by one, we're going into a function call

        for key, val in zip(self.inputs.keys(), values):  # for every value in the function arguments
            expr = Expression('value', val, None, None, lex.linenumber)
            active_params[function_depth][key] = expr  # set the value in the current scope (which is 0) to the appropriate value

        for key in self.outputs.keys():                   # same thing with function outputs
            active_params[function_depth][key] = None  # but just set them to None for now, since we don't know what they are

        for s in self.statements:
            s.handle() # handle each statement in turn

        outs = []
        for name in self.outputs.keys():
            val = get_var(name).evaluate() # evaluate the expression and rewrap the result in expression
            outs.append(val) # during the function call, these variables were assigned values and we want to return these values
        
        if len(outs) == 1:
            outs = outs[0]
        expr = Expression('value', outs, None, None, lex.linenumber)
        decrease_depth() # heading out of the function call, pop out of depth
        # print(f'{self.name} returning {expr.evaluate()}')
        return expr # return the outputs}}}

class AssignStatement():# {{{
    def __init__(self, name, expr, linenum):
        self.names = name
        self.expr = expr
        self.linenum = linenum

    def handle(self):
        global scope
        global scope_num
        global function_depth
        global active_params
        # print(self.expr.value)
        values = self.expr.evaluate()
        if not isinstance(values, list) and not isinstance(values, tuple): # makes it zippable with the associated names
            values = [values]
        if len(values) != len(self.names):
            fail(f'Expected {len(self.names)} values, but got {len(values)}', self.linenum)

        for n, v in zip(self.names, values):
            expr = Expression('value', v, None, None, lex.linenumber)
            depth, snum = is_var_defined(n)
            if depth is None:
                fail(f"Variable '{n}' hasn't been defined.", self.linenum)
            set_var(n, expr, depth, snum)
# }}}
class WhileStatement():# {{{
    def __init__(self, condition, statements, linenum):
        self.condition = condition
        self.statements = statements 
        self.linenum = linenum

    def handle(self):
        global scope_num
        global scope
        global function_depth
        increase_scope()
        while self.condition.evaluate():
            for s in self.statements:
                s.handle()
        decrease_scope()
        # }}}

class IfElseStatement():# {{{
    def __init__(self, condition, true_statements, false_statements, linenum):
        self.condition = condition
        self.true_statements = true_statements
        self.false_statements = false_statements
        self.linenum = linenum

    def handle(self):
        increase_scope()
        if self.condition.evaluate():
            for s in self.true_statements:
                s.handle()
        else:
            if self.false_statements is not None:
                for s in self.false_statements:
                    s.handle()
        decrease_scope()
        # }}}

class FunctionCallStatement():# {{{
    def __init__(self, name, args, linenum):
        self.name = name
        self.args = args
        self.linenum = linenum

    def handle(self):
        global known_functions
        func = known_functions.get(self.name, None)
        if func is None:
            fail(f"Unknown function '{self.name}'", self.linenum)
        return func.call(self.args) # it's just a call for side-effects, probably }}}

class VariableDeclaration():# {{{
    def __init__(self, names, expr, linenum):
        self.names = names
        self.expr = expr
        self.linenum = linenum

    def handle(self):
        global scope
        global scope_num
        global function_depth

        values = self.expr.evaluate()

        if not isinstance(values, list):
            values = [values]
        if len(values) != len(self.names):
            fail(f'Expected {len(self.names)} values, but got {len(values)}', self.linenum)

        for n, v in zip(self.names, values):
            depth, snum = is_var_defined(n)
            if depth:
                fail(f"Variable '{n}' already declared.", self.linenum)
            # not already declared, so we're good to go
            expr = Expression('value', v, None, None, lex.linenumber)

            scope[function_depth][scope_num][n] = expr

    # }}}

class PythonFunction(): #{{{
    def __init__(self, name, func, inputs, outputs):
        self.name = name
        self.func = func
        self.inputs = inputs 
        self.outputs = outputs 
        global known_functions

        if self.name in known_functions:
            if known_functions[self.name].is_defined(): # we already have a defined function
                fail(f"Function {self.name} has already been defined.") # redefinition of same function
            elif not self.is_defined(): # function isn't defined, so are we defining it now?
                fail(f"Function {self.name} has already been declared.") # no, so we're repeating a declaration
            else: # we are providing a definition
                known_functions[self.name] = self

    def is_defined(self):
        return bool(self.func)

    def call(self, arguments): # arguments is a list of expressions
        # print(f'calling {self.name} with {[a.evaluate() for a in arguments]}')
        if not self.is_defined():
            fail(f"Function '{self.name}' declared, but undefined")

        global scope
        global scope_num
        global function_depth
         
        if len(self.inputs) != len(arguments):
            fail(f"Error in call of function {self.name}: expected {len(self.inputs)} args, but got"
                    f" {len(arguments)}") # mismatched inputs
        
        if self.name == 'integer.add':
            inps = [(a.kind, a.name, a.value) for a in arguments]
            # print(inps)
        outs = self.func(*[a.evaluate() for a in arguments])

        expr = Expression('value', outs, None, None, lex.linenumber)
        # print(f'{self.name} returning {expr.evaluate()}')
        return expr # return the output Expression 

    def save(self):
        global known_functions
        known_functions[self.name] = self # }}}


##### standard library #####
#==========================#

# integer functions {{{
def add(_temp_var_a, _temp_var_b):
    return _temp_var_a + _temp_var_b

def subtract(_temp_var_a, _temp_var_b):
    return _temp_var_a - _temp_var_b

def multiply(_temp_var_a, _temp_var_b):
    return _temp_var_a * _temp_var_b

def divide(_temp_var_a, _temp_var_b):
    return _temp_var_a // _temp_var_b, _temp_var_a % _temp_var_b

def sqrt(_temp_var_a):
    return int(_temp_var_a ** .5)

def equal(_temp_var_a, _temp_var_b):
    return _temp_var_a == _temp_var_b

def gcd(_temp_var_a, _temp_var_b):
   while _temp_var_b: 
       _temp_var_a, _temp_var_b = _temp_var_b, _temp_var_a % _temp_var_b 
   return _temp_var_a

# }}}

# linux system calls{{{
def write(_filedesc, _string, _length):
    _string = bytes(str(_string), 'utf-8').decode('unicode_escape').encode('utf-8')
    try:
        os.write(_filedesc, _string)
    except Exception as e:
        fail(f'Writing to {_filedesc} failed')
    return _length

def read(_filedesc, _numbytes):
    _temp_buffer = os.read(_filedesc, _numbytes).decode('unicode_escape')
    _count = len(_temp_buffer) 
    return _count, _temp_buffer

def file_open(_filename, **_flags):
    return open(_filename, **_flags).fileno()
# }}}

# string functions {{{

def length(_string):
    return len(str(_string))# }}}

def initialize_known_functions():# {{{
    ### integer functions ###
    PythonFunction('integer.add', add, ['a','b'], ['a']).save()
    PythonFunction('integer.subtract', subtract, ['a','b'], ['a']).save()
    PythonFunction('integer.multiply', multiply, ['a','b'], ['a']).save()
    PythonFunction('integer.divide', divide, ['a','b'], ['a']).save()
    PythonFunction('integer.equal', equal, ['a','b'], ['a']).save()
    PythonFunction('integer.sqrt', sqrt, ['a'], ['a']).save()
    PythonFunction('integer.gcd', gcd, ['a','b'], ['a']).save()
    ### linux system calls ###
    PythonFunction('linux.write', write, ['num','str','len'], ['bytes']).save()
    PythonFunction('linux.read', read, ['desc','num'], ['buf', 'var']).save()
    PythonFunction('linux.open', file_open, ['fname','flags'], ['desc']).save()
    ### string functions ###
    PythonFunction('string.length', length, ['str'], ['len']).save()



    # }}}


##### sections #####
#==================#

def main_module_exports():# {{{
    global current_module_name
    global tokenizer

    if tokenizer.try_match('main'):
        _ = tokenizer.must_match('main')
        current_module_name = 'main'
        declarations_section()
        program_section()
        functions_section()
    elif tokenizer.try_match('module'):
        _ = tokenizer.must_match('module') # token = 'module'
        token = tokenizer.must_match_regex(IDENTIFIER) # next token must be an identifier
        current_module_name = token       # module name is that token
        # section is exports
        if tokenizer.try_match('exports'):
            exports_section()
    elif tokenizer.try_match('imports'):
        imports_section()
        declarations_section()
        functions_section()
        # }}}

def program_section():# {{{
    global statement_queue
    global tokenizer
    _ = tokenizer.must_match('program')
    statements = statement_block()
    for s in statements:
        statement_queue.append(s)
# }}}

def exports_section():# {{{
    global tokenizer
    _ = tokenizer.must_match('exports')
    _ = tokenizer.must_match('{')
    function_declaration_list()
    _ = tokenizer.must_match('}')
# }}}

def imports_section():# {{{
    global tokenizer
    _ = tokenizer.must_match('imports')
    _ = tokenizer.must_match('{')
    module_list()
    _ = must_match('}')
# }}}

def declarations_section():# {{{
    global tokenizer
    _ = tokenizer.must_match('declarations')
    _ = tokenizer.must_match('{')
    function_declaration_list()
    _ = tokenizer.must_match('}')
    # }}}

def module_list():# {{{
    ''' Does nothing??? Just throws away some tokens?
    '''
    while not tokenizer.try_match('}'):
        token = tokenizer.must_match_regex(IDENTIFIER)
        _ = tokenizer.must_match(';')
# }}}


##### functions #####
#===================#

def functions_section():# {{{
    ''' Matches the section for function declarations
    '''
    _ = tokenizer.must_match('functions')
    _ = tokenizer.must_match('{')
    function_list()
    _ = tokenizer.must_match('}')
# }}}

def function():# {{{
    ''' Matches a function definition, and returns the Function object
    '''
    global current_module_name
    global known_functions
    global tokenizer

    _ = tokenizer.must_match('(')
    out_list = identifier_list()
    _ = tokenizer.must_match(')')
    _ = tokenizer.must_match('=')

    name = tokenizer.must_match_regex(IDENTIFIER)
    if '.' not in name:
        module_with_dot = current_module_name + '.'
        test_name = module_with_dot + name
        name = test_name

    # we can get rid of this error honestly, it doesn't matter for an interpreted language
    if name not in known_functions: 
        fail(f"Function '{name}' hasn't been declared, but is trying to be defined.")

    _ = tokenizer.must_match('(')
    in_list = identifier_list()
    _ = tokenizer.must_match(')')

    statements = statement_block() 
    func = known_functions[name]
    # set statements for the function, so it's now defined
    func.set_statements(statements)
# }}}

def function_list():# {{{
    ''' Matches functions until '}' is found, which marks the end of the functions section. 
        Then, returns the list of functions.
    '''
    while not tokenizer.try_match('}'):
        function()# }}}

def function_declaration():# {{{
    ''' Matches the declaration of a single function, and adds its existance to global known_functions
    '''
    global known_functions
    # syntax
    token = tokenizer.must_match('(')
    out_list = identifier_list()
    token = tokenizer.must_match(')')
    token = tokenizer.must_match('=')

    # semantics
    ident = tokenizer.must_match_regex(IDENTIFIER)
    name = current_module_name + '.' + ident

    # syntax
    token = tokenizer.must_match('(')
    in_list = identifier_list()
    token = tokenizer.must_match(')')
    token = tokenizer.must_match(';')

    # add this function to "known functions"
    func = Function(name, in_list, out_list, None) # not defined, so no statements
    known_functions[name] = func
# }}}

def function_declaration_list():# {{{
    ''' Matches function declarations until '}' is found, adding them all to known functions immediately
    '''
    while not tokenizer.try_match('}'):
        function_declaration()
# }}}

##### statements #####
#====================#

def variable_declaration():# {{{
    ''' Matches a variable declaration and returns the VariableDec statement object
    '''
    global tokenizer
    token = tokenizer.must_match('var')
    id_count = 0
    singleton = False
    name = ''
    names = []
    l = {}

    if tokenizer.try_match_regex(IDENTIFIER): # only one declaration
        # name of variable
        name = tokenizer.must_match_regex(IDENTIFIER)
        id_count += 1
        singleton = True
    else: # more than one declaration
        _ = tokenizer.must_match('(')
        l = identifier_list()
        _ = tokenizer.must_match(')')
        id_count = len(l)

    _ = tokenizer.must_match('=')
    expr = expression()
    _ = tokenizer.must_match(';')

    stmt = None
    if singleton:
        stmt = VariableDeclaration([name], expr, lex.linenumber) # gotta use [name] because VariableDec expects a list of strings 
    else:
        names = list(l.keys()) #[::-1]
        stmt = VariableDeclaration(names, expr, lex.linenumber) # there's >1 of them so add them all to the stack

    return stmt # }}}

def assignment_statement():# {{{
    ''' Assigns a new value to an already existing variable (no 'var' keyword)
    '''
    global tokenizer
    l = {}
    id_count = 0
    singleton = False
    if tokenizer.try_match_regex(IDENTIFIER):
        id_count = 1;
        name = tokenizer.must_match_regex(IDENTIFIER) # consume token
        singleton = True
    else:
        _ = tokenizer.must_match('(')
        l = identifier_list()
        _ = tokenizer.must_match(')')
        id_count = len(l)

    _ = tokenizer.must_match('=')
    expr = expression()
    _ = tokenizer.must_match(';')

    stmt = None
    if singleton:
        stmt = AssignStatement([name], expr, lex.linenumber)
    else:
        names = list(l.keys()) #[::-1]
        stmt = AssignStatement(names, expr, lex.linenumber)
    return stmt# }}}

def if_else_statement():# {{{
    global tokenizer
    # if (
    _ = tokenizer.must_match('if')
    _ = tokenizer.must_match('(')
    # condition
    expr = expression()
    # )
    _ = tokenizer.must_match(')')
    # then
    true_stmts = statement_block()
    # initialize
    false_stmts = None
    # else (
    if tokenizer.try_match('else'):
        _ = tokenizer.must_match('else')
        # then
        false_stmts = statement_block()

    # false_stmts might be none, but that is OK
    # this is handled in the evaluation stage
    if_else = IfElseStatement(expr, true_stmts, false_stmts, lex.linenumber)
    return if_else# }}}

def while_statement():# {{{
    # while (
    _ = tokenizer.must_match('while')
    _ = tokenizer.must_match('(')
    # condition
    cond = expression()
    # )
    _ = tokenizer.must_match(')')
    # then 
    statements = statement_block()
    while_stmt = WhileStatement(cond, statements, lex.linenumber)

    return while_stmt# }}}

def statement_block():# {{{
    ''' Returns a list of Statement objects (in order)
    '''
    # should increase scope number here, but we instead handle it during evalutation stage
    _ = tokenizer.must_match('{')
    statements = statement_list()
    _ = tokenizer.must_match('}')

    return statements # }}}

def statement_list():# {{{
    # global active_parameter_list
    statements = []
    while not tokenizer.try_match('}'):
        stmt = None
        if tokenizer.try_match('var'):
            stmt = variable_declaration()
        elif tokenizer.try_match('{'):
            stmt = statement_block()
        elif tokenizer.try_match('if'):
            stmt = if_else_statement()
        elif tokenizer.try_match('while'):
            stmt = while_statement()
        elif tokenizer.try_match('('):
            stmt = assignment_statement()
        elif tokenizer.try_match_regex(IDENTIFIER):
            if tokenizer.try_lookahead('('):
                stmt = function_call_statement() # just for side effects
                _ = tokenizer.must_match(';')
            elif tokenizer.try_lookahead('='):
                stmt = assignment_statement()
            else:
                fail("statement_list: Expected a statement")
        else:
            fail("statement_list: Expected a statement")
        # no matter what, add the statement to the list
        statements.append(stmt)

    # return the gathered statements 
    return statements # }}}


##### expressions #####
#=====================#

def expression():# {{{
    global tokenizer
    # we have a number!
    if tokenizer.try_match_regex(NUMBER):
        token = tokenizer.must_match_regex(NUMBER)
        return Expression('value', int(token), None, None, lex.linenumber)

    # we have a string!
    if tokenizer.try_match_regex(STRING_LITERAL):
        token = tokenizer.must_match_regex(STRING_LITERAL)
        return Expression('value', token.strip('"'), None, None, lex.linenumber) # get rid of "s around the string with strip

    if tokenizer.try_match_regex(IDENTIFIER):
        # we found a function
        if tokenizer.try_lookahead('('):
            return function_call() # return the outcome of function call (expr)
        # we found a variable
        else:
            name = tokenizer.must_match_regex(IDENTIFIER)
            return Expression('variable', None, name, None, lex.linenumber)
    fail("That's not an expression")# }}}

def function_call():# {{{
    ''' Matches and builds an expression with type function call
    '''
    global current_module_name
    global tokenizer

    name = tokenizer.must_match_regex(IDENTIFIER)

    if '.' not in name:
        module_with_dot = current_module_name + '.'
        test_name = module_with_dot + name
        name = test_name

    _ = tokenizer.must_match('(')
    arguments = argument_list()
    _ = tokenizer.must_match(')')

    func = Expression('function', None, name, arguments, lex.linenumber)
    # stmt = FunctionCallStatement(name, arguments)
    return func# }}}

def function_call_statement(): #{{{
    ''' Matches and builds a statement with type function call
    '''
    global current_module_name
    global tokenizer

    name = tokenizer.must_match_regex(IDENTIFIER)

    if '.' not in name:
        module_with_dot = current_module_name + '.'
        test_name = module_with_dot + name
        name = test_name

    _ = tokenizer.must_match('(')
    arguments = argument_list()
    _ = tokenizer.must_match(')')

    # func = Expression('function', None, name, arguments)
    stmt = FunctionCallStatement(name, arguments, lex.linenumber)
    return stmt# }}}

def argument():# {{{
    ''' Does nothing...literally. I'll keep it here for completeness
    '''
    pass# }}}

def argument_list():# {{{
    global tokenizer
    arguments = []
    while not tokenizer.try_match(')'):
        expr = expression()
        arguments.append(expr)
        if tokenizer.try_match(')'):
            break
        _ = tokenizer.must_match(',')
    return arguments# }}}

def identifier_list():# {{{
    global tokenizer
    l = {}
    while not tokenizer.try_match(')'):
        token = tokenizer.must_match_regex(IDENTIFIER)
        l[token] = ''
        if tokenizer.try_match(')'):
            break
        token = tokenizer.must_match(',')
    return l# }}}

