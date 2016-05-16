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
#import bmesh

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty
from bpy.types import Operator

#dicom data dealing with
#import pydicom

#custom structures from volume render
from .volreader import loadVolume, loadDCMVolume
#from .raycube import RayCube
#from .raycast import RayCastRender

from .vol_shaders import vs, fs
from bgl import *
#from OpenGL import GL

volrender_program = None
volrender_ramptext = Buffer(GL_INT, [1])
volrender_texture = Buffer(GL_INT, [1])

rampColors = 256
step  = 1.0 / (rampColors - 1.0)
updateProgram = 0

# Helper functions
def addCube():
    #Control settings
    bpy.context.user_preferences.system.use_mipmaps = False
    bpy.context.scene.game_settings.material_mode = 'GLSL'
    bpy.context.space_data.viewport_shade = 'TEXTURED'


    # Create material
    if not 'VolumeMat' in bpy.data.materials:
        mat = bpy.data.materials.new('VolumeMat')
        mat.use_transparency = True
        mat.use_shadeless = True
    else:
        mat = bpy.data.materials['VolumeMat']

    # Create new cube
    bpy.ops.mesh.primitive_cube_add(location=(0,3,0))
    cube = bpy.context.object
    cube.name = 'VolCube'

    # Add material to current object
    me = cube.data
    me.materials.append(mat)

    addColorRamp()

#    I think my version is easier.
#    bme = bmesh.new()
#    bmesh.ops.create_cube(bme, size = 1)
    
#    vol_cube = bpy.data.meshes.new("Vol Cube")
#    cube = bpy.data.objects.new("Vol Cube", vol_cube)
#    bme.to_mesh(vol_cube)
#    context.scene.objects.link(cube)
#    bme.free()
    return (cube, mat)


def update_colorRamp():
    global volrender_ramptext, rampColors, step

    cr_node = bpy.data.scenes[0].node_tree.nodes['ColorRamp']
    pixels = Buffer(GL_FLOAT, [rampColors, 4])

    for x in range(0, rampColors):
       pixels[x] = cr_node.color_ramp.evaluate(x * step)

    glActiveTexture(GL_TEXTURE0 + volrender_ramptext[0])
    glBindTexture(GL_TEXTURE_1D, volrender_ramptext[0])
    glTexSubImage1D(GL_TEXTURE_1D, 0, 0, rampColors, GL_RGBA, GL_FLOAT, pixels)
    glActiveTexture(GL_TEXTURE0)
    
    # update Viewport By stteing the time line frame
#   bpy.data.scenes[0].update_tag()
#   bpy.data.scenes[0].update()
#   bpy.context.area.tag_redraw()
    for area in bpy.context.screen.areas:
        if area.type in ['VIEW_3D']:
            area.tag_redraw()

def addColorRamp():
    # Compositor need to be activated first before we can access the nodes.
    bpy.context.scene.use_nodes = True

    nodes = bpy.context.scene.node_tree.nodes

    # Check if there already a color ramp is existing.
    if not "ColorRamp" in nodes:
        nodes.new("CompositorNodeValToRGB")
        nodes['ColorRamp'].color_ramp.elements[0].color[3] = 0.0

