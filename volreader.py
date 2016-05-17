"""
volreader.py
Author: Mahesh Venkitachalam, Patrick Moore
Utilities for reading 3D volumetric data as a 3D OpenGL texture.

function modified for dicom support
"""

import os
import bpy
from bgl import *
#from PIL import Image
from volume_render.pydicom import read_file
 
def loadVolume(dirName, filelist, texture):
    """read volume from directory as a 3D texture"""
    # list images in directory
    #dirname = os.path.dirname(dirName)

    if filelist[0].name == "":
        files = sorted(os.listdir(dirName))
    else:
        files = filelist

    print('loading mages from: %s' % dirName)

    depth = 0
    width, height = 0, 0
    for file in files:
        if hasattr(file, 'name'):
            file_path = os.path.abspath(os.path.join(dirName, file.name))
        else:
            file_path = os.path.abspath(os.path.join(dirName, file))
#        try:
        # read image
        #imgData = Image.open(file_path)
        imgData = bpy.data.images.load(file_path)

         # check if all are of the same size
        if depth is 0:
            width, height = imgData.size
            #width, height = img.size[0], img.size[1] 
            data = Buffer(GL_FLOAT, [len(files), width * height])
            #data[depth] = img.getdata()
            data[depth] = list(imgData.pixels)[::4]
        else:
            if (width, height) == (imgData.size[0], imgData.size[1]):
                #data[depth] = img.getdata()
                data[depth] = list(imgData.pixels)[::4]
            else:
                print('mismatch')
                raise RunTimeError("image size mismatch")
        depth += 1

        bpy.data.images.remove(imgData)

#        except:
            # skip
            #print('Invalid image: %s' % file_path)

    # load image data into single array
    print('volume data dims: %d %d %d' % (width, height, depth))

    # load data into 3D texture
    glPixelStorei(GL_UNPACK_ALIGNMENT,1)
    glBindTexture(GL_TEXTURE_3D, texture)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage3D(GL_TEXTURE_3D, 0, GL_RED, width, height, depth, 0, 
                 GL_RED, GL_FLOAT, data)

    #return texture
    return (width, height, depth)



def loadDCMVolume(dirName, filelist, texture):
    """read dcm volume from directory as a 3D texture"""
    # list images in directory
    if filelist[0].name == "":
        files = sorted(os.listdir(dirName))
    else:
        files = filelist

    print('loading mages from: %s' % dirName)

    depth = 0
    width, height = 0, 0
    for file in files:
        #skip non dcm files
        if hasattr(file, 'name'):
            if not file.name.endswith(".dcm"): 
                print('skipping junk file: ' + file)
                continue
            file_path = os.path.abspath(os.path.join(dirName, file.name))
        else:
            if not file.endswith(".dcm"): 
                print('skipping junk file: ' + file)
                continue
            file_path = os.path.abspath(os.path.join(dirName, file))

 #        try:
        # read image
        ds = read_file(file_path)
        img_size = ds.pixel_array.shape
        imgData = ds.pixel_array.flat.copy().astype("f")
        #imgData = ds.PixelData

        # check if all are of the same size
        if depth is 0:
            width, height = img_size[0], img_size[1] 
            data = Buffer(GL_FLOAT, [len(files), width * height])
            data[depth] = imgData/max(imgData)
        else:
            if (width, height) == (img_size[0], img_size[1]):
                #data[depth] = imgData[::2]
                data[depth] = imgData/max(imgData)
            else:
                print('mismatch')
                raise RunTimeError("image size mismatch")
            
        depth += 1
#        except:
#            print('Invalid image: %s' % file_path)

    # load image data into single array
    print('volume data dims: %d %d %d' % (width, height, depth))

    # load data into 3D texture
    glPixelStorei(GL_UNPACK_ALIGNMENT,1)
    glBindTexture(GL_TEXTURE_3D, texture)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage3D(GL_TEXTURE_3D, 0,  GL_RED, width, height, depth, 0, 
                 GL_RED,  GL_FLOAT, data)

    return (width, height, depth, float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1]), float(ds.SliceThickness))

# load texture
def loadTexture(filename):
    img = Image.open(filename)
    #img_data = np.array(list(img.getdata()), 'B')
    #texture = GL.glGenTextures(1)
    width, height = img.size[0], img.size[1] 
    img_data = Buffer(GL_BYTE, [width * height * 4])
    texture = Buffer(GL_INT, [1])
    glGenTextures(1, texture)
    glPixelStorei(GL_UNPACK_ALIGNMENT,1)
    glBindTexture(GL_TEXTURE_2D, texture)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.size[0], img.size[1], 
                 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
    
    return texture