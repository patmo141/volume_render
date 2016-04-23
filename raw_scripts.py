#----------------------------------------------------------
# File .py
#----------------------------------------------------------
import bpy
from bpy.props import *
from bgl import * #Iam lazy I don't want to type always bgl.gl....

#
# Shader
#
vs = """
varying vec3 pos;

void main()
{
    gl_Position = ftransform();
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
uniform sampler2D tex;

varying vec3 pos;

const float maxDist = sqrt(2.0);
const int numSamples = 256;
const float stepSize = maxDist/float(numSamples);

const float numberOfSlices = 96.0;
const float slicesOverX = -10.0;
const float slicesOverY = 10.0;

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

    k = cos( ele );
    z = sin( ele );
    y = sin( azi ) * k;
    x = cos( azi ) * k;

    return vec3( x, z, y );
}

float tex3D(sampler2D texture, vec3 volpos)
{
    float s1,s2;
    float dx1,dy1;
    float dx2,dy2;

    vec2 texpos1,texpos2;

    s1 = floor(volpos.z*numberOfSlices);
    s2 = s1+1.0;

    dx1 = fract(s1/slicesOverX);
    dy1 = floor(s1/slicesOverY)/slicesOverY;

    dx2 = fract(s2/slicesOverX);
    dy2 = floor(s2/slicesOverY)/slicesOverY;
    
    texpos1.x = dx1+(volpos.x/slicesOverX);
    texpos1.y = dy1+(volpos.y/slicesOverY);

    texpos2.x = dx2+(volpos.x/slicesOverX);
    texpos2.y = dy2+(volpos.y/slicesOverY);

    return mix( texture2D(texture,texpos1).x, texture2D(texture,texpos2).x, (volpos.z*numberOfSlices)-s1);
}

void main()
{
    vec3 clipPlane = p2cart(azimuth, elevation);
    vec3 view = normalize(pos - gl_ModelViewMatrixInverse[3].xyz);
    Ray eye = Ray( gl_ModelViewMatrixInverse[3].xyz, normalize(view) );

    AABB aabb = AABB(vec3(-1.0), vec3(+1.0));

    float tnear, tfar;
    IntersectBox(eye, aabb, tnear, tfar);
    if (tnear < 0.0) tnear = 0.0;

    vec3 rayStart = eye.Origin + eye.Dir * tnear;
    vec3 rayStop = eye.Origin + eye.Dir * tfar;
    rayStart = 0.5 * (rayStart + 1.0);
    rayStop = 0.5 * (rayStop + 1.0);

    vec3 pos = rayStart;
    vec3 dir = rayStop - rayStart;
    vec3 step = normalize(dir) * stepSize;
    float travel = distance(rayStop, rayStart);
    
    float len = length(dir);
    dir = normalize(dir);
       

    //clipPlaneDepth = 0.3;

    if (clip)
    {
        gl_FragColor.a = 0.0;   
        //next, see if clip plane faces viewer
        bool frontface = (dot(dir , clipPlane) > 0.0);
        //next, distance from ray origin to clip plane
        float dis = dot(dir,clipPlane);
        if (dis != 0.0  )  dis = (-clipPlaneDepth - dot(clipPlane, rayStart.xyz-0.5)) / dis;
        if ((!frontface) && (dis < 0.0)) return;
        if ((frontface) && (dis > len)) return;
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

    vec4 accum = vec4(0.0, 0.0, 0.0, 0.0);
    vec4 sample = vec4(0.0, 0.0, 0.0, 0.0);
    vec4 value = vec4(0.0, 0.0, 0.0, 0.0);
    
    if (dither) //jaggy artefact dithering
    {
        pos = pos + step * (fract(sin(gl_FragCoord.x * 12.9898 + gl_FragCoord.y * 78.233) * 43758.5453));
    }
    
    for (int i=0; i < numSamples && travel > 0.0; ++i, pos += step, travel -= stepSize) {

        float tf_pos;

        tf_pos = tex3D(tex, pos);   
        
        value = vec4(tf_pos);

        // Process the volume sample
        sample.a = value.a * opacityFactor * (1.0/float(numSamples));
        sample.rgb = value.rgb * sample.a * lightFactor;
                        
        accum.rgb += (1.0 - accum.a) * sample.rgb;
        accum.a += sample.a;

        if(accum.a>=1.0)
        break;
    }

    gl_FragColor.rgb = accum.rgb;
    gl_FragColor.a = accum.a;
}
"""

def replaceShader():
    #program_id = Buffer(GL_INT, 1)
    #glGetIntegerv(0x8B8D, program_id)#GL_CURRENT_PROGRAM
    #self.program = program_id[0]

    for prog in range(32767):
        if glIsProgram(prog) == True:
            program = prog 

    #Get the sahder generated by setSource()     
    maxCount = 9
    count = Buffer(GL_INT, 1)
    shaders = Buffer(GL_BYTE, [maxCount])
    glGetAttachedShaders(program, maxCount, count, shaders)

    #print(self.program)
    #print(shaders)
        
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
        own["error"] = True
        maxLength = 1000
        length = Buffer(GL_INT, 1) #Blender generates a GL_BYTE instead
        infoLog = Buffer(GL_BYTE, [maxLength])
        glGetShaderInfoLog(fragShader, maxLength, length, infoLog)
        print("---Fragment Shader fault---")                    
        print("".join(chr(infoLog[i]) for i in range(length[0])))

    return program