def initColorRamp(program):
    global volrender_ramptext
 
    pixels = Buffer(GL_FLOAT, [rampColors, 4])

    if volrender_ramptext[0] == 0:
        glGenTextures(1, volrender_ramptext)
    
    glPixelStorei(GL_UNPACK_ALIGNMENT,1)
    glBindTexture(GL_TEXTURE_1D, volrender_ramptext[0])
    glTexParameterf(GL_TEXTURE_1D, GL_TEXTURE_WRAP_S, GL_CLAMP)
    glTexParameterf(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameterf(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexImage1D(GL_TEXTURE_1D, 0, GL_RGBA8, rampColors, 0, GL_RGBA, GL_FLOAT, pixels)
    glBindTexture(GL_TEXTURE_1D, 0)

    glUseProgram(program)
    glUniform1i(28, volrender_ramptext[0])
    glUseProgram(0)

    # update the color ramp one time after init
    update_colorRamp()

    return volrender_ramptext


def replaceShader(tex):
    program = None

    # get shader program number depending on material index.
    # Also not a save version. It is really tricky to get the right shade number. 
    # After startup the program number depends on the material index increment by 3.
    # If a new object is added (even without material) the shader number will be moved by 3.
    # If an object will be deleted the number will not decrease until restart.
    #for i, mat in enumerate(bpy.data.materials):
    #    if mat.name == "VolumeMat":
    #        program = (i + 1) * 3
    #        break
  
    # This is not a save. It always gets the last sahder number.
    # The object must be the last added object.
    for prog in range(32767):
        if glIsProgram(prog) == True:
            program = prog

    if program == None:
        print("Shader program number not found")
        return program

    #Get the shader generated by setSource()     
    maxCount = 9
    count = Buffer(GL_INT, 1)
    shaders = Buffer(GL_BYTE, [maxCount])
    glGetAttachedShaders(program, maxCount, count, shaders)

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
        glLinkProgram(program)

        #Delete the shader objects
        glDeleteShader(vertShader)
        glDeleteShader(fragShader)

        # Bind the volume texture
        glActiveTexture(GL_TEXTURE0 + tex)
        glBindTexture(GL_TEXTURE_3D, tex)
        glUseProgram(program)
        glUniform1i(27, tex)
        glUseProgram(0)
        glActiveTexture(GL_TEXTURE0)

    return program


#
# Property (uniform) update functions
#
def update_azimuth(self, context):
    #global volrender_program
    glUseProgram(volrender_program)
    glUniform1f(20, self.azimuth)
    glUseProgram(0)
 
def update_elevation(self, context):
    #global volrender_program
    glUseProgram(volrender_program)
    glUniform1f(21, self.elevation) 
    glUseProgram(0)
    
def update_clipPlaneDepth(self, context):
    #global volrender_program
    glUseProgram(volrender_program)
    glUniform1f(22, self.clipPlaneDepth) 
    glUseProgram(0)

def update_clip(self, context):
    #global volrender_program
    glUseProgram(volrender_program)
    glUniform1f(23, self.clip)  
    glUseProgram(0)

def update_dither(self, context):
    #global volrender_program
    glUseProgram(volrender_program)
    glUniform1f(24, self.dither) 
    glUseProgram(0)

def update_opacityFactor(self, context):
    #global volrender_program
    glUseProgram(volrender_program)
    glUniform1f(25, self.opacityFactor) 
    glUseProgram(0)

def update_lightFactor(self, context):
    #global volrender_program
    glUseProgram(volrender_program)
    glUniform1f(26, self.lightFactor) 
    glUseProgram(0)

  
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
        default = 10,
        min = 0,
        max = 100,
        update = update_lightFactor)


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
        global volrender_texture
       
        print('loading texture')
 
        if volrender_texture[0] == 0:
            glGenTextures(1, volrender_texture)

        self.volume = loadVolume(self.filepath, volrender_texture[0])
        
        (width, height, depth) = self.volume

        if not 'VolCube' in context.scene.objects:
            addCube()

        print('added a cube and succsesfully created 3d OpenGL texture from Image Stack')
        print('the image id as retuned by glGenTextures is %i' % volrender_texture[0])
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
        global volrender_texture

        if volrender_texture[0] == 0:
            glGenTextures(1, volrender_texture)

        self.volume = loadDCMVolume(self.filepath, volrender_texture[0])
        
        (width, height, depth) = self.volume

        if not 'VolCube' in context.scene.objects:
            addCube()

        print('added a cube and succsesfully created 3d OpenGL texture from DICOM stack')
        print('the image id as retuned by glGenTextures is %i' % volrender_texture[0])
        
        return {'FINISHED'}


class ShaderReplace(Operator):
    """Attaches volume texture and replaces shader of object"""
    bl_idname = "volume_render.replace_shader"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Replace Shader"
    bl_description = "Render or update the volume"

    def execute(self,context):
        global volrender_program
        global volrender_texture
        global volrender_ramptext

        if 'VolCube' in bpy.data.objects:
            volrender_program = replaceShader(volrender_texture[0])
            volrender_ramptext = initColorRamp(volrender_program)
            #print('program ', volrender_program, '  texture ', volrender_texture[0], '  rampText ', volrender_ramptext[0])

            obj = context.object      
            update_azimuth(obj, bpy.context)
            update_elevation(obj, bpy.context)
            update_clipPlaneDepth(obj, bpy.context)
            update_clip(obj, bpy.context)
            update_dither(obj, bpy.context)
            update_opacityFactor(obj, bpy.context)
            update_lightFactor(obj, bpy.context)

        return {'FINISHED'}

#
#   Menu in UI region
#
class UIPanel(bpy.types.Panel):
    bl_label = "Volume Ray Tracer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    #will comment these out because can't get to obj
    #data at registration time
    #obj = bpy.context.object
    #update_azimuth(obj, bpy.context)
    #update_elevation(obj, bpy.context)
    #update_clipPlaneDepth(obj, bpy.context)
    #update_clip(obj, bpy.context)
    #update_dither(obj, bpy.context)
    #update_opacityFactor(obj, bpy.context)
    #update_lightFactor(obj, bpy.context)

    def draw(self, context):
        global volrender_ramptext
        
        layout = self.layout
        scene = context.scene
        obj = context.object

        layout.operator('import_test.import_volume_image', text="Import Image Volume")
        layout.operator('import_test.import_volume_dicom', text="Import DICOM Voulme")
        layout.operator('volume_render.replace_shader', text="Update Volume")

        if volrender_ramptext[0] != 0 and obj != None and obj.name == 'VolCube':
            layout.prop(obj, 'azimuth')
            layout.prop(obj, 'elevation')
            layout.prop(obj, 'clipPlaneDepth')
            layout.prop(obj, 'opacityFactor')
            layout.prop(obj, 'lightFactor')
            layout.prop(obj, 'clip')
            layout.prop(obj, 'dither')

            cr_node = scene.node_tree.nodes['ColorRamp']
            layout.template_color_ramp(cr_node, "color_ramp", expand=True)


def scene_update(context):
    global updateProgram
    global updateProgram

    if bpy.data.materials.is_updated:
        #if bpy.data.materials['VolumeMat'].is_updated:
        #    print("update2")
        #    updateProgram = 3

        if hasattr(bpy.data.scenes[0].node_tree, 'is_updated'):
            if bpy.data.scenes[0].node_tree.is_updated:
                #print("update")
                update_colorRamp()

    # shader update delay 
    if updateProgram == 1:
        print("update3")
        replaceShader(volrender_texture[0])

        for area in bpy.context.screen.areas:
            if area.type in ['VIEW_3D']:
                area.tag_redraw()

    if updateProgram > 0:
        updateProgram -= 1


def register():
    initObjectProperties()
    
    bpy.utils.register_class(ImportDICOMVoulme)
    bpy.utils.register_class(ImportImageVolume)
    bpy.utils.register_class(ShaderReplace)
    bpy.utils.register_class(UIPanel)
    if "scene_update" in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.remove(scene_update)
    bpy.app.handlers.scene_update_post.append(scene_update)


def unregister():
    bpy.utils.unregister_class(ImportDICOMVoulme)
    bpy.utils.unregister_class(ImportImageVolume)
    bpy.utils.unregister_class(ShaderReplace)
    bpy.utils.unregister_class(UIPanel)
    if "scene_update" in bpy.app.handlers.scene_update_post:
        bpy.app.handlers.scene_update_post.remove(scene_update)

    del bpy.types.Object.clip 
    del bpy.types.Object.dither
    del bpy.types.Object.azimuth
    del bpy.types.Object.elevation
    del bpy.types.Object.clipPlaneDepth
    del bpy.types.Object.opacityFactor
    del bpy.types.Object.lightFactor
    
    global volrender_texture 
    global volrender_ramptext 

    if volrender_ramptext != -1:
        glDeleteTextures (1, volrender_ramptext)

    if volrender_texture != -1:
        glDeleteTextures (1, volrender_texture)

if __name__ == "__main__":
    register()
