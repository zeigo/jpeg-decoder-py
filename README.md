It is a JPEG decoder supporting sequential and progressive DCT-based encoding. Restart is not supported. I write it to test that I have understood how JPEG works.

If you are interested in how JPEG works or are trying to write a JPEG codec, I hope the code and wiki in this repository can help you.

To use it, open the directory `jpeg-py`, and run `decoder.py`. The detail of the input image is printed, the input image is decoded to a matrix of [Y, Cb, Cr], and a new image is generated using this matrix. You can add you own jpg image to the directory, and change the argument of function `decode()`. 

The IDCT is not optimized, so it's time consuming. For the images I provide to test, it may cost 30s, be patient please :)