#
# Property (uniform) update functions
#

def update_azimuth(self, context):
    glUseProgram(program)
    glUniform1f(20, self.azimuth)
    glUseProgram(0)
 
def update_elevation(self, context):
    glUseProgram(program)
    glUniform1f(21, self.elevation) 
    glUseProgram(0)
    
def update_clipPlaneDepth(self, context):
    glUseProgram(program)
    glUniform1f(22, self.clipPlaneDepth) 
    glUseProgram(0)

def update_clip(self, context):
    glUseProgram(program)
    glUniform1f(23, self.clip)  
    glUseProgram(0)

def update_dither(self, context):
    glUseProgram(program)
    glUniform1f(24, self.dither) 
    glUseProgram(0)

def update_opacityFactor(self, context):
    glUseProgram(program)
    glUniform1f(25, self.opacityFactor) 
    glUseProgram(0)

def update_lightFactor(self, context):
    glUseProgram(program)
    glUniform1f(26, self.lightFactor) 
    glUseProgram(0)


#
#   Store properties in the active scene
#
def initSceneProperties(obj):
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
        
    bpy.types.Object.clip = BoolProperty(
        name = "Clip", 
        description = "True or False?",
        update=update_clip)
    obj['clip'] = False

    bpy.types.Object.dither = BoolProperty(
        name = "Dither", 
        description = "True or False?",
        update=update_dither)
    obj['dither'] = False


""" 
    # Example CODE
    bpy.types.Object.MyInt = IntProperty(
        name = "Integer", 
        description = "Enter an integer")
    obj['MyInt'] = 17
 
    bpy.types.Object.MyFloat = FloatProperty(
        name = "Float", 
        description = "Enter a float",
        default = 33.33,
        min = -100,
        max = 100)
 
    bpy.types.Object.MyBool = BoolProperty(
        name = "Boolean", 
        description = "True or False?")
    obj['MyBool'] = True
 
    bpy.types.Object.MyEnum = EnumProperty(
        items = [('Eins', 'Un', 'One'), 
                 ('Zwei', 'Deux', 'Two'),
                 ('Drei', 'Trois', 'Three')],
        name = "Ziffer")
    obj['MyEnum'] = 2
 
    bpy.types.Object.MyString = StringProperty(
        name = "String")
    obj['MyString'] = "Lorem ipsum dolor sit amet"
    return
"""

initSceneProperties(bpy.context.object)
program = replaceShader()

#
#   Menu in UI region
#
class UIPanel(bpy.types.Panel):
    bl_label = "Property panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    obj = bpy.context.object
    update_azimuth(obj, bpy.context)
    update_elevation(obj, bpy.context)
    update_clipPlaneDepth(obj, bpy.context)
    update_clip(obj, bpy.context)
    update_dither(obj, bpy.context)
    update_opacityFactor(obj, bpy.context)
    update_lightFactor(obj, bpy.context)

    def draw(self, context):
        layout = self.layout
        obj = context.object

        layout.prop(obj, 'azimuth')
        layout.prop(obj, 'elevation')
        layout.prop(obj, 'clipPlaneDepth')
        layout.prop(obj, 'opacityFactor')
        layout.prop(obj, 'lightFactor')
        layout.prop(obj, 'clip')
        layout.prop(obj, 'dither')

"""
        layout.prop(obj, 'MyInt', icon='BLENDER', toggle=True)
        layout.prop(obj, 'MyFloat')
        layout.prop(obj, 'MyBool')
        layout.prop(obj, 'MyEnum')
        layout.prop(obj, 'MyString')
        layout.operator("idname_must.be_all_lowercase_and_contain_one_dot")
"""
#
#   The button prints the values of the properites in the console.
#
""" 
class OBJECT_OT_PrintPropsButton(bpy.types.Operator):
    bl_idname = "idname_must.be_all_lowercase_and_contain_one_dot"
    bl_label = "Print props"
 
    def execute(self, context):
        obj = context.object
        printProp("Int: ", 'MyInt', obj)
        printProp("Float:  ", 'MyFloat', obj)
        printProp("Bool:   ", 'MyBool', obj)
        printProp("Enum:   ", 'MyEnum', obj)
        printProp("String: ", 'MyString', obj)
        return{'FINISHED'}  
 
def printProp(label, key, obj):
    try:
        val = obj[key]
    except:
        val = 'Undefined'
    print("%s %s" % (key, val))

"""
#   Registration
bpy.utils.register_module(__name__)