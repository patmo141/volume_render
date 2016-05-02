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

# Blender imports
import bpy
import bmesh

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty
from bpy.types import Operator


#dicom data dealing with
import pydicom

#custom structures from volume render
from .volreader import loadVolume, loadDCMVolume
#from .raycube import RayCube
from .raycast import RayCastRender

from .vol_shaders import vs, fs
from bgl import *

class ImportImageVolume(Operator, ImportHelper):
    """Imports and then clears volume data"""
    bl_idname = "import_test.import_volume_image"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import Image Volume"

    # ImportHelper mixin class uses this
    filename_ext = ".tif"

    filter_glob = StringProperty(
            default="*.tif; *.jpg; *.png",
            options={'HIDDEN'},
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
            default= .1,
            )
    pix_height = FloatProperty(
            name="Pixel Height",
            description="physical height of pixel in Blender Units",
            default= .1,
            )
    slice_thickness = FloatProperty(
            name="Slice Thickness",
            description="physical thickness of image slice in Blender Units",
            default= .1,
            )

    def execute(self,context):
        
        print('loading texture')
        self.volume = loadVolume(self.filepath)
        
        (texture, width, height, depth) = self.volume
        
        bme = bmesh.new()
        bmesh.ops.create_cube(bme, size = 1)
        
        vol_cube = bpy.data.meshes.new("Vol Cube")
        cube = bpy.data.objects.new("Vol Cube", vol_cube)
        bme.to_mesh(vol_cube)
        context.scene.objects.link(cube)
        bme.free()
        
        
        print('added a cube and succsesfully created 3d OpenGL texture from Image Stack')
        print('the image id as retuned by glGenTextures is %i' % texture)
        #print(self.filename_ext)

        return {'FINISHED'}

