'''
Copyright (C) 2016 Thomas Szepe, Patrick Moore

Blender Implementation created by Thomas Szepe and Patrick Moore  with some parts
    based entirely off the  work of Mahesh Venkitachalam and his excellent E-Book
    Python Playground: Geeky Projects for the Curious Programmer
    electronut.in
    ISBN:  9781593276041

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

bl_info = {
    "name":        "Volume Render",
    "description": "OpenGL volume rendering in the 3d View",
    "author":      "Thomas Szepe, Patrick Moore",
    "version":     (0, 0, 1),
    "blender":     (2, 7, 6),
    "location":    "View 3D > Tool Shelf",
    "warning":     "Alpha",  # used for warning icon and text in addons panel
    "wiki_url":    "",
    "tracker_url": "",
    "category":    "3D View"
    }

import sys

if not __path__[0] in sys.path:
    sys.path.append(__path__[0])

# Blender imports
import bpy

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty, CollectionProperty
from bpy.types import Operator

#custom structures from volume render
#from .volreader import loadVolume, loadDCMVolume
#from .vol_shaders import vs, fs
from bgl import *

class vars():
    volrender_ramptext = Buffer(GL_INT, 1, [-1])
    volrender_texture = Buffer(GL_INT, 1, [-1])
    volrender_program = None
    slice_program = None
    draw_handler = None

    rampColors = 256
    step  = 1.0 / (rampColors -1)
    updateProgram = 0

#
# Shader
#
#""" this line is needed for syntax high lighting in Notepad++.

vs = """
varying vec3 pos;

void main()
{
    gl_Position = ftransform();
//  gl_position = gl_ModelViewMatrix * gl_Vertex;
    pos = vec3(gl_Vertex);
}
"""

fs = """
#version 330 compatibility
#extension GL_ARB_explicit_uniform_location : require

layout(location = 20) uniform float azimuth;
layout(location = 21) uniform float elevation;
layout(location = 22) uniform float clipPlaneDepth; //clipping plane variables
layout(location = 23) uniform bool clip;
layout(location = 24) uniform bool dither;
layout(location = 25) uniform float opacityFactor;
layout(location = 26) uniform float lightFactor;
layout(location = 27) uniform sampler3D tex;
layout(location = 28) uniform sampler1D ramp;
layout(location = 29) uniform int shaderType;

varying vec3 pos;

const float maxDist = sqrt(2.0);
const int numSamples = 256;
const float stepSize = maxDist/float(numSamples);

const float numberOfSlices = 96.0;
const float slicesOverX = -10.0;
const float slicesOverY = 10.0;

const float rampColors = 258;

struct Ray 
{
    vec3 Origin;
    vec3 Dir;
};

struct AABB 
{
    vec3 Min;
    vec3 Max;
};

bool IntersectBox(Ray r, AABB aabb, out float t0, out float t1)
{
    vec3 invR = 1.0 / r.Dir;
    vec3 tbot = invR * (aabb.Min-r.Origin);
    vec3 ttop = invR * (aabb.Max-r.Origin);
    vec3 tmin = min(ttop, tbot);
    vec3 tmax = max(ttop, tbot);
    vec2 t = max(tmin.xx, tmin.yz);
    t0 = max(t.x, t.y);
    t = min(tmax.xx, tmax.yz);
    t1 = min(t.x, t.y);
    return t0 <= t1;
}

vec3 p2cart(float azimuth, float elevation)
{
    float pi = 3.14159;
    float x, y, z, k;
    float ele = -elevation * pi / 180.0;
    float azi = (azimuth + 90.0) * pi / 180.0;

    k = cos(ele);
    z = sin(ele);
    y = sin(azi) * k;
    x = cos(azi) * k;

    return vec3( x, z, y );
}

void main()
{
    vec3 clipPlane = p2cart(azimuth, elevation);
    vec3 view = normalize(pos - gl_ModelViewMatrixInverse[3].xyz);

    Ray eye = Ray(gl_ModelViewMatrixInverse[3].xyz, normalize(view));
    AABB aabb = AABB(vec3(-1.0), vec3(+1.0));

    float tnear, tfar;
    IntersectBox(eye, aabb, tnear, tfar);
    if (tnear < 0.0) tnear = 0.0;

    vec3 rayStart = eye.Origin + eye.Dir * tnear;
    vec3 rayStop = eye.Origin + eye.Dir * tfar;
 
    // Transform from object space to texture coordinate space: 
    rayStart = 0.5 * (rayStart + 1.0);
    rayStop = 0.5 * (rayStop + 1.0);

    // Perform the ray marching:
    vec3 pos = rayStart;
    vec3 dir = rayStop - rayStart;
    vec3 step = normalize(dir) * stepSize;
    float travel = distance(rayStop, rayStart);
    
    float len = length(dir);
    dir = normalize(dir);

    if (clip)
    {
        gl_FragColor.a = 0.0;   
        //next, see if clip plane faces viewer
        bool frontface = (dot(dir , clipPlane) > 0.0);
        //next, distance from ray origin to clip plane
        float dis = dot(dir,clipPlane);

        if (dis != 0.0 )
            dis = (-clipPlaneDepth - dot(clipPlane, rayStart.xyz - 0.5)) / dis;

        if ((!frontface) && (dis < 0.0))
            return;

        if ((frontface) && (dis > len))
            return;

        if ((dis > 0.0) && (dis < len)) 
        {
            if (frontface) {
                rayStart = rayStart + dir * dis;
            } else {
                rayStop =  rayStart + dir * dis; 
            }
    
            pos = rayStart;
            step = normalize(rayStop-rayStart) * stepSize;
            travel = distance(rayStop, rayStart);   
        }   
    }

    if (dither) //jaggy artefact dithering
    {
        pos = pos + step * (fract(sin(gl_FragCoord.x * 12.9898 + gl_FragCoord.y * 78.233) * 43758.5453));
    }
    
    /* luminance control raycast example */
    if(shaderType == 1)
    {
        for (int i=0; i < numSamples && travel > 0.0; ++i, pos += step, travel -= stepSize)
        {
        }
    }

    /* brightness control raycast example */
    else if  (shaderType == 2)
    {
        float val_threshold = opacityFactor * stepSize;
        float brightness = lightFactor;

        vec4 frag_color = vec4(0.0, 0.0, 0.0, 0.0);
        vec4 color;

        for (int i=0; i < numSamples && travel > 0.0; ++i, pos += step, travel -= stepSize)
        {
            float density = texture3D(tex, pos).r;

            color.rgb = texture1D(ramp, density).rgb;
            color.a   = density * stepSize * val_threshold * brightness;
            frag_color.rgb = frag_color.rgb * (1.0 - color.a) + color.rgb * color.a;
        }

        if (frag_color == vec4(0.0,0.0,0.0,0.0))
            discard;
        else
            gl_FragColor = vec4(frag_color.rgb,1.0);
    }

    /* density control raycast example */
    else if  (shaderType == 3)
    {
        float val_threshold = opacityFactor * stepSize;
        float brightness = lightFactor;

        vec4 frag_color = vec4(0.0, 0.0, 0.0, 0.0);
        vec4 color;

        for (int i=0; i < numSamples && travel > 0.0; ++i, pos += step, travel -= stepSize)
        {
            float density = texture3D(tex, pos).r;

            color.rgb = texture1D(ramp, val_threshold + density).rgb;
            color.a   = density * stepSize * brightness;
            frag_color.rgb = frag_color.rgb * (1.0 - color.a) + color.rgb * color.a;
        }

        if (frag_color == vec4(0.0,0.0,0.0,0.0))
            discard;
        else
            gl_FragColor = vec4(frag_color.rgb,1.0);
    }

    /* color control raycast example */
    else if  (shaderType == 4)
    {
        float val_threshold = opacityFactor * stepSize;
        float brightness = lightFactor;

        vec4 frag_color = vec4(0.0, 0.0, 0.0, 0.0);
        vec4 color;

        for (int i=0; i < numSamples && travel > 0.0; ++i, pos += step, travel -= stepSize)
        {
            float density = texture3D(tex, pos).r;
            density += val_threshold - 0.5;
            density = density*density*density;

            color.rgb = texture1D(ramp, density).rgb;
            color.a   = density * stepSize * brightness;
            frag_color.rgb = frag_color.rgb * (1.0 - color.a) + color.rgb * color.a;
        }

        if (frag_color == vec4(0.0,0.0,0.0,0.0))
            discard;
        else
            gl_FragColor = vec4(frag_color.rgb,1.0);
    }

    /* Maximum Intensity Projection raycast example */
    else if  (shaderType == 7)
    {
        float val_threshold = opacityFactor / rampColors;
        float max_val = 0.0;

        for (int i=0; i < numSamples && travel > 0.0; ++i, pos += step, travel -= stepSize)
        {
            float density = texture3D(tex, pos).r;
            max_val = max(max_val, density);
        }

        if (max_val >= val_threshold)
            gl_FragColor = vec4(max_val);
            //gl_FragColor = texture1D(ramp, max_val);
        else
            discard;
    }

    else
    {
        vec4 sample = vec4(0.0, 0.0, 0.0, 0.0);
        vec4 value = vec4(0.0, 0.0, 0.0, 0.0);
        vec4 accum = vec4(0.0, 0.0, 0.0, 0.0);
    

        for (int i=0; i < numSamples && travel > 0.0; ++i, pos += step, travel -= stepSize)
        {
            float tf_pos = texture3D(tex, pos).r;   
            value = texture1D(ramp, tf_pos);

            // Process the volume sample
            sample.a = value.a * opacityFactor * stepSize;
            sample.rgb = value.rgb * sample.a * lightFactor;
            accum.rgb += (1.0 - accum.a) * sample.rgb;
            accum.a += sample.a;

            if(accum.a >= 1.0)
                break;
        }
        gl_FragColor = accum;
    }
}
"""


strVS = """
//in vec3 aVert;
//uniform mat4 uMVMatrix;
//uniform mat4 uPMatrix;
uniform float SliceFrac;
uniform int SliceMode;
out vec3 texcoord;

void main()
{
    // X-slice?
    if (SliceMode == 1)
    {
//      texcoord = vec3(SliceFrac, aVert.x, 1.0-aVert.y);
        texcoord = vec3(SliceFrac, gl_Vertex.x*0.5+0.5, gl_Vertex.y*0.5+0.5);
    }
    // Y-slice?
    else if (SliceMode == 2)
    {
//      texcoord = vec3(aVert.x, SliceFrac, 1.0-aVert.y);
        texcoord = vec3(gl_Vertex.x*0.5+0.5, SliceFrac, gl_Vertex.y*0.5+0.5);
    }
    // Z-slice
    else if (SliceMode == 3)
    {
//      texcoord = vec3(aVert.x, 1.0-aVert.y, SliceFrac);
        texcoord = vec3(gl_Vertex.x*0.5+0.5, gl_Vertex.y*0.5+0.5, SliceFrac);
    }

    // calculate transformed vertex
//  gl_Position = uPMatrix * uMVMatrix * vec4(aVert, 1.0); 
//  gl_position = gl_ModelViewMatrix * gl_Vertex;
    gl_Position = ftransform();
}
"""

strFS = """
# version 330 compatibility
in vec3 texcoord;
uniform sampler3D tex;
//out vec4 fragColor;

void main()
{
    // look up color in texture
//  float col = texture3D(tex, texcoord).r;
    vec4 col = texture3D(tex, texcoord);
//  fragColor = col.rrra;
    gl_FragColor = col.rrrr;
}
"""


import os
#import bpy
#from bgl import *
from volume_render.pydicom import read_file

try:
    from PIL import Image, ImageMath
    pil = True
except:
    pil = False
 
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
        #try:
        if pil == True:
            imgData = Image.open(file_path)

            # check if all are of the same size
            if depth is 0:
                width, height = imgData.size[0], imgData.size[1] 
                data = Buffer(GL_BYTE, [len(files), width * height])
                data[depth] = imgData.getdata(0) # 0 = "R" ##imgData.convert("L").getdata()
            else:
                if (width, height) == (imgData.size[0], imgData.size[1]):
                    data[depth] = imgData.getdata(0)
                else:
                    print('mismatch')
                    raise RunTimeError("image size mismatch")
        else:
            imgData = bpy.data.images.load(file_path)

            if depth is 0:
                width, height = imgData.size
                data = Buffer(GL_FLOAT, [len(files), width * height])
                data[depth] = list(imgData.pixels)[::4]
            else:
                if (width, height) == (imgData.size[0], imgData.size[1]):
                    data[depth] = list(imgData.pixels)[::4]
                else:
                    print('mismatch')
                    raise RunTimeError("image size mismatch")

            bpy.data.images.remove(imgData)

        depth += 1
        #except:
            #print('Invalid image: %s' % file_path)

    # load image data into single array
    print('volume data dims: %d %d %d' % (width, height, depth))

    # load data into 3D texture
    glPixelStorei(GL_UNPACK_ALIGNMENT,1)
    glBindTexture(GL_TEXTURE_3D, texture)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_BORDER)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)

    if pil == True:
        glTexImage3D(GL_TEXTURE_3D, 0, GL_RED, width, height, depth, 0, 
                     GL_RED, GL_UNSIGNED_BYTE, data)
    else:
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

        #try:
        # read image
        ds = read_file(file_path)
        img_size = ds.pixel_array.shape
        imgData = ds.pixel_array.flat.copy().astype("f")
        #imgData = ds.PixelData
        maximum = max(imgData)

        # check if all are of the same size
        if depth is 0:
            width, height = img_size[0], img_size[1] 
            data = Buffer(GL_FLOAT, [len(files), width * height])
            data[depth] = imgData/maximum
        else:
            if (width, height) == (img_size[0], img_size[1]):
                #data[depth] = imgData[::2]
                data[depth] = imgData/maximum
            else:
                print('mismatch')
                raise RunTimeError("image size mismatch")
            
        depth += 1
        #except:
            #print('Invalid image: %s' % file_path)

    # load image data into single array
    print('volume data dims: %d %d %d' % (width, height, depth))

    # load data into 3D texture
    glPixelStorei(GL_UNPACK_ALIGNMENT,1)
    glBindTexture(GL_TEXTURE_3D, texture)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_BORDER)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_3D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage3D(GL_TEXTURE_3D, 0,  GL_RED, width, height, depth, 0, 
                 GL_RED,  GL_FLOAT, data)

    return (width, height, depth, float(ds.PixelSpacing[0]), float(ds.PixelSpacing[1]), float(ds.SliceThickness))


def compileShader(source, shaderType):
    shader = glCreateShader(shaderType)
    glShaderSource(shader, source)
    glCompileShader(shader)

    shader_ok = Buffer(GL_INT, 1)
    glGetShaderiv(shader, GL_COMPILE_STATUS, shader_ok)
    
    if not shader_ok[0]:
        infoLen = Buffer(GL_INT, 1)
        glGetShaderiv(shader, GL_INFO_LOG_LENGTH, infoLen)
        infoLog = Buffer(GL_BYTE, infoLen[0])

        if infoLen[0] > 1:
            length = Buffer(GL_INT, 1)
            glGetShaderInfoLog(shader, infoLen[0], length, infoLog)
            print("Shader compile failure (%s):" % (shaderType))  
            print("".join(chr(infoLog[i]) for i in range(length[0])))
            #print (''.join(infoLog))

    return shader


def loadShaders(strVS, strFS):
    # compile vertex shader
    shaderV = compileShader(strVS, GL_VERTEX_SHADER)
    # compiler fragment shader
    shaderF = compileShader(strFS, GL_FRAGMENT_SHADER)
    
    # create the program object
    if vars.slice_program == None:
        vars.slice_program = glCreateProgram()

        # attach shaders
        glAttachShader(vars.slice_program, shaderV)
        glAttachShader(vars.slice_program, shaderF)

        # Link the program
        glLinkProgram(vars.slice_program)
        glDeleteShader(shaderV)
        glDeleteShader(shaderF)
        #glDeleteProgram(program)

        # Check if there were some issues when linking the shader.
        program_ok = Buffer(GL_INT, 1)
        glGetProgramiv(vars.slice_program, GL_LINK_STATUS, program_ok); #missing gl.GL_LINK_STATUS 0x8B82 = 35714

        if not program_ok[0]:
            infoLen = Buffer(GL_INT, 1)
            glGetProgramiv(vars.slice_program, GL_INFO_LOG_LENGTH, infoLen)
            infoLog = Buffer(GL_BYTE, infoLen[0])

            if infoLen[0] > 1:
                length = Buffer(GL_INT, 1)
                glGetProgramInfoLog(vars.slice_program, infoLen[0], length, infoLog);
                print ('Error linking program:')
                #print (''.join(infoLog))
                print (''.join(chr(infoLog[i]) for i in range(length[0])))
    
    return vars.slice_program


def drawSlice(self, context, program, texture, sliceMode, slicePos, x = 0, y = 0, width = 0, height = 0):
    """
    OpenGL code to draw a rectangle in the viewport
    """
    glDisable(GL_DEPTH_TEST)

    # view setup
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glOrtho(-1, 1, -1, 1, -15, 15)
    gluLookAt(0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)

    act_tex = Buffer(GL_INT, 1)
    glGetIntegerv(GL_TEXTURE_2D, act_tex)

    viewport = Buffer(GL_INT, 4)
    glGetIntegerv(GL_VIEWPORT, viewport)

    if width == 0 and height == 0:
        width = viewport[2]
        height = viewport[3]

    glViewport(viewport[0] + x, viewport[1] + y, width, height)
    glScissor(viewport[0] + x, viewport[1] + y, width, height)

    glUseProgram(program)

    # set current slice mode
    glUniform1i(glGetUniformLocation(program, "SliceMode"), sliceMode)
    # set current slice fraction
    glUniform1f(glGetUniformLocation(program, "SliceFrac"), slicePos)
    
    # enable texture
    #glEnable(GL_TEXTURE_3D)
    #glActiveTexture(GL_TEXTURE0 + texture)
    glBindTexture(GL_TEXTURE_3D, texture)
    glUniform1i(glGetUniformLocation(program, "tex"), texture)

    # draw routine
    texco = [(1, 1), (0, 1), (0, 0), (1, 0)]
    verco = [(1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0), (1.0, -1.0)]

    glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

    glColor4f(1.0, 1.0, 1.0, 1.0)

    glBegin(GL_QUADS)
    for i in range(4):
        glTexCoord3f(texco[i][0], texco[i][1], 0.0)
        glVertex2f(verco[i][0], verco[i][1])
    glEnd()

    glBindTexture(GL_TEXTURE_3D, 0)
    #glActiveTexture(GL_TEXTURE0)
    glUseProgram(0)

    # restoring settings
    glBindTexture(GL_TEXTURE_2D, act_tex[0])

    #glDisable(GL_TEXTURE_3D)

    # reset view
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()

    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

    glViewport(viewport[0], viewport[1], viewport[2], viewport[3])
    glScissor(viewport[0], viewport[1], viewport[2], viewport[3])


# Helper functions
def addCube(pixelDimsX, pixelDimsY, pixelDimsZ, pixelSpacingX, pixelSpacingY, pixelSpacingZ):
    #Control settings
    #bpy.context.user_preferences.system.use_mipmaps = False
    bpy.context.scene.game_settings.material_mode = 'GLSL'
    bpy.context.space_data.viewport_shade = 'TEXTURED'

    # Create material
    if not 'VolumeMat' in bpy.data.materials:
        mat = bpy.data.materials.new('VolumeMat')
        mat.use_transparency = True

    mat = bpy.data.materials['VolumeMat']

    # Create new cube
    if not 'VolCube' in bpy.data.objects:
        bpy.ops.mesh.primitive_cube_add(location=(0,3,0))
        cube = bpy.context.object
        cube.name = 'VolCube'

        # Add material to current object
        me = cube.data
        me.materials.append(mat)

    cube = bpy.data.objects['VolCube']
    cube.scale = (pixelDimsX * pixelSpacingX / 100.0, 
                  pixelDimsY * pixelSpacingY / 100.0, 
                  pixelDimsZ * pixelSpacingZ / 100.0)

    addColorRamp()

    return (cube, mat)


def update_colorRamp():
    cr_node = bpy.data.scenes[0].node_tree.nodes['VolColorRamp']
    pixels = Buffer(GL_FLOAT, [vars.rampColors, 4])

    for x in range(0, vars.rampColors):
        pixels[x] = cr_node.color_ramp.evaluate(x * vars.step)

    glActiveTexture(GL_TEXTURE0 + vars.volrender_ramptext[0])
    glBindTexture(GL_TEXTURE_1D, vars.volrender_ramptext[0])
    glTexSubImage1D(GL_TEXTURE_1D, 0, 0, vars.rampColors, GL_RGBA, GL_FLOAT, pixels)
    glActiveTexture(GL_TEXTURE0)
    
    # update Viewport By stteing the time line frame
    #bpy.data.scenes[0].update_tag()
    #bpy.data.scenes[0].update()
    #bpy.context.area.tag_redraw()
    for area in bpy.context.screen.areas:
        if area.type in ['VIEW_3D']:
            area.tag_redraw()

def addColorRamp():
    # Compositor need to be activated first before we can access the nodes.
    bpy.context.scene.use_nodes = True

    tree = bpy.context.scene.node_tree
    links = tree.links

    # Check if there already a color ramp is existing.
    if not "VolColorRamp" in tree.nodes:
        # create Color Ramp node
        ramp = tree.nodes.new("CompositorNodeValToRGB")
        ramp.name = "VolColorRamp"
        ramp.color_ramp.elements[0].color[3] = 0.0

        # create Viewer node
        viewer = tree.nodes.new("CompositorNodeViewer")
        viewer.name = "VolViewer"
        links.new(ramp.outputs[0],viewer.inputs[0])  # image-image

def initColorRamp(program):
    pixels = Buffer(GL_FLOAT, [vars.rampColors, 4])

    if vars.volrender_ramptext[0] == -1:
        glGenTextures(1, vars.volrender_ramptext)
    
    glPixelStorei(GL_UNPACK_ALIGNMENT,1)
    glBindTexture(GL_TEXTURE_1D, vars.volrender_ramptext[0])
    glTexParameterf(GL_TEXTURE_1D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER)
    glTexParameterf(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage1D(GL_TEXTURE_1D, 0, GL_RGBA8, vars.rampColors, 0, GL_RGBA, GL_FLOAT, pixels)
    glBindTexture(GL_TEXTURE_1D, 0)

    glUseProgram(program)
    glUniform1i(28, vars.volrender_ramptext[0])
    glUseProgram(0)

    # update the color ramp one time after init
    update_colorRamp()

    return vars.volrender_ramptext


def replaceShader(tex):
    # This is not a save. It always gets the sahder number from the last added material.
    # To get the correct shader number the object must be the last added object.
    if vars.volrender_program == None:
        for prog in range(32767):
            if glIsProgram(prog) == True:
                vars.volrender_program = prog

        if vars.volrender_program == None:
            print("Shader program number not found")
            return

    print(vars.volrender_program, tex, vars.volrender_ramptext[0])
    #Get the shader generated by setSource()     
    maxCount = 9
    count = Buffer(GL_INT, 1)
    shaders = Buffer(GL_BYTE, maxCount)
    glGetAttachedShaders(vars.volrender_program, maxCount, count, shaders)

    #Get the original vertex and fragment shader
    vertShader = shaders[0]
    fragShader = shaders[4]

    #Load the shaders sources   
    glShaderSource(vertShader, vs)
    glShaderSource(fragShader, fs)
     
    #Compile the shaders         
    glCompileShader(vertShader)
    glCompileShader(fragShader)

    #Check for compile errors
    vertShader_ok = Buffer(GL_INT, 1)
    glGetShaderiv(vertShader, GL_COMPILE_STATUS, vertShader_ok);
    fragShader_ok = Buffer(GL_INT, 1)
    glGetShaderiv(fragShader, GL_COMPILE_STATUS, fragShader_ok);

    if vertShader_ok[0] != True:
        #print error log
        maxLength = 1000
        length = Buffer(GL_INT, 1)
        infoLog = Buffer(GL_BYTE, [maxLength])
        glGetShaderInfoLog(vertShader, maxLength, length, infoLog)
        print("---Vertex shader fault---")                    
        print("".join(chr(infoLog[i]) for i in range(length[0])))
    elif fragShader_ok[0] != True:
        #print error log
        maxLength = 1000
        length = Buffer(GL_INT, 1)
        infoLog = Buffer(GL_BYTE, [maxLength])
        glGetShaderInfoLog(fragShader, maxLength, length, infoLog)
        print("---Fragment shader fault---")                    
        print("".join(chr(infoLog[i]) for i in range(length[0])))
    else:
        #Link the shader program's
        glLinkProgram(vars.volrender_program)

        #Delete the shader objects
        glDeleteShader(vertShader)
        glDeleteShader(fragShader)

        # Bind the volume texture
        glActiveTexture(GL_TEXTURE0 + tex)
        glBindTexture(GL_TEXTURE_3D, tex)
        glUseProgram(vars.volrender_program)
        glUniform1i(27, tex)
        glUseProgram(0)
        glActiveTexture(GL_TEXTURE0)


#
# Property (uniform) update functions
#
def update_azimuth(self, context):
    glUseProgram(vars.volrender_program)
    glUniform1f(20, self.azimuth)
    glUseProgram(0)
 
def update_elevation(self, context):
    glUseProgram(vars.volrender_program)
    glUniform1f(21, self.elevation) 
    glUseProgram(0)
    
def update_clipPlaneDepth(self, context):
    glUseProgram(vars.volrender_program)
    glUniform1f(22, self.clipPlaneDepth) 
    glUseProgram(0)

def update_clip(self, context):
    glUseProgram(vars.volrender_program)
    glUniform1f(23, self.clip)  
    glUseProgram(0)

def update_dither(self, context):
    glUseProgram(vars.volrender_program)
    glUniform1f(24, self.dither) 
    glUseProgram(0)

def update_opacityFactor(self, context):
    glUseProgram(vars.volrender_program)
    glUniform1f(25, self.opacityFactor) 
    glUseProgram(0)

def update_lightFactor(self, context):
    glUseProgram(vars.volrender_program)
    glUniform1f(26, self.lightFactor) 
    glUseProgram(0)

def update_shaderType(self, context):
    glUseProgram(vars.volrender_program)
    glUniform1i(29, int(self.shaderType)) 
    glUseProgram(0)

def update_sliceMode(self, context):
    if vars.slice_program:
        #glUseProgram(vars.slice_program)
        #glUniform1i(glGetUniformLocation(vars.slice_program, "SliceMode"), int(self.sliceMode))
        #glUseProgram(0)
        if vars.draw_handler != None:
            bpy.types.SpaceView3D.draw_handler_remove(vars.draw_handler, "WINDOW")
            vars.draw_handler = None

        if vars.draw_handler == None:
            args = (self, context, vars.slice_program, vars.volrender_texture[0], int(context.object.sliceMode), context.object.slicePos, 0, 0, 200, 200)
            vars.draw_handler = bpy.types.SpaceView3D.draw_handler_add(drawSlice, args, "WINDOW", "POST_PIXEL")


def update_slicePos(self, context):
    if vars.slice_program:
        #glUseProgram(vars.slice_program)
        #glUniform1f(glGetUniformLocation(vars.slice_program, "SliceFrac"), self.slicePos)
        #glUseProgram(0)
        if vars.draw_handler != None:
            bpy.types.SpaceView3D.draw_handler_remove(vars.draw_handler, "WINDOW")
            vars.draw_handler = None

        if vars.draw_handler == None:
            args = (self, context, vars.slice_program, vars.volrender_texture[0], int(context.object.sliceMode), context.object.slicePos, 0, 0, 200, 200)
            vars.draw_handler = bpy.types.SpaceView3D.draw_handler_add(drawSlice, args, "WINDOW", "POST_PIXEL")


def initObjectProperties():
    bpy.types.Object.clip = BoolProperty(
        name = "Clip",
        default = False,
        description = "Use Clip Plane",
        update=update_clip)

    bpy.types.Object.dither = BoolProperty(
        name = "Dither",
        default = False,
        description = "True or False?",
        update=update_dither)

    bpy.types.Object.azimuth = FloatProperty(
        name = "Azimuth", 
        description = "Enter a float",
        default = 90,
        min = -360,
        max = 360,
        update=update_azimuth)

    bpy.types.Object.elevation = FloatProperty(
        name = "Elevation", 
        description = "Enter a float",
        default = 125.0,
        min = -360,
        max = 360,
        update=update_elevation)

    bpy.types.Object.clipPlaneDepth = FloatProperty(
        name = "Clip Plane Depth", 
        description = "Enter a float",
        default = 0.03,
        min = -1,
        max = 1,
        update=update_clipPlaneDepth)

    bpy.types.Object.opacityFactor = FloatProperty(
        name = "Opacity Factor", 
        description = "Enter a float",
        default = 25.0,
        min = 0,
        max = 256,
        update=update_opacityFactor)

    bpy.types.Object.lightFactor = FloatProperty(
        name = "Light Factor", 
        description = "Enter a float",
        default = 1.2,
        min = 0,
        max = 100,
        update = update_lightFactor)

    bpy.types.Object.shaderType = EnumProperty(
       items = [('1', 'Luminance', 'luminance light'),
                ('2', 'Brightness', 'brightness control'),
                ('3', 'Color', 'color control'),
                ('4', 'Density', 'density control'),
                ('5', 'Isosurface', 'isosurface'),
                ('6', 'Transparent Isosurface', 'transparent isosurface'),
                ('7', 'MIP', 'maximum intensity projection')],
       name = "Shader Type",
       default = '7',
       update=update_shaderType)

    bpy.types.Object.sliceMode = EnumProperty(
        items = [('0', '3D', 'Render 3D volume'),
                 ('1', 'X', 'Render 2D X axis slice'),
                 ('2', 'Y', 'Render 2D X axis slice'),
                 ('3', 'Z', 'Render 2D X axis slice')],
        name = "Slice Mode",
        default = '0',
        update=update_sliceMode)

    bpy.types.Object.slicePos = FloatProperty(
        name = "Slice Position", 
        description = "Enter a float",
        default = 0.5,
        min = 0.0,
        max = 1.0,
        update=update_slicePos)


def deleteObjectProperties():
    del bpy.types.Object.clip 
    del bpy.types.Object.dither
    del bpy.types.Object.azimuth
    del bpy.types.Object.elevation
    del bpy.types.Object.clipPlaneDepth
    del bpy.types.Object.opacityFactor
    del bpy.types.Object.lightFactor
    del bpy.types.Object.shaderType
    del bpy.types.Object.sliceMode
    del bpy.types.Object.slicePos


class ImportImageVolume(Operator, ImportHelper):
    """Imports and then clears volume data"""
    bl_idname = "import_test.import_volume_image"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import Image Volume"
    bl_description = "Import image slices"

    # ImportHelper mixin class uses this
    filename_ext = ".tif"
 
    filter_glob = StringProperty(
            default="*.tif;*.jpg;*.png",
            options={'HIDDEN'},
            )

    directory = StringProperty(
            subtype='DIR_PATH',
            )

    files = CollectionProperty(
            name="File Path",
            type=bpy.types.OperatorFileListElement,
            )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    max_slices = IntProperty(
            name="Max Slices",
            description="will only import up to this many slices",
            default= 500,
            )
    
    start_slice = IntProperty(
            name="Start Slice",
            description="will start with this slice",
            default= 0,
            )

    pix_width = FloatProperty(
            name="Pixel Width",
            description="physical width of pixel in Blender Units",
            default= 1.0,
            )
    pix_height = FloatProperty(
            name="Pixel Height",
            description="physical height of pixel in Blender Units",
            default= 1.0,
            )
    slice_thickness = FloatProperty(
            name="Slice Thickness",
            description="physical thickness of image slice in Blender Units",
            default= 1.0,
            )

    def execute(self,context):
        print('loading texture')
 
        if vars.volrender_texture[0] == -1:
            glGenTextures(1, vars.volrender_texture)

        volume = loadVolume(self.directory, self.files, vars.volrender_texture[0])
        
        addCube(float(volume[0]), float(volume[1]), float(volume[2]),
                self.pix_width, self.pix_height, self.slice_thickness)


        #print('added a cube and succsesfully created 3d OpenGL texture from Image Stack')
        #print('the image id as retuned by glGenTextures is %i' % volrender_texture[0])
        #print(self.filename_ext)

        return {'FINISHED'}


class ImportDICOMVoulme(Operator, ImportHelper):
    """Imports volume data stack"""
    bl_idname = "import_test.import_volume_dicom"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import Dicom Volume"
    bl_description = "Import DICOM image slices"
 
    # ImportHelper mixin class uses this
    filename_ext = ".dcm"

    filter_glob = StringProperty(
            default="*.dcm;",
            options={'HIDDEN'},
            )

    directory = StringProperty(
            subtype='DIR_PATH',
            )

    files = CollectionProperty(
            name="File Path",
            type=bpy.types.OperatorFileListElement,
            )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    max_slices = IntProperty(
            name="Max Slices",
            description="will only import up to this many slices",
            default= 500,
            )
    
    start_slice = IntProperty(
            name="Start Slice",
            description="will start with this slice",
            default= 0,
            )

    def execute(self,context):
        if vars.volrender_texture[0] == -1:
            glGenTextures(1, vars.volrender_texture)

        volume = loadDCMVolume(self.directory, self.files, vars.volrender_texture[0])

        #if not 'VolCube' in context.scene.objects:
        addCube(float(volume[0]), float(volume[1]), float(volume[2]),
                volume[3], volume[4], volume[5])

        #print('added a cube and succsesfully created 3d OpenGL texture from DICOM stack')
        #print('the image id as retuned by glGenTextures is %i' % volrender_texture[0])
        
        return {'FINISHED'}


class ShaderReplace(Operator):
    """Attaches volume texture and replaces shader of object"""
    bl_idname = "volume_render.replace_shader"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Replace Shader"
    bl_description = "Render or update the volume"


    def execute(self,context):
        if 'VolCube' in bpy.data.objects:
            replaceShader(vars.volrender_texture[0])
            vars.volrender_ramptext = initColorRamp(vars.volrender_program)
            #print('program ', vars.volrender_program, '  texture ', vars.volrender_texture[0], '  rampText ', vars.volrender_ramptext[0])
            loadShaders(strVS, strFS)

            obj = bpy.data.objects['VolCube']    
            update_azimuth(obj, bpy.context)
            update_elevation(obj, bpy.context)
            update_clipPlaneDepth(obj, bpy.context)
            update_clip(obj, bpy.context)
            update_dither(obj, bpy.context)
            update_opacityFactor(obj, bpy.context)
            update_lightFactor(obj, bpy.context)
            update_shaderType(obj, bpy.context)
            update_sliceMode(obj, bpy.context)
            update_slicePos(obj, bpy.context)

        return {'FINISHED'}

#
#   Menu in UI region
#
class UIPanel(bpy.types.Panel):
    bl_label = "Volume Ray Tracer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object
        draw_handler = None

        layout.operator('import_test.import_volume_image', text="Import Image Volume")
        layout.operator('import_test.import_volume_dicom', text="Import DICOM Voulme")
        layout.operator('volume_render.replace_shader', text="Update Volume")

        if vars.volrender_ramptext[0] != 0 and obj != None and obj.name == 'VolCube':
            #layout.prop(obj, 'shaderType')
            layout.prop(obj, 'sliceMode')
            layout.prop(obj, 'opacityFactor')
            layout.prop(obj, 'lightFactor')
            layout.prop(obj, 'dither')
            layout.prop(obj, 'shaderType')

            if obj.sliceMode == "0":
                layout.prop(obj, 'azimuth')
                layout.prop(obj, 'elevation')
                layout.prop(obj, 'clipPlaneDepth')
                layout.prop(obj, 'clip')

                if vars.draw_handler != None:
                    bpy.types.SpaceView3D.draw_handler_remove(vars.draw_handler, "WINDOW")
                    vars.draw_handler = None
            else:
                layout.prop(obj, 'slicePos')

            cr_node = scene.node_tree.nodes['VolColorRamp']
            layout.template_color_ramp(cr_node, "color_ramp", expand=True)


def scene_update(context):
    if bpy.data.materials.is_updated:
        if bpy.data.materials['VolumeMat'].is_updated:
            vars.updateProgram = 3

        if hasattr(bpy.data.scenes[0].node_tree, 'is_updated'):
            if bpy.data.scenes[0].node_tree.is_updated:
                update_colorRamp()

    # shader update delay 
    if vars.updateProgram == 1:
        replaceShader(vars.volrender_texture[0])
        initColorRamp(vars.volrender_program)

        obj = bpy.data.objects['VolCube']    
        update_azimuth(obj, bpy.context)
        update_elevation(obj, bpy.context)
        update_clipPlaneDepth(obj, bpy.context)
        update_clip(obj, bpy.context)
        update_dither(obj, bpy.context)
        update_opacityFactor(obj, bpy.context)
        update_lightFactor(obj, bpy.context)
        #update_shaderType(obj, bpy.context)

    if vars.updateProgram > 0:
        vars.updateProgram -= 1


def register():
    initObjectProperties()
    
    bpy.utils.register_class(ImportDICOMVoulme)
    bpy.utils.register_class(ImportImageVolume)
    bpy.utils.register_class(ShaderReplace)
    bpy.utils.register_class(UIPanel)

    if not "scene_update" in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.append(scene_update)


def unregister():
    bpy.utils.unregister_class(ImportDICOMVoulme)
    bpy.utils.unregister_class(ImportImageVolume)
    bpy.utils.unregister_class(ShaderReplace)
    bpy.utils.unregister_class(UIPanel)

    if "scene_update" in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.remove(scene_update)

    if vars.draw_handler != None:
        bpy.types.SpaceView3D.draw_handler_remove(vars.draw_handler, "WINDOW")

    deleteObjectProperties()

    if vars.volrender_ramptext[0] != -1:
        glDeleteTextures(1, vars.volrender_ramptext)

    if vars.volrender_texture[0] != -1:
        glDeleteTextures(1, vars.volrender_texture)

    if vars.slice_program != None:
        glDeleteProgram(vars.slice_program)

if __name__ == "__main__":
    register()


    