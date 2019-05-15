import math

def create_nd_array(shape):
    """create n-dimensional array filled with 0"""
    if len(shape) == 0: return 0
    res = []
    for _ in range(shape[0]):
        res.append(create_nd_array(shape[1:]))
    return res

# CCIR Recommendation 601
def RGBtoYCbCr(R, G, B):
    Y = 0.299 * R + 0.587*G + 0.114*B
    Cb = -0.1687*R - 0.3313*G + 0.5*B + 128
    Cr = 0.5*R - 0.4187*G - 0.0813*B + 128
    return Y, Cb, Cr

def YCbCrtoRGB(li):
    Y, Cb, Cr = li
    R = Y + 1.402 *(Cr-128)
    G = Y - 0.34414*(Cb-128) - 0.71414*(Cr-128)
    B = Y + 1.772*(Cb-128)
    return [int(R), int(G), int(B)]

def alpha(x):
    return 1/2 if x != 0 else 1/math.sqrt(8)

def FDCT_matrix(f):
    F = create_nd_array([8,8])
    for u in range(8):
        for v in range(8):
            F[u][v] = FDCT(f, u, v)
    return F

def FDCT(f, u, v):
    """f --FDCT-> F(u,v)"""
    res = 0
    for x in range(8):
        for y in range(8):
            res += f[x][y] * math.cos(math.pi*u*(2*x+1)/16) * math.cos(math.pi*v*(2*y+1)/16)
    return res * alpha(u) * alpha(v)

def IDCT_matrix(F):
    f = create_nd_array([8,8])
    for x in range(8):
        for y in range(8):
            f[x][y] = clip(round(IDCT(F, x, y))+128)
    return f

def clip(x):
    if x > 255: return 255
    if x < 0: return 0
    return x

def IDCT(F, x, y):
    """F --IDCT-> f(x, y)"""
    res = 0
    for u in range(8):
        for v in range(8):
            res += alpha(u) * alpha(v) * F[u][v] * math.cos(math.pi*u*(2*x+1)/16) * math.cos(math.pi*v*(2*y+1)/16)
    return res

def bits_to_coefficient(bits):
    if bits[0] == 1: # positive
        return bits_to_number(bits)
    flip = [1-x for x in bits]
    return -bits_to_number(flip)

def coefficients_to_bits(val):
    if val == 0:
        return []
    elif val > 0:
        return number_to_bits(val)
    else:
        return [1-bit for bit in number_to_bits(-val)]


def number_to_bits(number):
    return [ 1 if digit == '1' else 0 for digit in bin(number)[2:]]

def bits_to_number(bits):
    """convert the binary representation to the original positive number"""
    res = 0
    for x in bits:
        res = res * 2 + x
    return res

def construct_zigzag():
    zigzag = []
    bl2tr = True # bottom-left to top-right
    for x in range(8): # first (0,0) last(7,7)   
        if bl2tr:
            for i in range(x+1):
                zigzag.append([x-i, i])
        else:
            for i in range(x+1):
                zigzag.append([i, x-i])
        bl2tr = not bl2tr
    for x in range(8, 15):
        if bl2tr:
            for i in range(x-i, 8):
                zigzag.append([x-i, i])
        else:
            for i in range(x-i, 8):
                zigzag.append([i, x-i])
        bl2tr = not bl2tr
    return zigzag

# zigzag[k] -> [i,j], k is the index in zigzag order, i, j are the indexs in the matrix
zigzag = construct_zigzag()

def zigzag2matrix(li):
    """convert a list of size 64 in zigzag order to a 8 by 8 matrix"""
    matrix = create_nd_array([8,8])
    for i, val in enumerate(li):
        x, y = zigzag[i]
        matrix[x][y] = val
    return matrix
