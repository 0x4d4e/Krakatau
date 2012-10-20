import collections, itertools
import struct, operator

from . import instructions
from .. import constant_pool
from ..classfile import ClassFile
from ..method import Method
from ..field import Field

class AssemblerError(Exception):
    def __init__(self, message, data=None):
        super(AssemblerError, self).__init__(message)
        self.data = data

def error(msg):
    raise AssemblerError(msg)

class PoolRef(object):
    def __init__(self, *args, **kwargs):
        self.index = kwargs.get('index')
        self.lbl = kwargs.get('lbl')
        self.args = args

    def toIndex(self, pool, forbidden=()):
        if self.index is not None:
            return self.index
        if self.lbl:
            self.index = pool.getLabel(self.lbl, forbidden)
        else:
            self.args = [(x.toIndex(pool) if isinstance(x, PoolRef) else x) for x in self.args]
            self.index = pool.getItem(*self.args)
        return self.index

class PoolInfo(object):
    def __init__(self):
        self.pool = constant_pool.ConstPool()
        self.lbls = {}

    def getLabel(self, lbl, forbidden=()):
        if lbl in forbidden:
            error('Recursive constant pool reference: ' + ', '.join(forbidden))
        forbidden = forbidden + (lbl,)
        return self.lbls[lbl].toIndex(self, forbidden)

    def getItem(self, type_, *args):
        return self.pool.getItemRaw((type_, tuple(args)))

    def Utf8(self, s):
        return self.getItem('Utf8', s)



_format_ops = collections.defaultdict(tuple)
_format_ops[''] = instructions.instrs_noarg
_format_ops['>B'] = 'iload', 'lload', 'fload', 'dload', 'aload', 'istore', 'lstore', 'fstore', 'dstore', 'astore', 'ret'
_format_ops['>h'] = 'ifeq', 'ifne', 'iflt', 'ifge', 'ifgt', 'ifle', 'if_icmpeq', 'if_icmpne', 'if_icmplt', 'if_icmpge', 'if_icmpgt', 'if_icmple', 'if_acmpeq', 'if_acmpne', 'goto', 'jsr', 'ifnull', 'ifnonnull'
_format_ops['>H'] = 'ldc_w', 'ldc2_w', 'getstatic', 'putstatic', 'getfield', 'putfield', 'invokevirtual', 'invokespecial', 'invokestatic', 'invokedynamic', 'new', 'anewarray', 'checkcast', 'instanceof'

_format_ops['>b'] += 'bipush', 
_format_ops['>Bb'] += 'iinc', 
_format_ops['>h'] += 'sipush', 
_format_ops['>HB'] += 'invokeinterface', 'multianewarray'
_format_ops['>B'] += 'ldc', 'newarray'
_format_ops['>i'] += 'goto_w', 'jsr_w'

_op_structs = {}
for fmt, ops in _format_ops.items():
    s = struct.Struct(fmt)
    for op in ops:
        _op_structs[op] = s

def getPadding(pos):
    return (3-pos) % 4

def getInstrLen(instr, pos):
    op = instr[0]
    if op in _op_structs:
        return 1 + _op_structs[op].size
    elif op == 'wide':
        return 2 * len(instr[1])
    else:
        padding = getPadding(pos)
        count = len(instr[1][1])
        if op == 'tableswitch':
            return 13 + padding + 4*count
        else:
            return 9 + padding + 8*count 

def assembleInstruction(instr, labels, pos, pool):
    def lbl2Off(lbl):
        if lbl not in labels:
            del labels[None]
            error('Undefined label: {}\nDefined labels for current method are: {}'.format(lbl, ', '.join(sorted(labels))))
        return labels[lbl] - pos


    op = instr[0]
    first = chr(instructions.allinstructions.index(op))

    instr = [(x.toIndex(pool) if isinstance(x, PoolRef) else x) for x in instr[1:]]
    if op in instructions.instrs_lbl:
        instr[0] = lbl2Off(instr[0])
    if op in _op_structs:
        rest = _op_structs[op].pack(*instr)
        return first+rest
    elif op == 'wide':
        subop, args = instr[0]
        prefix = chr(instructions.allinstructions.index(subop))
        rest = struct.pack('>'+'H'*len(args), args)
        return first + prefix + rest
    else:
        padding = getPadding(pos)
        param, jumps, default = instr[0]
        default = lbl2Off(default)

        if op == 'tableswitch':
            jumps = map(lbl2Off, jumps)
            low, high = param, param + len(jumps)-1
            temp = struct.Struct('>i')
            part1 = first + '\0'*padding + struct.pack('>iii', default, low, high)
            return part1 + ''.join(map(temp.pack, jumps))
        elif op == 'lookupswitch':
            jumps = {k:lbl2Off(lbl) for k,lbl in jumps}
            jumps = sorted(jumps.items())
            temp = struct.Struct('>ii')
            part1 = first + '\0'*padding + struct.pack('>ii', default, len(jumps))
            part2 = ''.join(map(temp.pack, *zip(*jumps))) if jumps else ''
            return part1 + part2
        
