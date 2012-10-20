from ply import lex
import ast

from ..classfile import ClassFile
from ..method import Method
from ..field import Field
from .. import constant_pool

from . import instructions as ins

directives = 'CLASS','INTERFACE','SUPER','IMPLEMENTS','CONST','FIELD','METHOD','END','LIMIT','CATCH'
keywords = ['METHOD','LOCALS','STACK','FROM','TO','USING','DEFAULT']
flags = ClassFile.flagVals.keys() + Method.flagVals.keys() + Field.flagVals.keys()

words = keywords + flags + constant_pool.name2Type.keys()
wordget = {w.lower():w.upper() for w in words}
wordget.update({'.'+w.lower():'D'+w for w in directives})

assert(set(wordget).isdisjoint(ins.allinstructions))
for op in ins.instrs_noarg:
    wordget[op] = 'OP_NONE'
for op in ins.instrs_int:
    wordget[op] = 'OP_INT'
for op in ins.instrs_lbl:
    wordget[op] = 'OP_LBL'
for op in ('getstatic', 'putstatic', 'getfield', 'putfield'):
    wordget[op] = 'OP_FIELD'
#support invokenonvirtual for backwards compatibility with Jasmin
for op in ('invokevirtual', 'invokespecial', 'invokestatic', 'invokedynamic', 'invokenonvirtual'): 
    wordget[op] = 'OP_METHOD'
for op in ('new', 'anewarray', 'checkcast', 'instanceof'):
    wordget[op] = 'OP_CLASS'
for op in ('wide','lookupswitch','tableswitch'):
    wordget[op] = 'OP_' + op.upper()

wordget['ldc'] = 'OP_LDC1'
wordget['ldc_w'] = 'OP_LDC1'
wordget['ldc2_w'] = 'OP_LDC2'
wordget['iinc'] = 'OP_INT_INT'
wordget['newarray'] = 'OP_NEWARR'
wordget['multianewarray'] = 'OP_CLASS_INT'
wordget['invokeinterface'] = 'OP_METHOD_INT'

for op in ins.allinstructions:
    wordget.setdefault(op,op.upper())

#special PLY value
tokens = ('NEWLINE', 'COLON', 'EQUALS', 'GENERIC', 'CPINDEX', 
    'STRING_LITERAL', 'INT_LITERAL', 'LONG_LITERAL', 'FLOAT_LITERAL', 'DOUBLE_LITERAL') + tuple(set(wordget.values()))

def t_WORDS(t):
    t.type = wordget[t.value]
    return t
t_WORDS.__doc__ = r'(?:{})(?=$|[\s])'.format('|'.join(wordget.keys()))

def t_ignore_COMMENT(t):
    r';.*'

# Define a rule so we can track line numbers
def t_NEWLINE(t):
    r'\n+'
    t.lexer.lineno += len(t.value)
    return t

def t_STRING_LITERAL(t):
    r'''[rR]?"([^"\\]*(?:\\.[^"\\]*)*)"'''
    #regex from http://stackoverflow.com/questions/430759/regex-for-managing-escaped-characters-for-items-like-string-literals/5455705#5455705
    t.value = ast.literal_eval(t.value)
    return t

#careful here: | is not greedy so hex must come first
t_INT_LITERAL = r'-?(?:0[xX][0-9a-fA-F]+|[0-9]+)' 
t_LONG_LITERAL = t_INT_LITERAL + r'[lL]'
t_DOUBLE_LITERAL = r'(?:NaN|[-+]?(?:Inf|\d+\.\d+(?:[eE]-?\d+)?|0[xX][0-9a-fA-F]*\.[0-9a-fA-F]+[pP]-?\d+))'
t_FLOAT_LITERAL = t_DOUBLE_LITERAL + r'[fF]'

t_COLON = r':'
t_EQUALS = r'='
t_CPINDEX = r'\[[0-9a-z_]+\]'
t_GENERIC = r'[^\s:="]+'
t_ignore = ' \t\r'

def t_error(t):
    print 'Parser error on line {} at {}'.format(t.lexer.lineno, t.lexer.lexpos)
    print t.value[:79]

def makeLexer(**kwargs):
    return lex.lex(**kwargs)