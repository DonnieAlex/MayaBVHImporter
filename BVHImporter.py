import maya.cmds as mc
import os, re
from typing import Optional

space_re = re.compile(r"\s+")

rotation_orders = [
    'XYZ',
    'YZX',
    'ZXY',
    'XZY',
    'YXZ',
    'ZYX'
]

def cleanPath(path:str)->str:
    return path.replace('\\', '/')

class TinyDAG(object):
    """
    Tiny DAG class for storing the hierarchy of the BVH file.
    """

    def __init__(self, obj:str, parent:Optional['TinyDAG']=None):
        """Constructor"""
        self.obj = obj
        self.__parent = parent

    @property
    def parent(self):
        """Returns the parent of the object"""
        return self.__parent

    def __str__(self) -> str:
        """String representation of the object"""
        return str(self.obj)

    def full_path(self) -> str:
        """Returns the full path of the object"""
        if self.parent is not None:
            return '%s|%s' % (self.parent.full_path(), str(self))
        return str(self.obj)
    
class ImportBVH:

    translationDict = {
            "Xposition": "translateX",
            "Yposition": "translateY",
            "Zposition": "translateZ",
            "Xrotation": "rotateX",
            "Yrotation": "rotateY",
            "Zrotation": "rotateZ"
            }


    def __init__(self, file_path:str, scale:float) -> None:
        file_path = cleanPath(file_path)
        self.data = None
        self.scale = scale
        self._channels = list()
        self._root_node = None
        self._root_node_full_path = None
        if not os.path.exists(file_path):
            raise Exception('File does not exist on disk')
        self.file_path = file_path
        self.getData(self.file_path, scale)
    
    @property
    def root_node(self)->str:
        return str(self._root_node_full_path)
        
    def getData(self, file_path:str, scale:float)->None:
        with open(file_path, 'r') as f:
            self.data = f.readlines()
        if not self.data[0].startswith('HIERARCHY'):
            self.data = None
            raise Exception('No valid bvh file was loaded')
        self.scale = scale
        self.readFile()
    

    def readFile(self)->None:
        # Safe close is needed for End Site part to keep from setting new
        # parent.
        safe_close = False
        # Once motion is active, animate.
        motion = False
        # Clear channels before appending
        self._channels.clear()
        frame = 0
        rot_order = str()

        if self._root_node is None:
            # Create a group for the rig, easier to scale.
            # (Freeze transform when ungrouping please..)
            mocap_name = os.path.basename(self.file_path)
            grp = mc.group(em=True, name=f'_mocap_{mocap_name}_grp')
            mc.setAttr(f'{grp}.scale', *[self.scale for i in range(3)])

            # The group is now the 'root'
            my_parent = TinyDAG(grp, None)
        else:
            mc.setAttr(f'{self.root_node.split("|")[0]}.scale', *[self.scale for i in range(3)])
            my_parent = TinyDAG(self._root_node, None)
            self._clear_animation()

        for line in self.data:
            line = line.replace('	', ' ')  # force spaces
            if not motion:
                # root joint
                if line.startswith('ROOT'):
                    # Set the Hip joint as root
                    if self._root_node:
                        my_parent = TinyDAG(str(self._root_node), None)
                    else:
                        my_parent = TinyDAG(line[5:].rstrip(), my_parent)
                        # Update root node in case we want to reload.
                        self._root_node = my_parent
                        self._root_node_full_path = my_parent.full_path()

                if 'JOINT' in line:
                    jnt = space_re.split(line.strip())
                    # Create the joint
                    my_parent = TinyDAG(jnt[1], my_parent)

                if 'End Site' in line:
                    # Finish up a hierarchy and ignore a closing bracket
                    safe_close = True

                if '}' in line:
                    # Ignore when safeClose is on
                    if safe_close:
                        safe_close = False
                        continue

                    # Go up one level
                    if my_parent is not None:
                        my_parent = my_parent.parent
                        if my_parent is not None:
                            mc.select(my_parent.full_path())

                if 'CHANNELS' in line:
                    chan = line.strip()
                    chan = space_re.split(chan)
                    axis = [i.replace('rotation', '') for i in chan[-3:]]
                    axis.reverse()
                    rot_order = rotation_orders.index(''.join(axis))

                    # Append the channels that are animated
                    for i in range(int(chan[1])):
                        self._channels.append(f'{my_parent.full_path()}.{self.translationDict[chan[2 + i]]}')
                    mc.setAttr(f'{jnt}.rotateOrder', rot_order)

                if 'OFFSET' in line:
                    offset = line.strip()
                    offset = space_re.split(offset)
                    jnt_name = str(my_parent)

                    # When End Site is reached, name it '_tip'
                    if safe_close:
                        jnt_name += '_tip'

                    # skip if exists
                    if mc.objExists(my_parent.full_path()):
                        jnt = my_parent.full_path()
                    else:
                        # Build a new joint
                        jnt = mc.joint(name=jnt_name, p=(0, 0, 0))

                    mc.setAttr(f'{jnt}.translate', *[float(i) for i in offset[1:]], typ='double3')
                    

                if 'MOTION' in line:
                    # Animate!
                    motion = True

            else:
                # We don't really need to use Frame count and time
                # (since Python handles file reads nicely)
                if 'Frame' not in line:
                    data = space_re.split(line.strip())
                    # Set the values to channels
                    for index, value in enumerate(data):
                        mc.setKeyframe(self._channels[index],
                                        time=frame,
                                        value=float(value))

                    frame += 1

    def _clear_animation(self):
        if self._root_node is None:
            raise Exception('Could not find root node to clear animation.')

        # Select hierarchy
        mc.select(str(self._root_node), hi=True)
        nodes = mc.ls(sl=True)

        trans_attrs = ['translateX', 'translateY', 'translateZ']
        rot_attrs = ['rotateX', 'rotateY', 'rotateZ']
        for node in nodes:
            for attr in trans_attrs + rot_attrs:
                # Delete input connections
                connections = mc.listConnections(f'{node}.{attr}',
                                                 s=True,
                                                 d=False)
                if connections is not None:
                    mc.delete(connections)

            for attr in rot_attrs:
                # Reset rotation
                mc.setAttr(f'{node}.{attr}', 0)