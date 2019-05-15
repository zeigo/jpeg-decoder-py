
SOI = 0XD8 # start of image
SOF0 = 0XC0 # start of frame, baselineDCT
SOF2 = 0XC2 # start of frame, progressive DCT
DQT = 0XDB # define quantization table
DHT = 0XC4 # define Huffman table
SOS = 0XDA # start of scan
APP0 = 0XE0
APP1 = 0XE1 # application
# APPn = 0XEn
EOI = 0XD9 # end of image
EOB = 0X00 # end of block for sequential, end of band for progressive
COM = 0XFE # comment

marker_dict = {}
marker_dict[SOI] = 'SOI'
marker_dict[SOF0] = 'SOF0'
marker_dict[SOF2] = 'SOF2'
marker_dict[DQT] = 'DQT'
marker_dict[DHT] = 'DHT'

marker_dict[SOS] = 'SOS'
marker_dict[APP0] = 'APP0'
marker_dict[APP1] = 'APP1'
marker_dict[EOI] = 'EOI'
marker_dict[COM] = 'COM'