def assembleCodeAttr(statements, pool, addLineNumbers, jasmode):
    if not statements:
        return None
    directives = [x[1] for x in statements if x[0] == 'dir']
    lines = [x[1:] for x in statements if x[0] == 'ins']

    offsets = []

    labels = {}
    pos = 0
    for lbl, instr in lines:
        labels[lbl] = pos
        if instr is not None:
            offsets.append(pos)
            pos += getInstrLen(instr, pos)

    code_bytes = ''
    for lbl, instr in lines:
        if instr is not None:
            code_bytes += assembleInstruction(instr, labels, len(code_bytes), pool)

    stack = locals_ = 65535
    excepts = []
    for d in directives:
        if d[0] == 'catch':
            name, start, end, target = d[1:]
            #Hack for compatibility with Jasmin
            if jasmode and name.args and (name.args[1].args == ('Utf8','all')):
                name.index = 0
            vals = labels[start], labels[end], labels[target], name.toIndex(pool)
            excepts.append(struct.pack('>HHHH',*vals))
        elif d[0] == 'stack':
            stack = min(stack, d[1])
        elif d[0] == 'locals':
            locals_ = min(locals_, d[1])

    attributes = []
    if addLineNumbers:
        lntable = [struct.pack('>HH',x,x) for x in offsets]
        ln_attr = struct.pack('>HIH', pool.Utf8("LineNumberTable"), 2+4*len(lntable), len(lntable)) + ''.join(lntable)        
        attributes.append(ln_attr)

    name_ind = pool.Utf8("Code")
    attr_len = 12 + len(code_bytes) + 8*len(excepts) + sum(map(len, attributes))
    
    assembled_bytes = struct.pack('>HIHHI', name_ind, attr_len, stack, locals_, len(code_bytes))
    assembled_bytes += code_bytes
    assembled_bytes += struct.pack('>H', len(excepts)) + ''.join(excepts)
    assembled_bytes += struct.pack('>H', len(attributes)) + ''.join(attributes)
    return assembled_bytes

def assemble(tree, addLineNumbers=False, jasmode=False):
    pool = PoolInfo()
    classdec, superdec, interface_decs, topitems = tree
    #scan topitems, plus statements in each method to get cpool directives

    interfaces = []
    fields = []
    methods = []
    attributes = []

    top_d = collections.defaultdict(list)
    for t, val in topitems:
        top_d[t].append(val)

    for slot, value in top_d['const']:
        if slot.index is not None:
            error('Assigning to directly constant pool indices is not currently supported.') 
        lbl = slot.lbl
        pool.lbls[lbl] = value

    for flags, name, desc, const in top_d['field']:
        flagbits = map(Field.flagVals.get, flags)
        flagbits = reduce(operator.__or__, flagbits, 0)
        name = name.toIndex(pool)
        desc = desc.toIndex(pool)

        if const is not None:
            attr = struct.pack('>HIH', pool.Utf8("ConstantValue"), 2, const.toIndex(pool))
            fattrs = [attr]
        else:
            fattrs = []

        field_code = struct.pack('>HHHH', flagbits, name, desc, len(fattrs)) + ''.join(fattrs)
        fields.append(field_code)


    for header, statements in top_d['method']:
        mflags, (name, desc) = header
        name = name.toIndex(pool)
        desc = desc.toIndex(pool)

        flagbits = map(Method.flagVals.get, mflags)
        flagbits = reduce(operator.__or__, flagbits, 0)

        code = assembleCodeAttr(statements, pool, addLineNumbers, jasmode)
        mattrs = [code] if code is not None else []        

        method_code = struct.pack('>HHHH', flagbits, name, desc, len(mattrs)) + ''.join(mattrs)
        methods.append(method_code)

    if addLineNumbers:
        sourceattr = struct.pack('>HIH', pool.Utf8("SourceFile"), 2, pool.Utf8("SourceFile"))
        attributes.append(sourceattr)

    interfaces = [x.toIndex(pool) for x in interface_decs]

    intf, cflags, this = classdec
    cflags = set(cflags)
    if intf:
        cflags.add('INTERFACE')
    if jasmode:
        cflags.add('SUPER')

    flagbits = map(ClassFile.flagVals.get, cflags)
    flagbits = reduce(operator.__or__, flagbits, 0)
    this = this.toIndex(pool)
    super_ = superdec.toIndex(pool)

    class_code = '\xCA\xFE\xBA\xBE' + struct.pack('>HH', 0, 49)
    class_code += pool.pool.bytes()
    class_code += struct.pack('>HHH', flagbits, this, super_)
    for stuff in (interfaces, fields, methods, attributes):
        bytes = struct.pack('>H', len(stuff)) + ''.join(stuff)
        class_code += bytes

    name = pool.pool.getArgs(this)[0]
    return name, class_code