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

def draw_callback(self,context):
    print('drawing vol box')
    self.vol_box.draw()
    return

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
    

def register():
    bpy.utils.register_class(ImportDICOMVoulme)
    bpy.utils.register_class(ImportImageVolume)


def unregister():
    bpy.utils.unregister_class(ImportDICOMVoulme)
    bpy.utils.unregister_class(ImportImageVolume)



