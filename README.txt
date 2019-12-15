===========================================
Interpreter for Pleasant, written in Python
===========================================

Pleasant is a toy language designed for use in a Programming Languages class. The intended project was to write a lexer and parser for the language, and use the provided C-runtime to execute code.

I misunderstood the instructions and ended up writing a full interpreter for the language. On the bright side, I learned an immense amount about how interpreters work. 

To run the interpreter, use:

    $ ./interpreter <source_file.main> 

To run all test files, use:

    $ ./interpreter TEST



Brief overview of each file:

lexer.py:
    Contains all the necessary lexing utilities for the parser, 

    - Tokenizer class: implements must_match and try_match utilities. Used in parser to consume tokens and store the
      global text

    - Also contains fail function for errors

parser.py:
    Contains the parser and interpretation functionality.

    - Values are wrapped in Expression objects, which use an evaluate() method to extract the wrapped value, depending
      on whether the expression was a const value, a variable, or a function call.

    - Statements are wrapped in various objects, which contain the relevent information for execution, i.e. type of
      statement, arguments, expressions, variable names, etc.

    - Parsing involves building a queue of statements to be executed and defining functions at the end.

    - Scope is kept track of through two different dictionaries: scope (for standard variables) and active_params (for
      parameters). Scope has two layers: function depth, and current scope number, which track recursive calls and
      statement blocks respectively. In this method, any variable defined in the current function depth and <= the
      current scope are available. However, if a variable is defined inside a statement block, it won't be available
      outside of it (for a demonstration of this, run $ ./interpreter tests/scope_test.main). As parameters don't need
      to be distinguished by statement blocks, active_params only keeps track of function depth.

    - Execution involves looping through the statement queue and executing them in order.

    - Line number and char number are tracked and embedded into each Statement object, in case a runtime error occurs.
      There is no function traceback features, unfortunately.

interpreter:
    Simply a wrapper for execution of parser.parse

    - Accepts input file name as command line argument, executes it using parser.parse
