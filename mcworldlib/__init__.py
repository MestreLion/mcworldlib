# mcworldlib - Minecraft save data library
#
#    Copyright (C) 2019 Rodrigo Silva (MestreLion) <minecraft@rodrigosilva.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program. See <http://www.gnu.org/licenses/gpl.html>

"""Yet another python library to manipulate Minecraft save data"""

from .anvil  import *
from .chunk  import *
from .cli    import *
from .level  import *
from .nbt    import *
from .tree   import Item, print_tree, walk as walk_data
from .world  import *
from .util   import *

# TODO: Change setup.cfg so it reads here instead of duplicating values!
__title__       = "mcworldlib"
__project__     = "MCWorldLib: Minecraft World Library"  # unused in setup.cfg
__description__ = "Yet another python library to manipulate Minecraft save data"  # __doc__
__author__      = "Rodrigo Silva (MestreLion)"
__email__       = "minecraft@rodrigosilva.com"
__version__     = '0.2021.10'

# Renaming stuff for the API
walk_nbt = walk  # from .nbt
del walk