class ImportDICOMVoulme(Operator, ImportHelper):
    """Imports volume data stack"""
    bl_idname = "import_test.import_volume_dicom"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import Dicom Volume"

    # ImportHelper mixin class uses this
    filename_ext = ".dcm"

    filter_glob = StringProperty(
            default="*.dcm;",
            options={'HIDDEN'},
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
        
        self.volume = loadDCMVolume(self.filepath)
        
        (texture, width, height, depth) = self.volume
        
        bme = bmesh.new()
        bmesh.ops.create_cube(bme, size = 1)
        
        vol_cube = bpy.data.meshes.new("Vol Cube")
        cube = bpy.data.objects.new("Vol Cube", vol_cube)
        bme.to_mesh(vol_cube)
        context.scene.objects.link(cube)
        bme.free()
        
        print('added a cube and succsesfully created 3d OpenGL texture from DICOM stack')
        print('the image id as retuned by glGenTextures is %i' % texture)
        
        return {'FINISHED'}

#perhaps, we do not need globals
global volrender_progam 
volrender_program = None
global volrender_ramptext 
volrender_ramptext = None

rampColors = 256
step  = 1.0 / (rampColors - 1.0)

def initColorRamp(program):
    # Compositor need to be activated first before we can access the nodes.
    bpy.context.scene.use_nodes = True

    scene = bpy.context.scene
    nodes = scene.node_tree.nodes

    # Check if there already a color ramp is existing.
    if not "ColorRamp" in nodes:
        nodes.new("CompositorNodeValToRGB")

    # Just ad a black image to the shader. the correct colors wil be set by the
    # update function. So the commented commands are not necessary.
    pixels = Buffer(GL_FLOAT, [rampColors, 4])

#   for x in range(0, rampColors):
#       pixels[x] = nodes['ColorRamp'].color_ramp.evaluate(x * step)

    rampTex = Buffer(GL_INT, [1])
    glGenTextures(1, rampTex)
    glPixelStorei(GL_UNPACK_ALIGNMENT,1)
    glBindTexture(GL_TEXTURE_1D, rampTex[0])
    glTexParameterf(GL_TEXTURE_1D, GL_TEXTURE_WRAP_S, GL_CLAMP)
    glTexParameterf(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage1D(GL_TEXTURE_1D, 0, GL_RGBA8, rampColors, 0, GL_RGBA, GL_FLOAT, pixels)
    glBindTexture(GL_TEXTURE_1D, 0)

#   bpy.context.object.colorRamp = pixels[1][0]

#   glActiveTexture(GL_TEXTURE0 + rampTex[0])
#   glBindTexture(GL_TEXTURE_1D, rampTex[0])
    glUseProgram(program)
    glUniform1i(28, rampTex[0])
    glUseProgram(0)
#   glActiveTexture(GL_TEXTURE0)

    return (rampTex[0])

def update_colorRamp(ramp, rampTex, rampColors, step):
#   global oldColor

#   if oldColor != ramp.color_ramp.evaluate(step):
    pixels = Buffer(GL_FLOAT, [rampColors, 4])

    for x in range(0, rampColors):
       pixels[x] = ramp.color_ramp.evaluate(x * step)

    glActiveTexture(GL_TEXTURE0 + rampTex)
    glBindTexture(GL_TEXTURE_1D, rampTex)
    glTexSubImage1D(GL_TEXTURE_1D, 0, 0, rampColors, GL_RGBA, GL_FLOAT, pixels)
    glActiveTexture(GL_TEXTURE0)
    
    # update Viewport By stteing the time line frame
    bpy.context.scene.frame_set(0)

#       oldColor = (pixels[1][0], pixels[1][1], pixels[1][2], pixels[1][3])

def replaceShader():
    program = -1

    for prog in range(32767):
        if glIsProgram(prog) == True:
            program = prog 

    #Get the sahder generated by setSource()     
    maxCount = 9
    count = Buffer(GL_INT, 1)
    shaders = Buffer(GL_BYTE, [maxCount])
    glGetAttachedShaders(program, maxCount, count, shaders)

    #Get the original vertex and fragment sahder
    vertShader = shaders[0]
    fragShader = shaders[4]

    #Load the shaders sources   
    glShaderSource(vertShader, vs)
    glShaderSource(fragShader, fs)
     
    #Compile the shaders         
    glCompileShader(vertShader)
    glCompileShader(fragShader)

    #Check for compile errors
    shader_ok = Buffer(GL_INT, 1)
    glGetShaderiv(fragShader, GL_COMPILE_STATUS, shader_ok);

    if shader_ok[0] == True:
        #Link the sahder program's
        glLinkProgram(program)

        #Delete the shader objects
        glDeleteShader(vertShader)
        glDeleteShader(fragShader)
    else:
        #print error log
        maxLength = 1000
        length = Buffer(GL_INT, 1)
        infoLog = Buffer(GL_BYTE, [maxLength])
        glGetShaderInfoLog(fragShader, maxLength, length, infoLog)
        print("---Fragment Shader fault---")                    
        print("".join(chr(infoLog[i]) for i in range(length[0])))

    return program
   
class ShaderReplace(Operator):
    """Attaches volume texture and replaces shader of object"""
    bl_idname = "volume_render.replace_shader"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Replace Shader"

    def execute(self,context):
        
        ########  TEMPORARY GRABS CUBE WITH EXISTING TEXTURE    ####
        ########  Will be replaced with code to generate a cube ####
        #and attach texture/shader program
        
        if not context.object:
            self.report({'ERROR'},"An object must be selected")
            
        if not context.object.name == 'Cube':
            self.report({'ERROR'},"Object must be a cube")
        
        if not len(context.object.material_slots) == 1:
            self.report({'ERROR'},"Cube should only have 1 material slot")
        
        #mat = context.object.material_slots[0].material
        
        ########  END TEMPORARY CODE SEGMENT ####
        
        #identify the cube as a volume object
        is_volume = context.object.get('is_volume', False)
        if not is_volume:
            context.object.is_volume = True
        
        #Control settings
        if context.user_preferences.system.use_mipmaps:
            context.user_preferences.system.use_mipmaps = False
        
        
        
  
        global volrender_program 
        volrender_program = replaceShader()
        print('volrender program is')
        print(volrender_program)
        
        global volrender_ramptext 
        volrender_ramptext = initColorRamp(volrender_program)
        
        #will comment these out because can't get to obj
        #data at registration time
        update_azimuth(context.object, bpy.context)
        update_elevation(context.object, bpy.context)
        update_clipPlaneDepth(context.object, bpy.context)
        update_clip(context.object, bpy.context)
        update_dither(context.object, bpy.context)
        update_opacityFactor(context.object, bpy.context)
        update_lightFactor(context.object, bpy.context)
        
        return {'FINISHED'}

#
# Property (uniform) update functions
#

def update_azimuth(self, context):
    #global volrender_program
    print(volrender_program)
    glUseProgram(volrender_program)
    glUniform1f(20, self.azimuth)
    glUseProgram(0)
 
def update_elevation(self, context):
    #global volrender_program
    print(volrender_program)
    glUseProgram(volrender_program)
    glUniform1f(21, self.elevation) 
    glUseProgram(0)
    
def update_clipPlaneDepth(self, context):
    #global volrender_program
    print(volrender_program)
    glUseProgram(volrender_program)
    glUniform1f(22, self.clipPlaneDepth) 
    glUseProgram(0)

def update_clip(self, context):
    #global volrender_program
    print(volrender_program)
    glUseProgram(volrender_program)
    glUniform1f(23, self.clip)  
    glUseProgram(0)

def update_dither(self, context):
    #global volrender_program
    print(volrender_program)
    glUseProgram(volrender_program)
    glUniform1f(24, self.dither) 
    glUseProgram(0)

def update_opacityFactor(self, context):
    #global volrender_program
    print(volrender_program)
    glUseProgram(volrender_program)
    glUniform1f(25, self.opacityFactor) 
    glUseProgram(0)

def update_lightFactor(self, context):
    #global volrender_program
    print(volrender_program)
    glUseProgram(volrender_program)
    glUniform1f(26, self.lightFactor) 
    glUseProgram(0)
    
def initObjectProperties():
    
    bpy.types.Object.is_volume = BoolProperty(
        name = "Is Volume",
        default = False,
        description = "Object container for volume?")

    
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
        max = 10,
        update = update_lightFactor)


#
#   Menu in UI region
#
class UIPanel(bpy.types.Panel):
    bl_label = "Volume Ray Tracer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    #will comment these out because can't get to obj
    #data at registration time
    #update_azimuth(obj, bpy.context)
    #update_elevation(obj, bpy.context)
    #update_clipPlaneDepth(obj, bpy.context)
    #update_clip(obj, bpy.context)
    #update_dither(obj, bpy.context)
    #update_opacityFactor(obj, bpy.context)
    #update_lightFactor(obj, bpy.context)

    def draw(self, context):
        global volrender_ramptext
        
        rampColors = 256
        step  = 1.0 / (rampColors - 1.0)

        layout = self.layout
        scene = bpy.context.scene
        
        if context.object == None: return
        obj = context.object
        
        #use get to try and access custom property
        #if it's not there...go on happily!
        is_volume = obj.get('is_volume', False)
        if not is_volume: 
            row = layout.row()
            row.label(text = "Not a Volume Data Object")
            return

        layout.prop(obj, 'azimuth')
        layout.prop(obj, 'elevation')
        layout.prop(obj, 'clipPlaneDepth')
        layout.prop(obj, 'opacityFactor')
        layout.prop(obj, 'lightFactor')
        layout.prop(obj, 'clip')
        layout.prop(obj, 'dither')

        cr_node = scene.node_tree.nodes['ColorRamp']
        layout.template_color_ramp(cr_node, "color_ramp", expand=True)

        update_colorRamp(cr_node, volrender_ramptext, rampColors, step)

def register():
    initObjectProperties()
    
    bpy.utils.register_class(ImportDICOMVoulme)
    bpy.utils.register_class(ImportImageVolume)
    bpy.utils.register_class(ShaderReplace)
    bpy.utils.register_class(UIPanel)

def unregister():
    bpy.utils.unregister_class(ImportDICOMVoulme)
    bpy.utils.unregister_class(ImportImageVolume)
    bpy.utils.unregister_class(ShaderReplace)
    bpy.utils.unregister_class(UIPanel)
     
    global volrender_ramptext 

    if volrender_ramptext != None:
        glDeleteTextures (1, [volrender_ramptext])

