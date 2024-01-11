# MayaBVHImporter
A script to import BVH files into Maya, autodetecting the correct rotation order on a per joint basis

HOW TO OPERATE
In Maya's script editor, type (or copy and paste) the following:

import BVHImporter as bvh
bvh.ImportBVH(<path_to_file>, 1.0)

where 
<path_to_file> should be the path to the bvh file you want to import (i.e.: "D:/Users/<your user name>/Documents/dataset/motioncapture_data/walk_008.bvh")
and 1.0 is the scale at which the imported character should be reconstructed (1.0 = as described in the file, 0.5 = half the size, etc)
