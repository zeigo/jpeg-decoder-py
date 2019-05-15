from marker import *
from huffman import create_huffman_tree
import numpy as np
from utils import *
from PIL import Image
import time
import math
from stream import Stream
from component import Component

class Decoder:
    def __init__(self, filename : str):
        self.filename = filename
        self.__buffer = open(filename, 'rb').read()
        self.pos = 0
        self.qts = {} # qt_id -> qt
        self.dc_ht = {} # ht_id -> ht
        self.ac_ht = {}
        self.components = {} # component_id -> Component object

        self.mode = None
        self.height = 0
        self.width = 0
        self.MCU_width = 0
        self.MCU_height = 0
        self.nr_MCUs_ver = 0
        self.nr_MCUs_hor = 0
        self.stuffed_height = 0
        self.stuffed_width = 0

        self.stream = None
        self.data = None

    def init_stream(self):
        """read entroy-encoded data between SOS and the next marker to the stream,
        remove byte padding 0x00, which follows a 0xff"""
        stream = Stream()
        while True:
            x = self.read_1b()
            if x != 0xff:
                stream.write_byte(x)
            else:
                y = self.read_1b()
                if y == 0x00: # remove byte padding 0x00
                    stream.write_byte(x)
                else: # x is the first byte of the next marker
                    self.pos -= 2
                    break
        self.stream = stream
        
    def read_bit(self):
        return self.stream.read_bit()
    
    def read_n_bits(self, n, extend = True):
        if n == 0: return 0
        bits = []
        for _ in range(n):
            bits.append(self.read_bit())
        if extend:
            return bits_to_coefficient(bits)
        else:
            return bits_to_number(bits)

    def read_2_4bit(self):
        val = self.read_1b()
        return val >> 4, val % (2 ** 4)

    def read_1b(self):
        self.pos += 1
        return self.__buffer[self.pos - 1]

    def read_1b_notconsume(self):
        return self.__buffer[self.pos]

    def read_2b(self):
        h, l = self.read_1b(), self.read_1b()
        return h * 256 + l

    def read_huffman_symbol(self, ht):
        """read bits from the stream and decode them according to Huffman table,
        return a Huffman-encoded symbol"""
        while True:
            symbol = ht.get_bit(self.read_bit())
            if symbol != None: return symbol

    def print_marker(self):
        """list file markers"""
        self.pos = 0
        while True:
            val = self.read_1b()
            if val == 0xff:
                marker_type = self.read_1b()
                if marker_type == 0 or marker_type == 0xff: continue
                if marker_type in marker_dict:
                    print(self.pos, marker_dict[marker_type])
                    if marker_type == EOI: return
                    if marker_type == SOI: continue
                    length = self.read_2b()
                    self.pos += length - 2 # skip the payload
                else:
                    print("unknown marker", hex(marker_type))

    def run(self):
        self.pos = 0
        start_time = time.time()
        while True:
            val = self.read_1b()
            if val == 0xff:
                marker_type = self.read_1b()
                if marker_type in marker_dict:
                    if marker_type == EOI: 
                        break
                    elif marker_type == SOI:
                        continue
                    elif marker_type == DHT:
                        self.read_huffman_table()
                    elif marker_type == DQT:
                        self.read_quantization_table()
                    elif marker_type == SOF0 or marker_type == SOF2:
                        self.read_frame(mode=marker_type)
                    elif marker_type == SOS:
                        self.read_scan()
                    elif marker_type == APP0 or marker_type == APP1:
                        length = self.read_2b()
                        self.pos += length - 2
                else:
                    print(hex(marker_type))
        print("scan ends:", time.time()-start_time)
        self.reverse_quantization()
        print("dequantization ends:", time.time()-start_time)
        self.reverse_zigzag()
        print("dezigzag ends:", time.time()-start_time)
        self.reverse_DCT()
        print("idct ends:", time.time()-start_time)
        self.reverse_split_block()
        print("reverse split ends:", time.time()-start_time)
        # self.reverse_color_space_transform()
        self.save()

    def read_frame(self, mode):
        """pos is end of marker"""
        length = self.read_2b()
        self.mode = mode
        sample_precision = self.read_1b() # almost always be 8
        assert sample_precision == 8, "Only precision 8 is supported"
        height = self.read_2b()
        width = self.read_2b()
        self.height, self.width = height, width
        nr_components = self.read_1b() # 3 for YCbCr or 1 for Y(grayscale)
        print(f"SOF, sample precision: {sample_precision}, height: {height}, width: {width}, number of components: {nr_components}")
        max_hf, max_vf = 1, 1
        for _ in range(nr_components):
            component_id = self.read_1b()
            hf, vf = self.read_2_4bit()
            if hf > max_hf: max_hf = hf
            if vf > max_vf: max_vf = vf
            qt_selector = self.read_1b()
            print(f"component_id: {component_id}, horizontal and vertical"
             f"sampling frequencies: {hf}-{vf}, qt selector: {qt_selector}")
            self.components[component_id] = Component(hf, vf, self.qts[qt_selector], component_id)
       
        self.MCU_width = 8 * max_hf
        self.MCU_height = 8 * max_hf
        self.nr_MCUs_ver = math.ceil(height / self.MCU_height)
        self.nr_MCUs_hor = math.ceil(width / self.MCU_width)
        self.stuffed_height = self.MCU_height * self.nr_MCUs_ver
        self.stuffed_width = self.MCU_width * self.nr_MCUs_hor
        for cp in self.components.values():
            cp.block_height = 8 * max_vf // cp.vf
            cp.block_width = 8 * max_hf // cp.hf
            cp.nr_blocks_ver = math.ceil(self.height/cp.block_height)
            cp.nr_blocks_hor = math.ceil(self.width/cp.block_width)
            cp.blocks = create_nd_array([self.stuffed_height//cp.block_height, self.stuffed_width//cp.block_width,64])

    def read_huffman_table(self):
        length = self.read_2b()
        # there can be multiple Huffman tables, so we loop until a 0xff indicates a new marker
        while self.read_1b_notconsume() != 0xff:
            table_class, ht_identifier = self.read_2_4bit()
            print(f"DHT, Huffman table: {ht_identifier}, for", ("AC" if table_class else "DC"))
            bits = []
            for _ in range(16):
                bits.append(self.read_1b())
            # print(bits)
            nr_codewords = sum(bits)
            huffvals = []
            for _ in range(nr_codewords):
                huffvals.append(self.read_1b())
            # print("huffvals:", huffvals)
            huffman_tree = create_huffman_tree(bits, huffvals)
            if table_class == 1:
                self.ac_ht[ht_identifier] = huffman_tree
            else:
                self.dc_ht[ht_identifier] = huffman_tree
            # huffman_tree.print_tree()

    def read_quantization_table(self):
        length = self.read_2b()
        # there can be multiple quantization tables, so we loop until a 0xff indicates a new marker
        while self.read_1b_notconsume() != 0xff:
            precision, identifier = self.read_2_4bit()
            print(f"DQT, quantization table precision: {precision}, identifier: {identifier}")
            # precision 0 for 8 bit, 1 for 16 bit
            if precision == 0:
                qt = []
                for _ in range(64):
                    qt.append(self.read_1b())
                self.qts[identifier] = qt
            elif precision == 1:
                qt = []
                for _ in range(64):
                    qt.append(self.read_2b())
                self.qts[identifier] = qt

    def read_scan(self):
        length = self.read_2b()
        nr_components = self.read_1b()
        print(f"SOS, number of components in a scan: {nr_components}")
        interleaved_components = []
        for _ in range(nr_components):
            component_selector = self.read_1b()
            DCht_selector, ACht_selector = self.read_2_4bit()
            cp = self.components[component_selector]
            cp.DCht = self.dc_ht[DCht_selector] if DCht_selector in self.dc_ht else None
            cp.ACht = self.ac_ht[ACht_selector] if ACht_selector in self.ac_ht else None
            interleaved_components.append(cp)
            print(f"component selector: {component_selector}, DC/AC huffman table {DCht_selector} {ACht_selector}")
        Ss = self.read_1b()
        Se = self.read_1b()
        Ah, Al = self.read_2_4bit()
        print(f"(Ss, Se) = {Ss}, {Se}, (Ah, Al) = {Ah}, {Al}")
        self.init_stream()
        if self.mode == SOF0: # sequential
            self.decode_sequential(interleaved_components)
        elif self.mode == SOF2: # progressive
            if Ss == 0:
                if Ah == 0: # DC first scan
                    self.decode_DC_progressive_first(interleaved_components, Al)
                else: # DC subsequent scan
                    self.decode_DC_progressive_subsequent(interleaved_components, Al)
            elif Ah == 0: # AC first scan
                self.decode_ACs_progressive_first(interleaved_components, Ss, Se, Al)
            else: # AC subsequent scan
                self.decode_ACs_progressive_subsequent(interleaved_components, Ss, Se, Al)
    
    def decode_sequential(self, interleaved_components):
        """Most sequential encoding is interleaved, here it doesn't support non-interleaved"""
        for cp in interleaved_components: cp.prev_DC = 0
        for i in range(self.nr_MCUs_ver):
            for j in range(self.nr_MCUs_hor):
                for cp in interleaved_components:
                    v_idx, h_idx = cp.vf * i, cp.hf * j # top-left block
                    for m in range(cp.vf):
                        for n in range(cp.hf):
                            block = cp.blocks[v_idx+m][h_idx+n]
                            cp.prev_DC = self.decode_sequential_per_block(cp.DCht, cp.ACht, block, cp.prev_DC)

    def decode_sequential_per_block(self, DCht, ACht, block, prev_DC):
        DC_size = self.read_huffman_symbol(DCht)
        newDC = self.read_n_bits(DC_size) + prev_DC
        block[0] = newDC
        idx = 1
        while idx <= 63:
            symbol = self.read_huffman_symbol(ACht)

            # end of block
            if symbol == EOB:
                break

            RUNLENGTH, SIZE = symbol >> 4, symbol % (2**4)
            idx += RUNLENGTH
            block[idx]= self.read_n_bits(SIZE)
            idx += 1
        return newDC

    def decode_DC_progressive_first(self, interleaved_components, Al):
        """DC can be interleaved"""
        for cp in interleaved_components: cp.prev_DC = 0
        for i in range(self.nr_MCUs_ver):
            for j in range(self.nr_MCUs_hor):
                for cp in interleaved_components:
                    v_idx, h_idx = cp.vf * i, cp.hf * j # top-left block
                    for m in range(cp.vf):
                        for n in range(cp.hf):
                            block = cp.blocks[v_idx+m][h_idx+n]
                            cp.prev_DC = self.decode_DC_progressive_first_per_block(cp.DCht, block, Al, cp.prev_DC)

    def decode_DC_progressive_first_per_block(self, DCht, block, Al, prev_DC):
        DC_size = self.read_huffman_symbol(DCht)
        newDC = self.read_n_bits(DC_size) + prev_DC
        block[0] = newDC << Al
        return newDC
        
    def decode_DC_progressive_subsequent(self, interleaved_components, Al):
        for i in range(self.nr_MCUs_ver):
            for j in range(self.nr_MCUs_hor):
                for cp in interleaved_components:
                    v_idx, h_idx = cp.vf * i, cp.hf * j # top-left block
                    for m in range(cp.vf):
                        for n in range(cp.hf):
                            block = cp.blocks[v_idx+m][h_idx+n]
                            self.decode_DC_progressive_subsequent_per_block(block, Al)

    def decode_DC_progressive_subsequent_per_block(self, block, Al):
        bit = self.read_bit()
        block[0] |= bit << Al

    def decode_ACs_progressive_first(self, interleaved_components, Ss, Se, Al):
        """must be non-interleaved"""
        cp = interleaved_components[0]
        length_EOB_run = 0
        for i in range(cp.nr_blocks_ver):
            for j in range(cp.nr_blocks_hor):
                block = cp.blocks[i][j]
                length_EOB_run = self.decode_ACs_progressive_first_per_block(cp.ACht, block, Ss, Se, Al, length_EOB_run)

    def decode_ACs_progressive_first_per_block(self, ACht, block, Ss, Se, Al, length_EOB_run):
        """the first scan of successive approximation or spectral selection only"""
        # this is a EOB
        if length_EOB_run > 0:
            return length_EOB_run - 1

        idx = Ss
        while idx <= Se:
            symbol = self.read_huffman_symbol(ACht)
            RUNLENGTH, SIZE = symbol >> 4, symbol % (2**4)

            if SIZE == 0:
                if RUNLENGTH == 15: # ZRL(15,0)
                    idx += 16
                else: # EOBn, n=0-14
                    return self.read_n_bits(RUNLENGTH, False) + (2**RUNLENGTH) - 1
            else:
                idx += RUNLENGTH
                block[idx] = self.read_n_bits(SIZE) << Al
                idx += 1
        return 0

    def decode_ACs_progressive_subsequent(self, interleaved_components, Ss, Se, Al):
        cp = interleaved_components[0]
        length_EOB_run = 0
        for i in range(self.nr_MCUs_ver):
            for j in range(self.nr_MCUs_hor):
                block = cp.blocks[i][j]
                length_EOB_run = self.decode_ACs_progressive_subsequent_per_block(cp.ACht, block, Ss, Se, Al, length_EOB_run)

    def decode_ACs_progressive_subsequent_per_block(self, ACht, block, Ss, Se, Al, length_EOB_run):
        idx = Ss
        # this is a EOB
        if length_EOB_run > 0:
            while idx <= Se:
                if block[idx] != 0:
                    self.refineAC(block, idx, Al)
                idx += 1
            return length_EOB_run - 1

        while idx <= Se:
            symbol = self.read_huffman_symbol(ACht)
            RUNLENGTH, SIZE = symbol >> 4, symbol % (2**4)
            if SIZE == 1: # zero history
                val = self.read_n_bits(SIZE) << Al
                while RUNLENGTH > 0 or block[idx] != 0:
                    if block[idx] != 0:
                        self.refineAC(block, idx, Al)
                    else:
                        RUNLENGTH -= 1
                    idx += 1
                block[idx] = val
                idx += 1
            elif SIZE == 0:
                if RUNLENGTH < 15: # EOBn, n=0-14 
                    # !!! read EOB run first
                    newEOBrun = self.read_n_bits(RUNLENGTH, False) + (1<<RUNLENGTH)
                    while idx <= Se:
                        if block[idx] != 0:
                            self.refineAC(block, idx, Al)
                        idx += 1
                    return newEOBrun - 1
                else: # ZRL(15,0)
                    while RUNLENGTH >= 0:
                        if block[idx] != 0:
                            self.refineAC(block, idx, Al)
                        else:
                            RUNLENGTH -= 1
                        idx += 1
        return 0

    def refineAC(self, block, idx, Al):
        val = block[idx]
        if val > 0:
            if self.read_bit() == 1:
                block[idx] += 1 << Al
        elif val < 0:
            if self.read_bit() == 1:
                block[idx] += (-1) << Al
            
    def reverse_quantization(self):
        for cp in self.components.values():
            for i in range(cp.nr_blocks_ver):
                for j in range(cp.nr_blocks_hor):
                    for k in range(64):
                        cp.blocks[i][j][k] *= cp.qt[k]


    def reverse_zigzag(self):
        for cp in self.components.values():
            for i in range(self.stuffed_height // cp.block_height):
                for j in range(self.stuffed_width // cp.block_width):
            # for i in range(cp.nr_blocks_ver):
            #     for j in range(cp.nr_blocks_hor):
                    cp.blocks[i][j] = zigzag2matrix(cp.blocks[i][j])

    def reverse_DCT(self):
        """cost the most time"""
        for cp in self.components.values():
            for i in range(cp.nr_blocks_ver):
                for j in range(cp.nr_blocks_hor):
                    cp.blocks[i][j] = IDCT_matrix(cp.blocks[i][j])

    # it is the hardest for programming...
    def reverse_split_block(self):
        pixels = create_nd_array([self.stuffed_height, self.stuffed_width, 3])
        cp_idx = 0
        for cp in self.components.values():
            for i in range(self.nr_MCUs_ver):
                for j in range(self.nr_MCUs_hor):
                    for u in range(cp.vf):
                        for v in range(cp.hf):
                            block = cp.blocks[i*cp.vf+u][j*cp.hf+v]
                            # (v_idx, h_idx) top-left corner of pixel block
                            v_idx = i * self.MCU_height + u * cp.block_height
                            h_idx = j * self.MCU_width + v * cp.block_width
                            step_r, step_c = cp.block_height // 8, cp.block_width // 8
                            for m in range(8):
                                for n in range(8):
                                    val = block[m][n]
                                    for x in range(step_r):
                                        for y in range(step_c):
                                            pixels[v_idx+m*step_r+x][h_idx+n*step_c+y][cp_idx] = val
            cp_idx += 1
        self.data = pixels

    def reverse_color_space_transform(self):
        for i in range(self.stuffed_height):
            for j in range(self.stuffed_width):
                self.data[i][j] = YCbCrtoRGB(self.data[i][j])
    
    def save(self):
        array = np.array(self.data, dtype=np.uint8)
        new_image = Image.fromarray(array, 'YCbCr')
        new_image.crop((0,0,self.width,self.height)).save("new" + self.filename)

SEQ = 'testseq.jpg'
PROG = 'testprog.jpg'
def decode(filename : str = SEQ):
# def decode(filename : str = PROG):
    decoder = Decoder(filename)
    decoder.print_marker()
    decoder.run()
decode()

