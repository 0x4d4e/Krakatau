def get_attribute_raw(bytestream):
    name_ind, length = bytestream.get('>HL')
    data = bytestream.getRaw(length)
    return name_ind,data

def get_attributes_raw(bytestream):
    attribute_count = bytestream.get('>H')
    return [get_attribute_raw(bytestream) for i in range(attribute_count)]
