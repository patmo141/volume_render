'''
Copyright (C) 2016 Patrick R. Moore

Blender Implementation created by Patrick Moore based entirely off the
    generous work of Mahesh Venkitachalam and his excellent E-Book
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
    "author":      "Patrick Moore",
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

