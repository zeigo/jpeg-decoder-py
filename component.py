class Component:
    def __init__(self, hf, vf, qt, identifier):
        self.id = identifier
        self.hf = hf
        self.vf = vf
        self.qt = qt

        # the size of corresponding pixel block, block_height = 8 * (max_vf / vf)
        self.block_height = 0
        self.block_width = 0
        # number of blocks per row and number of rows of blocks, 
        # nr_blocks_ver = ceil(image_height / block_height)
        # they are used in non-interleaved scan where a MCU contains just one block,
        # so they are equal to number of MCU rows and number of MCU columns respectively
        self.nr_blocks_ver = 0 
        self.nr_blocks_hor = 0 
        # a 3d array to store coefficients, row * col * 64
        self.blocks = None 
        
        # may change when scanning
        self.prev_DC = 0
        self.ACht = None 
        self.DCht = None