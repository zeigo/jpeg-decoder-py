class Stream:
    def __init__(self):
        self.pos = 0
        self.bitpos = 7 # msb 7, lsb 0
        self.buffer = []

    def write_byte(self, val):
        self.buffer.append(val)
    
    def read_bit(self):
        mask = 1 << self.bitpos
        bit = (self.buffer[self.pos] & mask) >> self.bitpos
        self.bitpos = (self.bitpos - 1) % 8
        if self.bitpos == 7: self.pos += 1
        return bit