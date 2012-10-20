from __future__ import division
import struct, collections
import types

import binUnpacker
import bytecode
from attributes_raw import get_attributes_raw

class Field(object):
    flagVals = {'PUBLIC':0x0001,
                'PRIVATE':0x0002,
                'PROTECTED':0x0004,
                'STATIC':0x0008,
                'FINAL':0x0010,
                'VOLATILE':0x0040,
                'TRANSIENT':0x0080,
                'SYNTHETIC':0x1000, 
                'ENUM':0x4000,
                }

    def __init__(self, data, classFile):
        self.class_ = classFile
        cpool = self.class_.cpool
        
        flags, self.name_id, self.desc_id, self.attributes = data

        self.name = cpool.getArgsCheck('Utf8', self.name_id)
        self.descriptor = cpool.getArgsCheck('Utf8', self.desc_id)
        # print 'Loading field ', self.name, self.descriptor

        self.flags = set(name for name,mask in Field.flagVals.items() if (mask & flags))
        self.static = 'STATIC' in self.flags

    def __str__(self):
        parts = map(str.lower, self.flags)
        parts += [self.descriptor, self.name]
        return ' '.join(parts)